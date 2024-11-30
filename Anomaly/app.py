import connexion
import yaml
import logging
import logging.config
from connexion.middleware import MiddlewarePosition
from starlette.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from pykafka import KafkaClient
from connexion import NoContent
import json
import os
from datetime import datetime
import uuid

# Load configurations
if "TARGET_ENV" in os.environ and os.environ["TARGET_ENV"] == "test":
    print("In Test Environment")
    app_conf_file = "/config/app_conf.yml"
    log_conf_file = "/config/log_conf.yml"
else:
    print("In Dev Environment")
    app_conf_file = "app_conf.yml"
    log_conf_file = "log_conf.yml"

with open(app_conf_file, 'r') as f:
    app_config = yaml.safe_load(f.read())

with open(log_conf_file, 'r') as f:
    log_config = yaml.safe_load(f.read())
    logging.config.dictConfig(log_config)

logger = logging.getLogger('basicLogger')

# Configuration Variables
json_path = app_config['datastore']['filepath']
kafka_hostname = app_config['events']['hostname']
kafka_port = app_config['events']['port']
kafka_topic = app_config['events']['topic']
high_threshold = app_config['thresholds']['get_all_reviews']['max']
low_threshold = app_config['thresholds']['get_all_reviews']['min']

# Ensure JSON data file exists
def make_json_file():
    if not os.path.isfile(json_path):
        with open(json_path, 'w') as f:
            json.dump([], f, indent=4)

# Save anomaly to JSON
def store_anomaly(anomaly):
    with open(json_path, 'r+') as f:
        data = json.load(f)
        data.append(anomaly)
        f.seek(0)
        json.dump(data, f, indent=4)

# Process Kafka messages and detect anomalies
def anomaly_detector():
    make_json_file()
    hostname = f"{kafka_hostname}:{kafka_port}"
    client = KafkaClient(hosts=hostname)
    topic = client.topics[str.encode(kafka_topic)]
    consumer = topic.get_simple_consumer(
        reset_offset_on_start=True,
        consumer_timeout_ms=1000
    )
    logger.info("Anomaly Detector Service is running")

    try:
        for message in consumer:
            if message is not None:
                msg = message.value.decode('utf-8')
                msg = json.loads(msg)

                event_id = str(uuid.uuid4())
                trace_id = msg["payload"]["trace_id"]
                event_type = msg["type"]
                anomalies = []

                if event_type == "get_all_reviews":
                    review_length = len(msg["payload"]["review"])
                    if review_length > high_threshold:
                        anomalies.append({
                            "event_id": event_id,
                            "trace_id": trace_id,
                            "event_type": event_type,
                            "anomaly_type": "Too Long",
                            "description": f"Review length {review_length} exceeds high threshold {high_threshold}",
                            "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                        })
                    elif review_length < low_threshold:
                        anomalies.append({
                            "event_id": event_id,
                            "trace_id": trace_id,
                            "event_type": event_type,
                            "anomaly_type": "Too Short",
                            "description": f"Review length {review_length} is below low threshold {low_threshold}",
                            "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                        })

                if event_type == "rating_game":
                    rating_value = msg["payload"]["rating"]
                    if rating_value > high_threshold:
                        anomalies.append({
                            "event_id": event_id,
                            "trace_id": trace_id,
                            "event_type": event_type,
                            "anomaly_type": "High Rating",
                            "description": f"Rating {rating_value} exceeds high threshold {high_threshold}",
                            "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                        })
                    elif rating_value < low_threshold:
                        anomalies.append({
                            "event_id": event_id,
                            "trace_id": trace_id,
                            "event_type": event_type,
                            "anomaly_type": "Low Rating",
                            "description": f"Rating {rating_value} is below low threshold {low_threshold}",
                            "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                        })

                for anomaly in anomalies:
                    store_anomaly(anomaly)
                    logger.info(f"Anomaly detected: {anomaly}")

    except Exception as e:
        logger.error(f"Error in anomaly detection: {e}")
        return NoContent, 404

# Retrieve anomalies
def get_anomalies(anomaly_type=None):
    logger.info("Request for retrieving anomalies started")

    valid_anomaly_types = ["Too Short", "Too Long", "Low Rating", "High Rating"]
    if anomaly_type and anomaly_type not in valid_anomaly_types:
        logger.error("Invalid anomaly type requested")
        return {"message": "Invalid anomaly type"}, 400

    if os.path.isfile(json_path):
        with open(json_path, 'r') as f:
            data = json.load(f)

        if anomaly_type:
            data = [d for d in data if d["anomaly_type"] == anomaly_type]

        if not data:
            logger.warning("No anomalies found")
            return {"message": "No anomalies found"}, 404

        logger.info("Anomalies retrieved successfully")
        return data, 200
    else:
        logger.warning("Anomaly data file not found")
        return {"message": "No anomalies found"}, 404

# Initialize scheduler
def init_scheduler():
    sched = BackgroundScheduler(daemon=True)
    sched.add_job(anomaly_detector, 'interval', seconds=app_config['scheduler']['period_sec'])
    sched.start()

# FlaskApp setup
app = connexion.FlaskApp(__name__, specification_dir='.')
app.add_api("openapi.yaml", strict_validation=True, validate_responses=True)
app.add_middleware(
    CORSMiddleware,
    position=MiddlewarePosition.BEFORE_EXCEPTION,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

if __name__ == "__main__":
    make_json_file()
    init_scheduler()
    app.run(port=8120, host="0.0.0.0")

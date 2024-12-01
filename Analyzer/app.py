import connexion
import yaml
import logging
import logging.config
from connexion import NoContent
from pykafka import KafkaClient
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import json
import os
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

# Constants
DATA_STORE = app_config['datastore']['filepath']
KAFKA_HOSTNAME = app_config['events']['hostname']
KAFKA_PORT = app_config['events']['port']
KAFKA_TOPIC = app_config['events']['topic']

# Initialize JSON datastore
def initialize_json_file():
    if not os.path.exists(DATA_STORE):
        logger.info(f"Initializing datastore at {DATA_STORE}")
        with open(DATA_STORE, 'w') as f:
            json.dump([], f, indent=4)

# Save an anomaly to JSON datastore
def save_anomaly(anomaly):
    with open(DATA_STORE, 'r+') as f:
        data = json.load(f)
        data.append(anomaly)
        f.seek(0)
        json.dump(data, f, indent=4)
    logger.info(f"Anomaly saved: {anomaly}")

# Process Kafka events and detect anomalies
def process_events():
    logger.info("Processing Kafka events for anomalies...")
    hostname = f"{KAFKA_HOSTNAME}:{KAFKA_PORT}"
    client = KafkaClient(hosts=hostname)
    topic = client.topics[KAFKA_TOPIC.encode('utf-8')]
    consumer = topic.get_simple_consumer(consumer_timeout_ms=1000)

    try:
        for msg in consumer:
            if msg is None:
                logger.info("No new messages")
                break

            event = json.loads(msg.value.decode('utf-8'))
            logger.debug(f"Received event: {event}")

            event_type = event['type']
            trace_id = event['payload']['trace_id']
            anomalies = []

            # Detect anomalies for get_all_reviews
            if event_type == 'get_all_reviews':
                value = event['payload']['get_all_reviews']
                if value < app_config['thresholds']['get_all_reviews']['min']:
                    anomalies.append({
                        "event_id": str(uuid.uuid4()),
                        "event_type": event_type,
                        "trace_id": trace_id,
                        "anomaly_type": "Too Low",
                        "description": f"Value {value} is below the minimum threshold",
                        "timestamp": datetime.now().isoformat()
                    })
                if value > app_config['thresholds']['get_all_reviews']['max']:
                    anomalies.append({
                        "event_id": str(uuid.uuid4()),
                        "event_type": event_type,
                        "trace_id": trace_id,
                        "anomaly_type": "Too High",
                        "description": f"Value {value} is above the maximum threshold",
                        "timestamp": datetime.now().isoformat()
                    })

            # Detect anomalies for rating_game
            if event_type == 'rating_game':
                value = event['payload']['rating_game']
                if value < app_config['thresholds']['rating_game']['min']:
                    anomalies.append({
                        "event_id": str(uuid.uuid4()),
                        "event_type": event_type,
                        "trace_id": trace_id,
                        "anomaly_type": "Low Rating",
                        "description": f"Value {value} is below the minimum threshold",
                        "timestamp": datetime.now().isoformat()
                    })
                if value > app_config['thresholds']['rating_game']['max']:
                    anomalies.append({
                        "event_id": str(uuid.uuid4()),
                        "event_type": event_type,
                        "trace_id": trace_id,
                        "anomaly_type": "High Rating",
                        "description": f"Value {value} is above the maximum threshold",
                        "timestamp": datetime.now().isoformat()
                    })

            # Save all detected anomalies
            for anomaly in anomalies:
                save_anomaly(anomaly)

    except Exception as e:
        logger.error(f"Error processing events: {str(e)}")

# Retrieve anomalies via REST API
def get_anomalies(anomaly_type=None, event_type=None):
    logger.info("Request for anomalies received")
    with open(DATA_STORE, 'r') as f:
        data = json.load(f)

    if anomaly_type:
        data = [anomaly for anomaly in data if anomaly["anomaly_type"] == anomaly_type]
    if event_type:
        data = [anomaly for anomaly in data if anomaly["event_type"] == event_type]

    if not data:
        return {"message": "No anomalies found"}, 404

    return data, 200

# Scheduler setup
def init_scheduler():
    sched = BackgroundScheduler(daemon=True)
    sched.add_job(process_events, 'interval', seconds=app_config['scheduler']['period_sec'])
    sched.start()
    logger.info("Scheduler initialized")

# Application setup
app = connexion.FlaskApp(__name__, specification_dir='.')
app.add_api("openapi.yaml", strict_validation=True, validate_responses=True)

if __name__ == "__main__":
    initialize_json_file()
    init_scheduler()
    app.run(port=8120, host="0.0.0.0")

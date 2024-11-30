import connexion
import yaml
import logging
import logging.config
from connexion.middleware import MiddlewarePosition
from starlette.middleware.cors import CORSMiddleware
from pykafka import KafkaClient
from pykafka.common import OffsetType
import os
import json
from datetime import datetime
from threading import Thread

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

# Kafka Configuration
kafka_hostname = f"{app_config['events']['hostname']}:{app_config['events']['port']}"
client = KafkaClient(hosts=kafka_hostname)
topic = client.topics[str.encode(app_config["events"]["topic"])]

# JSON Data Store
DATA_STORE = app_config['datastore']['filepath']

def make_json_file():
    """Ensure the JSON anomaly file exists."""
    if not os.path.isfile(DATA_STORE):
        with open(DATA_STORE, 'w') as f:
            json.dump([], f, indent=4)

def save_anomaly(anomaly):
    """Save a detected anomaly to the JSON file."""
    with open(DATA_STORE, 'r+') as f:
        data = json.load(f)
        data.append(anomaly)
        f.seek(0)
        json.dump(data, f, indent=4)

def process_event(event):
    """Process a Kafka event and detect anomalies."""
    event_id = event.get("event_id")
    event_type = event.get("type")
    payload = event.get("payload")
    trace_id = event.get("trace_id")
    logger.info(f"Received event: {event}")

    if event_type == "get_all_reviews":
        review_length = len(payload.get("review", ""))
        if review_length < app_config["thresholds"]["get_all_reviews"]["min"]:
            anomaly = {
                "event_id": event_id,
                "event_type": event_type,
                "trace_id": trace_id,
                "anomaly_type": "Too Short",
                "description": f"Review length {review_length} is below the minimum threshold",
                "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            }
            logger.info(f"Anomaly detected: {anomaly}")
            save_anomaly(anomaly)

    elif event_type == "rating_game":
        rating_value = payload.get("rating")
        if rating_value < app_config["thresholds"]["rating_game"]["min"]:
            anomaly = {
                "event_id": event_id,
                "event_type": event_type,
                "trace_id": trace_id,
                "anomaly_type": "Low Rating",
                "description": f"Rating {rating_value} is below the minimum threshold",
                "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            }
            logger.info(f"Anomaly detected: {anomaly}")
            save_anomaly(anomaly)

    else:
        logger.warning(f"Unhandled event type: {event_type}")

def consume_kafka_events():
    """Consume Kafka events in a separate thread."""
    consumer = topic.get_simple_consumer(
        reset_offset_on_start=False,
        consumer_timeout_ms=1000,
        auto_offset_reset=OffsetType.LATEST
    )
    logger.info("Kafka consumer initialized.")
    try:
        for msg in consumer:
            if msg is not None:
                msg_str = msg.value.decode('utf-8')
                event = json.loads(msg_str)
                process_event(event)
    except Exception as e:
        logger.error(f"Error consuming events: {str(e)}")

def get_anomalies(event_type=None):
    """Retrieve anomalies from the JSON file."""
    logger.info("Request for anomalies received.")
    try:
        with open(DATA_STORE, 'r') as f:
            anomalies = json.load(f)
    except FileNotFoundError:
        anomalies = []

    if event_type:
        anomalies = [a for a in anomalies if a['event_type'] == event_type]

    if not anomalies:
        logger.warning("No anomalies found.")
        return {"message": "No anomalies found"}, 404

    return anomalies, 200

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
    kafka_thread = Thread(target=consume_kafka_events)
    kafka_thread.daemon = True
    kafka_thread.start()
    app.run(port=8120, host="0.0.0.0")

import connexion
import json
import yaml
import logging.config
import os
from connexion.middleware import MiddlewarePosition
from starlette.middleware.cors import CORSMiddleware
from pykafka import KafkaClient
from pykafka.common import OffsetType
from datetime import datetime

if "TARGET_ENV" in os.environ and os.environ["TARGET_ENV"] == "test":
    print("In Test Environment")
    app_conf_file = "/config/app_conf.yml"
    log_conf_file = "/config/log_conf.yml"
else:
    print("In Dev Environment")
    app_conf_file = "app_conf.yml"
    log_conf_file = "log_conf.yml"

# Load application configuration
with open(app_conf_file, 'r') as f:
    app_config = yaml.safe_load(f.read())

# Load logging configuration
with open(log_conf_file, 'r') as f:
    log_config = yaml.safe_load(f.read())
    logging.config.dictConfig(log_config)

# Set up logger
logger = logging.getLogger('basicLogger')
logger.info("App Conf File: %s", app_conf_file)
logger.info("Log Conf File: %s", log_conf_file)
# Kafka setup
hostname = f"{app_config['events']['hostname']}:{app_config['events']['port']}"
client = KafkaClient(hosts=hostname)
topic = client.topics[str.encode(app_config["events"]["topic"])]

# JSON data store
DATA_STORE = app_config['datastore']['filepath']

def get_kafka_consumer():
    """Initialize Kafka consumer."""
    consumer = topic.get_simple_consumer(
        reset_offset_on_start=False,
        consumer_timeout_ms=1000,
        auto_offset_reset=OffsetType.LATEST
    )
    return consumer

def save_anomaly(anomaly):
    try:
        logger.debug(f"Attempting to read file: {app_config['datastore']['filename']}")
        with open(app_config['datastore']['filename'], 'r') as f:
            anomalies = json.load(f)
    except FileNotFoundError:
        logger.warning("Datastore file not found. Initializing a new list.")
        anomalies = []

    anomalies.append(anomaly)

    try:
        logger.debug(f"Attempting to write to file: {app_config['datastore']['filename']}")
        with open(app_config['datastore']['filename'], 'w') as f:
            json.dump(anomalies, f, indent=4)
        logger.info("Successfully saved anomaly.")
    except Exception as e:
        logger.error(f"Failed to write to file: {str(e)}")



def process_event(event):
    """Process Kafka event for anomaly detection."""
    event_id = event.get("event_id")
    event_type = event.get("type")
    payload = event.get("payload")
    trace_id = event.get("trace_id")
    logger.info(f"Received event: {event}")

    if event_type == "get_all_reviews":
        # Example anomaly check for review events
        review_length = len(payload.get("review", ""))
        if review_length < app_config["thresholds"]["review_length"]["min"]:
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
        # Example anomaly check for game ratings
        rating_value = payload.get("rating")
        if rating_value < app_config["thresholds"]["rating"]["min"]:
            anomaly = {
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
    """Background thread to consume Kafka events."""
    consumer = get_kafka_consumer()
    try:
        for msg in consumer:
            if msg is not None:
                msg_str = msg.value.decode('utf-8')
                event = json.loads(msg_str)
                process_event(event)
    except Exception as e:
        logger.error(f"Error consuming events: {str(e)}")

# REST API endpoints
def get_anomalies(anomaly_type):
    """Retrieve anomalies by type."""
    try:
        with open(DATA_STORE, 'r') as f:
            anomalies = json.load(f)
    except FileNotFoundError:
        anomalies = []

    filtered_anomalies = [a for a in anomalies if a['anomaly_type'] == anomaly_type]
    return filtered_anomalies, 200

# Set up FlaskApp and routes
app = connexion.FlaskApp(__name__, specification_dir='.')
app.add_api('openapi.yaml')
app.add_middleware(
    CORSMiddleware,
    position=MiddlewarePosition.BEFORE_EXCEPTION,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

if __name__ == '__main__':
    from threading import Thread

    # Start Kafka consumer in a separate thread
    kafka_thread = Thread(target=consume_kafka_events)
    kafka_thread.daemon = True
    kafka_thread.start()

    app.run(port=8120, host='0.0.0.0')

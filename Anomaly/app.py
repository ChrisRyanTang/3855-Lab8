import connexion
import yaml
import logging
import logging.config
from connexion.middleware import MiddlewarePosition
from starlette.middleware.cors import CORSMiddleware
from pykafka import KafkaClient
from pykafka.common import OffsetType
from apscheduler.schedulers.background import BackgroundScheduler
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
# kafka_hostname = f"{app_config['events']['hostname']}:{app_config['events']['port']}"
# client = KafkaClient(hosts=kafka_hostname)
# topic = client.topics[str.encode(app_config["events"]["topic"])]
get_all_reviews_thresholds = app_config["thresholds"]["get_all_reviews"]
rating_game_thresholds = app_config["thresholds"]["rating_game"]



# JSON Data Store
DATA_STORE = app_config['datastore']['filepath']
kafka_consumer = None

def init_kafka_consumer():
    """Initialize the Kafka consumer."""
    global kafka_consumer
    kafka_hostname = f"{app_config['events']['hostname']}:{app_config['events']['port']}"
    client = KafkaClient(hosts=kafka_hostname)
    topic = client.topics[str.encode(app_config["events"]["topic"])]

    kafka_consumer = topic.get_simple_consumer(
        reset_offset_on_start=False,
        consumer_timeout_ms=1000,
        auto_offset_reset=OffsetType.LATEST
    )
    logger.info("Kafka consumer initialized.")


def make_json_file():
    """Ensure the JSON anomaly file exists."""
    if not os.path.isfile(DATA_STORE):
        with open(DATA_STORE, 'w') as f:
            json.dump([], f, indent=4)

def save_anomaly(anomaly):
    """Save a detected anomaly to the JSON file."""
    try:
        with open(DATA_STORE, 'r+') as f:
            data = json.load(f)  # Load existing anomalies
            data.append(anomaly)  # Append the new anomaly
            f.seek(0)  # Reset file pointer to the beginning
            json.dump(data, f, indent=4)  # Write updated anomalies
        logger.info("Anomaly saved successfully.")
    except FileNotFoundError:
        # If the file doesn't exist, create it and save the anomaly
        with open(DATA_STORE, 'w') as f:
            json.dump([anomaly], f, indent=4)
        logger.info("Anomaly file not found. Created a new file and saved anomaly.")
    except Exception as e:
        logger.error(f"Error saving anomaly: {str(e)}")

def process_events_from_kafka():
    """Fetch events from Kafka and process them."""
    global kafka_consumer
    try:
        for msg in kafka_consumer:
            if msg is not None:
                event = json.loads(msg.value.decode('utf-8'))
                process_event(event)
    except Exception as e:
        logger.error(f"Error fetching events from Kafka: {str(e)}")


def process_event(event):
    """Process a single event and detect anomalies."""
    event_id = event.get("event_id")
    event_type = event.get("type")
    payload = event.get("payload")
    trace_id = event.get("trace_id")
    logger.info(f"Processing event: {event}")

    anomalies = []

    if event_type == "get_all_reviews":
        review_length = payload.get("reviews", 0)
        if review_length < app_config["thresholds"]["get_all_reviews"]["min"]:
            anomalies.append({
                "event_id": event_id,
                "event_type": event_type,
                "trace_id": trace_id,
                "anomaly_type": "Too Short",
                "description": f"Review length {review_length} is below the minimum threshold",
                "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            })
        if review_length > app_config["thresholds"]["get_all_reviews"]["max"]:
            anomalies.append({
                "event_id": event_id,
                "event_type": event_type,
                "trace_id": trace_id,
                "anomaly_type": "Too Long",
                "description": f"Review length {review_length} is above the maximum threshold",
                "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            })

    if event_type == "rating_game":
        rating_value = payload.get("rating", 0)
        if rating_value < app_config["thresholds"]["rating_game"]["min"]:
            anomalies.append({
                "event_id": event_id,
                "event_type": event_type,
                "trace_id": trace_id,
                "anomaly_type": "Low Rating",
                "description": f"Rating {rating_value} is below the minimum threshold",
                "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            })
        if rating_value > app_config["thresholds"]["rating_game"]["max"]:
            anomalies.append({
                "event_id": event_id,
                "event_type": event_type,
                "trace_id": trace_id,
                "anomaly_type": "High Rating",
                "description": f"Rating {rating_value} is above the maximum threshold",
                "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            })

    for anomaly in anomalies:
        save_anomaly(anomaly)
        logger.info(f"Anomaly detected: {anomaly}")

            
def init_scheduler():
    sched = BackgroundScheduler(daemon=True)
    sched.add_job(process_events_from_kafka, 'interval', seconds=app_config['scheduler']['period_sec'])
    sched.start()



def get_anomalies(event_type=None):
    """Retrieve anomalies from the JSON file."""
    logger.info("Request for anomalies received.")
    
    valid_types = ["get_all_reviews", "rating_game"]
    if event_type and event_type not in valid_types:
        return {"message": "Invalid event type"}, 400

    if os.path.isfile(DATA_STORE):
        with open(DATA_STORE, 'r') as f:
            data = json.load(f)
            
        if event_type:
            data = [d for d in data if d["event_type"] == event_type]
        
        if not data:
            return {"message": "No anomalies found"}, 404
        
        logger.debug(f"Returning anomalies: {data}")
        logger.info(f"Anomalies retrieved successfully.")
        return data, 200
    else:
        return {"message": "No anomalies found"}, 404

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
    init_kafka_consumer()
    init_scheduler()
    app.run(port=8120, host="0.0.0.0")

import connexion
import yaml
import logging
import logging.config
from connexion import NoContent
from connexion.middleware import MiddlewarePosition
from starlette.middleware.cors import CORSMiddleware
from pykafka import KafkaClient
from pykafka.common import OffsetType
from apscheduler.schedulers.background import BackgroundScheduler
import os
import json
import uuid
from datetime import datetime

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
get_all_reviews_thresholds = app_config["thresholds"]["get_all_reviews"]
rating_game_thresholds = app_config["thresholds"]["rating_game"]
kafka_hostname = app_config['events']['hostname']
kafka_port = app_config['events']['port']
kafka_topic = app_config['events']['topic']
DATA_STORE = app_config['datastore']['filepath']



def make_json_file():
    """Ensure the JSON anomaly file exists."""
    if not os.path.isfile(DATA_STORE):
        logger.info(f'Initialized datastore: {DATA_STORE}')
        with open(DATA_STORE, 'w') as f:
            json.dump([], f, indent=4)

def save_anomaly(anomaly):
    """Save a detected anomaly to the JSON file."""
    try:
        with open(DATA_STORE, 'r+') as f:
            data = json.load(f)
            data.append(anomaly)
            f.seek(0)
            json.dump(data, f, indent=4)
        logger.info(f"Anomaly saved: {anomaly}")
    except Exception as e:
        logger.error(f"Error saving anomaly: {str(e)}")

# def process_events_from_kafka():
#     """Fetch events from Kafka and process them."""
#     global kafka_consumer
#     try:
#         for msg in kafka_consumer:
#             if msg is not None:
#                 event = json.loads(msg.value.decode('utf-8'))
#                 process_event(event)
#     except Exception as e:
#         logger.error(f"Error fetching events from Kafka: {str(e)}")

def process_events():
    logger.info("Processing Kafka events for anomalies...")
    hostname = f"{kafka_hostname}:{kafka_port}"
    client = KafkaClient(hosts=hostname)
    topic = client.topics[kafka_topic.encode('utf-8')]
    consumer = topic.get_simple_consumer(consumer_timeout_ms=1000, reset_offset_on_start=False)

    # Dictionary to track review counts by game_id
    review_counts = {}

    try:
        for msg in consumer:
            if msg is None:
                logger.info("No new messages")
                break

            # Log the raw Kafka message
            # logger.debug(f"Raw Kafka message: {msg.value.decode('utf-8')}")

            # Parse the Kafka message
            event = json.loads(msg.value.decode('utf-8'))
            logger.info(f"Processing event: {event}")

            event_type = event.get('type')
            if event_type not in ['get_all_reviews', 'rating_game']:
                logger.warning(f"Unexpected event type: {event_type}")
                continue

            # Extract fields
            game_id = event['payload'].get('game_id', "Unknown")
            trace_id = event['payload'].get('trace_id', "Unknown")
            num_reviews = event['payload'].get('num_reviews', "Unknown")
            anomalies = []

            # Process 'get_all_reviews' events
            if event_type == 'get_all_reviews':
                # game_id = event['payload'].get('game_id', "Unknown")
                if game_id < app_config['thresholds']['get_all_reviews']['min']:
                    anomalies.append({
                        "event_id": str(event['payload'].get('game_id', "Unknown")),  
                        "event_type": event_type,
                        "trace_id": trace_id,
                        "anomaly_type": "Too Few Reviews",
                        "description": f"Game Id {game_id} is below the minimum threshold",
                        "timestamp": datetime.now().isoformat()
                    })
                if game_id > app_config['thresholds']['get_all_reviews']['max']:
                    anomalies.append({
                        "event_id": str(event['payload'].get('game_id', "Unknown")),  
                        "event_type": event_type,
                        "trace_id": trace_id,
                        "anomaly_type": "Too Many Reviews",
                        "description": f"Game Id {game_id} is above the maximum threshold",
                        "timestamp": datetime.now().isoformat()
                    })

            # Process 'rating_game' events (unchanged)
            elif event_type == 'rating_game':
                num_reviews = event['payload'].get('num_reviews', "Unknown")
                if num_reviews < app_config['thresholds']['rating_game']['min']:
                    anomalies.append({
                        "event_id": int(event['payload'].get('num_reviews', "Unknown")),
                        "event_type": event_type,
                        "trace_id": trace_id,
                        "anomaly_type": "Too Few Ratings",
                        "description": f"Number of reviews {num_reviews} is below the minimum threshold",
                        "timestamp": datetime.now().isoformat()
                    })
                if num_reviews > app_config['thresholds']['rating_game']['max']:
                    anomalies.append({
                        "event_id": int(event['payload'].get('num_reviews', "Unknown")),
                        "event_type": event_type,
                        "trace_id": trace_id,
                        "anomaly_type": "Too Many Ratings",
                        "description": f"Number of reviews {num_reviews} is above the maximum threshold",
                        "timestamp": datetime.now().isoformat()
                    })

            # logger.debug(f"Anomalies detected for get_all_reviews: {anomalies}")

            # Save all detected anomalies
            for anomaly in anomalies:
                save_anomaly(anomaly)

    except Exception as e:
        logger.error(f"Error processing events: {str(e)}")



def get_anomalies(anomaly_type=None, event_type=None):
    """Retrieve anomalies from the JSON file."""
    logger.info("Request for anomalies received.")

    valid_anomaly_types = ["TooHigh", "TooLow", "Too Many Reviews", "Too Few Reviews", "Too Many Ratings", "Too Few Ratings"]
    valid_event_types = ["get_all_reviews", "rating_game"]

    if anomaly_type and anomaly_type not in valid_anomaly_types:
        logger.error(f"Invalid Anomaly Type requested: {anomaly_type}")
        return {"message": "Invalid anomaly type"}, 400
    
    if event_type and event_type not in valid_event_types:
        logger.error(f"Invalid Event Type requested: {event_type}")
        return {"message": "Invalid event type"}, 400

    if os.path.isfile(DATA_STORE):
        with open(DATA_STORE, 'r') as f:
            data = json.load(f)

        # Filter by anomaly_type if provided
        if anomaly_type:
            data = [anomaly for anomaly in data if anomaly["anomaly_type"] == anomaly_type]
            logger.debug(f"Returning anomalies of type {anomaly_type}: {data}")
        
        # Filter by event_type if provided
        if event_type:
            data = [anomaly for anomaly in data if anomaly["event_type"] == event_type]


        if not data:
            logger.warning("No anomalies found.")
            return {"message": "No anomalies found"}, 404

        logger.debug(f"Returning anomalies: {data}")
        logger.info("Anomalies retrieved successfully.")
        return data, 200
    
    else:
        logger.warning("Anomaly data file not found.")
        return {"message": "No anomalies found"}, 404
    
def init_scheduler():
    sched = BackgroundScheduler(daemon=True)
    sched.add_job(process_events, 'interval', seconds=app_config['scheduler']['period_sec'])
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

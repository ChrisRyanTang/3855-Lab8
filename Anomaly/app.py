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

def process_event():
    """Process a single event and detect anomalies."""
    make_json_file()
    hostname = "%s:%d" % (kafka_hostname, kafka_port)
    client = KafkaClient(hosts=hostname)
    topic = client.topics[str.encode(kafka_topic)]
    consumer = topic.get_simple_consumer(
        reset_offset_on_start=False,
        consumer_timeout_ms=1000,
        # auto_offset_reset=OffsetType.LATEST
    )
    try:
        for msg in consumer:
            if msg is not None:
                logger.info("No message received")
                break
            
            msg = msg.value.decode('utf-8')
            logger.info(f"Processing event: {msg}")
            event_id = str(uuid.uuid4())
            event_type = msg['type']
            trace_id = msg['payload']["trace_id"]

            anomalies = []

            if event_type == 'get_all_reviews':
                get_all_reviews = msg['payload']["get_all_reviews"]
                if get_all_reviews < get_all_reviews_thresholds["min"]:
                    anomalies.append({
                        "event_id": event_id,
                        "event_type": event_type,
                        "trace_id": trace_id,
                        "anomaly_type": "Too Short",
                        "description": f"Review length {get_all_reviews} is below the minimum threshold",
                        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                    })
                if get_all_reviews > get_all_reviews_thresholds["max"]:
                    anomalies.append({
                        "event_id": event_id,
                        "event_type": event_type,
                        "trace_id": trace_id,
                        "anomaly_type": "Too Long",
                        "description": f"Review length {get_all_reviews} is above the maximum threshold",
                        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                    })

            if event_type == "rating_game":
                rating_game = msg['payload']["rating_game"]
                if rating_game < rating_game_thresholds["min"]:
                    anomalies.append({
                        "event_id": event_id,
                        "event_type": event_type,
                        "trace_id": trace_id,
                        "anomaly_type": "Low Rating",
                        "description": f"Rating {rating_game} is below the minimum threshold",
                        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                    })
                if rating_game > rating_game_thresholds["max"]:
                    anomalies.append({
                        "event_id": event_id,
                        "event_type": event_type,
                        "trace_id": trace_id,
                        "anomaly_type": "High Rating",
                        "description": f"Rating {rating_game} is above the maximum threshold",
                        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                    })

            for anomaly in anomalies:
                save_anomaly(anomaly)
                logger.info(f"Anomaly detected: {anomaly}")
    except Exception as e:
        logger.error(f"Error processing event: {str(e)}")
        return NoContent, 404


def get_anomalies(anomaly_type=None):
    """Retrieve anomalies from the JSON file."""
    logger.info("Request for anomalies received.")

    valid_anomaly_types = ["TooHigh", "TooLow", "Too Short", "Too Long", "Low Rating", "High Rating"]
    if anomaly_type and anomaly_type not in valid_anomaly_types:
        logger.error(f"Invalid Anomaly Type requested: {anomaly_type}")
        return {"message": "Invalid anomaly type"}, 400

    if os.path.isfile(DATA_STORE):
        with open(DATA_STORE, 'r') as f:
            data = json.load(f)

        # Filter by anomaly_type if provided
        if anomaly_type:
            data = [anomaly for anomaly in data if anomaly["anomaly_type"] == anomaly_type]
            logger.debug(f"Returning anomalies of type {anomaly_type}: {data}")
        
        # Filter by event_type if provided
        # if event_type:
        #     data = [d for d in data if d["event_type"] == event_type]

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
    sched.add_job(process_event, 'interval', seconds=app_config['scheduler']['period_sec'])
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

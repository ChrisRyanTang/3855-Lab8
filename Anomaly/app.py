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
high_threshold = app_config["thresholds"]["high"]
low_threshold = app_config["thresholds"]["low"]


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
    kafka_hostname = f"{app_config['events']['hostname']}:{app_config['events']['port']}"
    topic = client.topics[str.encode(app_config["events"]["topic"])]
    client = KafkaClient(hosts=kafka_hostname)
    consumer = topic.get_simple_consumer(
        reset_offset_on_start=True,
        consumer_timeout_ms=1000,
        # auto_offset_reset=OffsetType.LATEST
    )
    try:
        for msg in consumer:
            msg_str = msg.value.decode('utf-8')
            event = json.loads(msg_str)
            process_event(event)

            event_id = event.get("event_id")
            event_type = event.get("type")
            payload = event.get("payload")
            trace_id = event.get("trace_id")
            logger.info(f"Received event: {event}")

            anomaly = []
            

        if event_type == "get_all_reviews":
            get_all_reviews = payload.get("reviews")
            if get_all_reviews < low_threshold:
                anomaly.append = ({
                    "event_id": event_id,
                    "event_type": event_type,
                    "trace_id": trace_id,
                    "anomaly_type": "Too Short",
                    "description": f"Review length {get_all_reviews} is below the minimum threshold",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                })
            if event_type == "get_all_reviews":
                get_all_reviews = payload.get("reviews")
                if get_all_reviews > high_threshold:
                    anomaly.append = ({
                        "event_id": event_id,
                        "event_type": event_type,
                        "trace_id": trace_id,
                        "anomaly_type": "Too Long",
                        "description": f"Review length {get_all_reviews} is above the maximum threshold",
                        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                    })

        if event_type == "rating_game":
            rating_game = payload.get("rating")
            if rating_game < low_threshold:
                anomaly.append = ({
                    "event_id": event_id,
                    "event_type": event_type,
                    "trace_id": trace_id,
                    "anomaly_type": "Low Rating",
                    "description": f"Rating {rating_game} is below the minimum threshold",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                })
            if event_type == "rating_game":
                rating_game = payload.get("rating")
                if rating_game > high_threshold:
                    anomaly.append = ({
                        "event_id": event_id,
                        "event_type": event_type,
                        "trace_id": trace_id,
                        "anomaly_type": "High Rating",
                        "description": f"Rating {rating_game} is above the maximum threshold",
                        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                    })
            
            for a in anomaly:
                save_anomaly(a)
                logger.info(f"Anomaly detected: {a}")
    except Exception as e:
        logger.error(f"Error processing event: {str(e)}")
        return {"message": "Error processing event"}, 404
            
def init_scheduler():
    sched = BackgroundScheduler(daemon=True)
    sched.add_job(process_event, 'interval', seconds=app_config['scheduler']['period_sec'])
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
    init_scheduler()
    app.run(port=8120, host="0.0.0.0")

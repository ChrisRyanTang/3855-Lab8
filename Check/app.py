import connexion
import logging.config
import yaml
import requests
from connexion.middleware import MiddlewarePosition
from starlette.middleware.cors import CORSMiddleware
from pykafka import KafkaClient
from pykafka.common import OffsetType
from apscheduler.schedulers.background import BackgroundScheduler
import os
import json

# Load application configuration
with open('app_conf.yml', 'r') as f:
    app_config = yaml.safe_load(f.read())

# Load logging configuration
with open('log_conf.yml', 'r') as f:
    log_config = yaml.safe_load(f.read())
    logging.config.dictConfig(log_config)

logger = logging.getLogger('basicLogger')

def get_kafka_consumer():
    client = KafkaClient(hosts=f"{app_config['events']['hostname']}:{app_config['events']['port']}")
    topic = client.topics[str.encode(app_config['events']['topic'])]
    consumer = topic.get_simple_consumer(
        reset_offset_on_start=False,
        consumer_timeout_ms=1000,
        auto_offset_reset=OffsetType.LATEST
    )
    return consumer

RECEIVER_URL = f"{app_config['Receiver']['url']}"
STORAGE_URL = f"{app_config['Storage']['url']}"
PROCESSING_URL = f"{app_config['Processing']['url']}"
ANALYZER_URL = f"{app_config['Analyzer']['url']}"
TIMEOUT = f"{app_config['timeout']}"
STATUS_FILE = f"{app_config['datastore']['filename']}"

def check_services():
    """ Called periodically """
    status = {}

    try:
        response = requests.get(RECEIVER_URL, timeout=TIMEOUT)
        status['receiver'] = "Healthy" if response.status_code == 200 else "Unavailable"
    except (TimeoutError, ConnectionError):
        status['receiver'] = "Unavailable"

    try:
        response = requests.get(STORAGE_URL, timeout=TIMEOUT)
        if response.status_code == 200:
            storage_json = response.json()
            status['storage'] = f"Storage has {storage_json['num_reviews']} NR and {storage_json['num_ratings']} NR events"
        else:
            status['storage'] = "Unavailable"
    except (TimeoutError, ConnectionError):
        status['storage'] = "Unavailable"

    try:
        response = requests.get(PROCESSING_URL, timeout=TIMEOUT)
        if response.status_code == 200:
            processing_json = response.json()
            status['processing'] = f"Processing has {processing_json['num_reviews']} NR and {processing_json['num_ratings']} NR events"
        else:
            status['processing'] = "Unavailable"
    except (TimeoutError, ConnectionError):
        status['processing'] = "Unavailable"

    try:
        response = requests.get(ANALYZER_URL, timeout=TIMEOUT)
        if response.status_code == 200:
            analyzer_json = response.json()
            status['analyzer'] = f"Analyzer has {analyzer_json['num_reviews']} NR and {analyzer_json['num_ratings']} NR events"
        else:
            status['analyzer'] = "Unavailable"
    except (TimeoutError, ConnectionError):
        status['analyzer'] = "Unavailable"

    with open(STATUS_FILE, 'w') as f:
        json.dump(status, f)

def get_status():
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, 'r') as f:
            status = json.load(f)
        return status, 200
    else:
        return {"message": "json file not found"}, 404
    

def get_event_stats():
    client = KafkaClient(hosts=f"{app_config['events']['hostname']}:{app_config['events']['port']}")
    topic = client.topics[str.encode(app_config['events']['topic'])]
    consumer = topic.get_simple_consumer(reset_offset_on_start=True, consumer_timeout_ms=1000)
    num_reviews, num_ratings = 0, 0
    try:
        for msg in consumer:
            msg_str = msg.value.decode('utf-8')
            event = json.loads(msg_str)
            if event['type'] == 'get_all_reviews':
                num_reviews += 1
            elif event['type'] == 'rating_game':
                num_ratings += 1
    except Exception as e:
        logger.error(f"Error retrieving event stats: {str(e)}")
        return {"message": "Error retrieving event stats"}, 404
    return {"num_reviews": num_reviews, "num_ratings": num_ratings}, 201

app = connexion.FlaskApp(__name__, specification_dir='.')
app.add_api('openapi.yaml')
app.add_middleware(
    CORSMiddleware,
    position=MiddlewarePosition.BEFORE_EXCEPTION,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def init_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_services, 'interval', seconds=10)
    scheduler.start()

if __name__ == '__main__':
    init_scheduler()
    app.run(port=8130, host='0.0.0.0')
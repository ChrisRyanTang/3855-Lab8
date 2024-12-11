import connexion
import os
import json
import requests
import yaml
import logging
import logging.config
import uuid
import time
from pykafka import KafkaClient
from datetime import datetime
from connexion import NoContent

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


def init_kafka_client():
    """
    Initialize the Kafka client and producer with retry logic.
    """
    global producer
    retries = app_config['kafka']['retries']
    retry_interval = app_config['kafka']['retry_interval']
    current_retry = 0

    while current_retry < retries:
        try:
            logger.info(f"Attempting to connect to Kafka (Retry {current_retry + 1}/{retries})...")
            client = KafkaClient(hosts=f"{app_config['events']['hostname']}:{app_config['events']['port']}")
            topic = client.topics[str.encode(app_config['events']['topic'])]
            producer = topic.get_sync_producer()
            logger.info("Kafka producer initialized successfully.")
            return
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {e}. Retrying in {retry_interval} seconds...")
            current_retry += 1
            time.sleep(retry_interval)

    logger.error("Exceeded maximum retries for connecting to Kafka.")
    raise ConnectionError("Unable to establish Kafka connection after retries.")

producer = init_kafka_client() 

def produce_event(event):
    """
    Produce an event to the Kafka topic.
    """
    global producer
    try:
        producer.produce(event.encode('utf-8'))
        logger.info("Event produced successfully.")
    except Exception as e:
        logger.error(f"Failed to produce event: {e}. Reinitializing Kafka producer...")
        init_kafka_client()
        producer.produce(event.encode('utf-8'))

def produce_event_with_type(event_type, reading):
    """
    Compose and produce an event with its type and payload.
    """
    try:
        msg = {
            'type': event_type,
            'datetime': datetime.now().strftime('%Y-%m-%dT:%H:%M:%S'),
            'payload': reading
        }
        msg_str = json.dumps(msg)
        produce_event(msg_str)
        logger.info(f"Produced event {event_type} to Kafka with trace_id: {reading['trace_id']}")
        return NoContent, 201
    except Exception as e:
        logger.error(f"Failed to produce event {event_type}: {str(e)}")
        raise

def get_all_reviews(body):
    trace_id = str(uuid.uuid4())
    body['trace_id'] = trace_id
    logger.info(f"get_all_reviews event with body: {body} ")
    return produce_event_with_type("get_all_reviews", body)

def rating_game(body):
    trace_id = str(uuid.uuid4())
    body['trace_id'] = trace_id
    logger.info(f"rating_game event with body: {body} ")
    return produce_event_with_type("rating_game", body)

def get_check():
    logger.info(f"Health check")
    return NoContent, 200

app = connexion.FlaskApp(__name__, specification_dir='')
app.add_api('openapi.yaml', strict_validation=True, validate_responses=True)

if __name__ == '__main__':
    app.run(port=8080, host='0.0.0.0')

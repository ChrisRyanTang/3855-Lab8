import connexion
import os
import json
import requests
import yaml
import logging
import logging.config
import uuid
from pykafka import KafkaClient
from datetime import datetime
from connexion import NoContent


with open('app_conf.yml', 'r') as f:
    app_config = yaml.safe_load(f)


with open('log_conf.yml', 'r') as f:
    log_config = yaml.safe_load(f.read())
    logging.config.dictConfig(log_config)
    
logger = logging.getLogger('basicLogger')


def producer(event_type, reading):
    client = KafkaClient(hosts=f"{app_config['events']['hostname']}:{app_config['events']['port']}")
    topic = client.topics[str.encode(app_config['events']['topic'])]
    producer = topic.get_sync_producer()

    msg = {
        'type': event_type,
        'datetime': datetime.now().strftime('%Y-%m-%dT:%H:%M:%S'),
        'payload': reading
    }
    msg_str = json.dumps(msg)
    producer.produce(msg_str.encode('utf-8'))
    logger.info(f"Produced event get_all_reviews to Kafka with trace_id: {reading['trace_id']}")
    
    return NoContent, 201

def get_all_reviews(body):
    trace_id = str(uuid.uuid4())
    body['trace_id'] = trace_id
    logger.info(f"get_all_reviews event with body: {body} ")
    
    producer("get_all_reviews", body)

    return NoContent, 201


def rating_game(body):
    trace_id = str(uuid.uuid4())
    body['trace_id'] = trace_id
    logger.info(f"rating_game event with body: {body} ")
    
    producer("rating_game", body)

    return NoContent, 201


app = connexion.FlaskApp(__name__, specification_dir='')
app.add_api('openapi.yaml', strict_validation=True, validate_responses=True)

if __name__ == '__main__':
    app.run(port=8080)


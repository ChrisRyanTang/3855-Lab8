import connexion
import json
import yaml
import logging.config
from connexion.middleware import MiddlewarePosition
from starlette.middleware.cors import CORSMiddleware
from pykafka import KafkaClient
from pykafka.common import OffsetType


with open('app_conf.yml', 'r') as f:
    app_config = yaml.safe_load(f)

with open('log_conf.yml', 'r') as f:
    log_config = yaml.safe_load(f.read())
    logging.config.dictConfig(log_config)

logger = logging.getLogger('basicLogger')

logger = logging.getLogger('basicLogger')
hostname = f"{app_config['events']['hostname']}:{app_config['events']['port']}"

# Kafka setup
client = KafkaClient(hosts=hostname)
topic = client.topics[str.encode(app_config["events"]["topic"])]


def get_kafka_consumer():
    client = KafkaClient(hosts=f"{app_config['events']['hostname']}:{app_config['events']['port']}")
    topic = client.topics[str.encode(app_config['events']['topic'])]
    consumer = topic.get_simple_consumer(
        reset_offset_on_start=False,
        consumer_timeout_ms=1000,
        auto_offset_reset=OffsetType.LATEST
    )
    return consumer



def get_all_reviews_readings(index):
    consumer = topic.get_simple_consumer(reset_offset_on_start=True, consumer_timeout_ms=1000)
    count = 0

    try:
        for msg in consumer:
            msg_str = msg.value.decode('utf-8')
            event = json.loads(msg_str)
            if event['type'] == 'get_all_reviews':
                if count == index:
                    logger.info(f"Returning get_all_reviews at index {index}")
                    return event['payload'], 200
                count += 1
    except Exception as e:
        logger.error(f"Error retrieving get_all_reviews at index {index}: {str(e)}")
    return {"message": "Not Found"}, 404

def rating_game_readings(index):
    consumer = topic.get_simple_consumer(reset_offset_on_start=True, consumer_timeout_ms=1000)
    count = 0
    try:
        for msg in consumer:
            msg_str = msg.value.decode('utf-8')
            event = json.loads(msg_str)
            if event['type'] == 'rating_game':
                if count == index:
                    logger.info(f"Returning rating_game at index {index}")
                    return event['payload'], 200
                count += 1
    except Exception as e:
        logger.error(f"Error retrieving rating_game at index {index}: {str(e)}")
        return {"message": "Not Found"}, 404


def get_event_stats():
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

if __name__ == '__main__':
    app.run(port=8110, host='0.0.0.0')

    app.add_middleware(
        CORSMiddleware,
        position=MiddlewarePosition.BEFORE_EXCEPTION,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

import connexion
import yaml
import logging
import logging.config
import json
from threading import Thread
from kafka import KafkaProducer
from pykafka import KafkaClient
from pykafka.common import OffsetType
from sqlalchemy.sql import and_
from datetime import datetime
from connexion import NoContent
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from base import Base
from get_all_reviews import Review
from rating_game import Rating


with open('app_conf.yml', 'r') as f:
    app_config = yaml.safe_load(f.read())

with open('log_conf.yml', 'r') as f:
    log_config = yaml.safe_load(f.read())
    logging.config.dictConfig(log_config)

logger = logging.getLogger('basicLogger')


DB_ENGINE = create_engine(
    f"mysql+pymysql://{app_config['datastore']['user']}:{app_config['datastore']['password']}@{app_config['datastore']['hostname']}:{app_config['datastore']['port']}/{app_config['datastore']['db']}"
)
Base.metadata.bind = DB_ENGINE
DB_SESSION = sessionmaker(bind=DB_ENGINE)
Base.metadata.create_all(DB_ENGINE)


producer = KafkaProducer(
    bootstrap_servers=[f"{app_config['events']['hostname']}:{app_config['events']['port']}"],
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

def send_kafka_message(topic, message):
    producer.send(topic, value=message)
    producer.flush()
    logger.info(f"Message sent to Kafka topic {topic}: {message}")


def process_messages():
    client = KafkaClient(hosts=f"{app_config['events']['hostname']}:{app_config['events']['port']}")
    topic = client.topics[str.encode(app_config['events']['topic'])]
    consumer = topic.get_simple_consumer(
        consumer_group=b'event_group',
        reset_offset_on_start=False,
        auto_offset_reset=OffsetType.LATEST
    )

    for msg in consumer:
        if msg is not None:
            msg_str = msg.value.decode('utf-8')
            msg = json.loads(msg_str)
            logger.info(f"Message: %s" % msg)

            payload = msg["payload"]

            if msg["type"] == "get_all_reviews":
                session = DB_SESSION()
                gr = Review(
                    steam_id = payload['steam_id'],
                    username = payload['username'],
                    review = payload['review'],
                    rating = payload['rating'],
                    game_id = payload['game_id'],
                    trace_id = payload['trace_id']
                )
                session.add(gr)
                session.commit()
                session.close()
                logger.info(f"Stored review: {payload['review']}")

            elif msg["type"] == "rating_game":
                rg = Rating(
                    game_id = payload['game_id'],
                    game_name = payload['game_name'],
                    rating = payload['rating'],
                    num_reviews = payload['num_reviews'],
                    trace_id = payload['trace_id']
                )
                session.add(rg)
                session.commit()
                session.close()
                logger.info(f"Stored rating: {payload['rating']}")

            consumer.commit_offsets()

def get_all_reviews_readings(start_timestamp, end_timestamp):
    session = DB_SESSION()
    reviews_list = []

    try:
        start_time = datetime.strptime(start_timestamp, "%Y-%m-%dT:%H:%M:%S")
        end_time = datetime.strptime(end_timestamp, "%Y-%m-%dT:%H:%M:%S")


        results = session.query(Review).filter(
            and_(Review.date_created >= start_time,
            Review.date_created < end_time)
        ).all()

        logger.info(f"Returned {len(reviews_list)} reviews between {start_timestamp} and {end_timestamp}")

        for reading in results:
            reviews_list.append(reading.to_dict())

        session.close()

    except Exception as e:
        logger.error(e)

    logger.info(f"Returned {len(reviews_list)} reviews between {start_timestamp} and {end_timestamp}")
    return reviews_list, 200

def rating_game_readings(start_timestamp, end_timestamp):
    session = DB_SESSION()
    ratings_list = []

    try:
        start_time = datetime.strptime(start_timestamp, "%Y-%m-%dT:%H:%M:%S")
        end_time = datetime.strptime(end_timestamp, "%Y-%m-%dT:%H:%M:%S")
    except ValueError as e:
        logger.error(f"Invalid timestamp format: {e}")
        return {"message": "Invalid timestamp format"}, 400

    results = session.query(Rating).filter(
        and_(Rating.date_created >= start_time,
        Rating.date_created < end_time)
    ).all()


    for reading in results:
        ratings_list.append(reading.to_dict())

    session.close()

    logger.info(f"Returned {len(ratings_list)} ratings between {start_timestamp} and {end_timestamp}")
    return ratings_list, 200


app = connexion.FlaskApp(__name__, specification_dir='')
app.add_api('openapi.yaml', strict_validation=True, validate_responses=True)

if __name__ == '__main__':
    t1 = Thread(target=process_messages)
    t1.setDaemon(True)
    t1.start()
<<<<<<< HEAD
    app.run(port=8090, host='0.0.0.0')

=======
    app.run(port=8090, host='0.0.0.0')
>>>>>>> f970313b061d5ee186037d8117883270e7188cd8

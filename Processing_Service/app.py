import json
import requests
import yaml
import logging
import logging.config
import connexion
import os
from connexion.middleware import MiddlewarePosition
from starlette.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
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

def populate_stats():
    logger.info('Starting periodic processing')

    try:
        with open(app_config['datastore']['filename'], 'r') as f:
            stats = json.load(f)
    except FileNotFoundError:
        logger.warning('Datastore file not found. Initializing new stats.')
        stats = {
            'num_reviews': 0,
            'num_ratings': 0,
            'thumbs_up_count': 0,
            'thumbs_down_count': 0,
            'last_updated': datetime.now().strftime('%Y-%m-%dT:%H:%M:%S')
        }

    last_updated = stats['last_updated']
    current_time = datetime.now().strftime('%Y-%m-%dT:%H:%M:%S')

    review_url = f"{app_config['eventstore1']['url']}?start_timestamp={last_updated}&end_timestamp={current_time}"
    rating_url = f"{app_config['eventstore2']['url']}?start_timestamp={last_updated}&end_timestamp={current_time}"

    logger.debug(f'Review URL: {review_url}')
    logger.debug(f'Rating URL: {rating_url}')

    reviews_response = requests.get(review_url)
    ratings_response = requests.get(rating_url)

    if reviews_response.status_code == 200:
        try:
            reviews = reviews_response.json()
            valid_reviews = []
            for review in reviews:
                try:
                    review['game_id'] = int(review['game_id'])
                    valid_reviews.append(review)
                except ValueError:
                    logger.error(f"Invalid game_id for review: {review}")

            stats['num_reviews'] += len(valid_reviews)
            stats['thumbs_up_count'] += sum(1 for r in valid_reviews if r['rating'] == 'thumbs up')
            stats['thumbs_down_count'] += sum(1 for r in valid_reviews if r['rating'] == 'thumbs down')
            logger.info(f'Received {len(valid_reviews)} valid reviews')
        except Exception as e:
            logger.error(f'Error processing reviews: {str(e)}')
    else:
        logger.error(f'Failed to fetch reviews: {reviews_response.status_code}')

    if ratings_response.status_code == 200:
        ratings = ratings_response.json()
        stats['num_ratings'] += len(ratings)
        logger.info(f'Received {len(ratings)} new ratings')
    else:
        logger.error(f'Failed to fetch ratings: {ratings_response.status_code}')

    stats['last_updated'] = current_time
    logger.info(f'Stats: {stats}')

    try:
        with open(app_config['datastore']['filename'], 'w') as f:
            json.dump(stats, f, indent=4)
        logger.info('Stats successfully updated')
    except Exception as e:
        logger.error(f'Failed to update stats: {str(e)}')

    logger.debug(f'Updated stats: {stats}')
    logger.info('Finished periodic processing')


def get_stats():
    logger.info('Grabbing the stats')

    try:
        with open(app_config['datastore']['filename'], 'r') as f:
            stats = json.load(f)
    except FileNotFoundError:
        logger.error('Statistics do not exist')
        return {'message': 'Stats error ouch'}, 404

    logger.debug(f'Returning stats: {stats}')
    return stats, 200

def init_scheduler():
    sched = BackgroundScheduler(daemon=True)
    sched.add_job(populate_stats, 'interval', seconds=app_config['scheduler']['period_sec'])
    sched.start()

app = connexion.FlaskApp(__name__, specification_dir='')
app.add_api('openapi.yaml', strict_validation=True, validate_responses=True)
app.add_middleware(
    CORSMiddleware,
    position=MiddlewarePosition.BEFORE_EXCEPTION,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == '__main__':
    init_scheduler()
    app.run(port=8100, host='0.0.0.0')




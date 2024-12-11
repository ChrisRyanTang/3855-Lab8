import requests
import logging.config
import yaml
from connexion.middleware import MiddlewarePosition
from starlette.middleware.cors import CORSMiddleware
from pykafka import KafkaClient
from pykafka.common import OffsetType
from requests.exceptions import Timeout, ConnectionError

# Load application configuration
with open('app_conf.yml', 'r') as f:
    app_config = yaml.safe_load(f.read())

# Load logging configuration
with open('log_conf.yml', 'r') as f:
    log_config = yaml.safe_load(f.read())
    logging.config.dictConfig(log_config)

RECEIVER_URL = app_config['Receiver']['hostname']['port']
STORAGE_URL = app_config['Storage']['hostname']['port']
PROCESSING_URL = app_config['Processing']['hostname']['port']
ANALYZER_URL = app_config['Analyzer']['hostname']['port']
TIMEOUT = app_config['timeout'] # Set to 2 seconds in your config file



def check_services():
    """ Called periodically """
    receiver_status = "Unavailable"
    try:
        response = requests.get(RECEIVER_URL, timeout=TIMEOUT)
        if response.status_code == 200:
            receiver_status = "Healthy"
            logger.info("Receiver is Healthly")
        else:
            logger.info("Receiver returning non-200 response")
    except (Timeout, ConnectionError):
        logger.info("Receiver is Not Available")

    storage_status = "Unavailable"
    try:
        response = requests.get(STORAGE_URL, timeout=TIMEOUT)
        if response.status_code == 200:
            storage_json = response.json()
            storage_status = f"Storage has {storage_json['num_bp']} BP and {storage_json['num_hr']} HR events"
            logger.info("Storage is Healthy")
        else:
            logger.info("Storage returning non-200 response")
    except (Timeout, ConnectionError):
        logger.info("Storage is Not Available")
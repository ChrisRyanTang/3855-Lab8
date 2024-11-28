import connexion
import json
import yaml
import logging.config
from connexion.middleware import MiddlewarePosition
from starlette.middleware.cors import CORSMiddleware
from pykafka import KafkaClient
from pykafka.common import OffsetType
from datetime import datetime

# Load configurations
with open('app_conf.yml', 'r') as f:
    app_config = yaml.safe_load(f)

with open('log_conf.yml', 'r') as f:
    log_config = yaml.safe_load(f.read())
    logging.config.dictConfig(log_config)

logger = logging.getLogger('basicLogger')

# Kafka setup
hostname = f"{app_config['events']['hostname']}:{app_config['events']['port']}"
client = KafkaClient(hosts=hostname)
topic = client.topics[str.encode(app_config["events"]["topic"])]

# JSON data store
DATA_STORE = app_config['datastore']['filepath']

def get_kafka_consumer():
    """Initialize Kafka consumer."""
    consumer = topic.get_simple_consumer(
        reset_offset_on_start=False,
        consumer_timeout_ms=1000,
        auto_offset_reset=OffsetType.LATEST
    )
    return consumer

def save_anomaly(anomaly):
    """Save detected anomaly to JSON data store."""
    try:
        with open(DATA_STORE, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = []

    data.append(anomaly)

    with open(DATA_STORE, 'w') as f:
        json.dump(data, f, indent=4)

    logger.info(f"Anomaly saved: {anomaly}")

def process_event(event):
    """Process incoming Kafka event and detect anomalies."""
    event_type = event.get('type')
    payload = event.get('payload')
    trace_id = event.get('trace_id')

    logger.info(f"Received event: {event}")

    thresholds = app_config['thresholds'].get(event_type)
    if not thresholds:
        logger.warning(f"No thresholds configured for event type: {event_type}")
        return

    value = payload.get('value')
    anomaly = None

    if value > thresholds['max']:
        anomaly = {
            "event_type": event_type,
            "trace_id": trace_id,
            "anomaly_type": "Too High",
            "description": f"Value {value} exceeds max threshold {thresholds['max']}",
            "timestamp": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
        }
    elif value < thresholds['min']:
        anomaly = {
            "event_type": event_type,
            "trace_id": trace_id,
            "anomaly_type": "Too Low",
            "description": f"Value {value} below min threshold {thresholds['min']}",
            "timestamp": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
        }

    if anomaly:
        logger.info(f"Anomaly detected: {anomaly}")
        save_anomaly(anomaly)

def consume_kafka_events():
    """Background thread to consume Kafka events."""
    consumer = get_kafka_consumer()
    for msg in consumer:
        if msg is not None:
            msg_str = msg.value.decode('utf-8')
            event = json.loads(msg_str)
            process_event(event)

# REST API endpoints
def get_anomalies(event_type):
    """Retrieve anomalies by type."""
    try:
        with open(DATA_STORE, 'r') as f:
            anomalies = json.load(f)
    except FileNotFoundError:
        anomalies = []

    filtered_anomalies = [a for a in anomalies if a['event_type'] == event_type]
    return filtered_anomalies, 200

# Set up FlaskApp and routes
app = connexion.FlaskApp(__name__, specification_dir='.')
app.add_api('openapi.yaml')
app.add_middleware(
    CORSMiddleware,
    position=MiddlewarePosition.BEFORE_EXCEPTION,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

if __name__ == '__main__':
    from threading import Thread

    # Start Kafka consumer in a separate thread
    kafka_thread = Thread(target=consume_kafka_events)
    kafka_thread.daemon = True
    kafka_thread.start()

    app.run(port=8120, host='0.0.0.0')

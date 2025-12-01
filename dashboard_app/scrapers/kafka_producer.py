from kafka import KafkaProducer, errors as kafka_errors
import json
import logging
import time
from kafka.errors import NoBrokersAvailable

logger = logging.getLogger(__name__)

class KafkaProducer_Simple:
    def __init__(self, bootstrap_servers='kafka:9092', topic='cross_ref_tasks', run_by_default=False):
        self.topic = topic
        if run_by_default:
            for attempt in range(10):
                try:
                    self.producer = KafkaProducer(
                        bootstrap_servers=bootstrap_servers,
                        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                        retries=5
                    )
                    print("Connected to Kafka!")
                    break
                except NoBrokersAvailable:
                    print("Waiting for Kafka to become available...")
                    time.sleep(5)
            else:
                raise Exception(" Failed to connect to Kafka after several attempts.")
        else:
            return
                
    def send_message(self, data: dict):
        try:
            logger.info (f"Sending message to topic :{self.topic} -> {data}")
            self.producer.send(self.topic, value=data)
            self.producer.flush()
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            
class KafkaProducer_WithBackOff:
    def __init__(self, bootstrap_servers='kafka:9092', topic='cross_ref_tasks', run_by_default=True):

        self.topic = topic
        if run_by_default:
            for attempt in range(10):
                try:
                    self.producer = KafkaProducer(
                        bootstrap_servers=bootstrap_servers,
                        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                        acks='all',
                        linger_ms=10,
                        max_in_flight_requests_per_connection=1,
                        retries=0
                    )
                    print("Connected to Kafka!")
                    break
                except NoBrokersAvailable:
                    print("Waiting for Kafka to become available...")
                    time.sleep(5)
            else:
                raise Exception(" Failed to connect to Kafka after several attempts.")
        else:
            return
       
        
    def send_message(self, topic:str, data:dict, max_retries=5):
        attempts = 0
        while attempts <= max_retries:
            try:
                # Send asynchronously but wait for the result to confirm delivery
                future = self.producer.send(topic, data)
                result = future.get(timeout=10)

                print(f"Message delivered to {topic} "
                    f"(partition {result.partition}, offset {result.offset})")
                
                # Reset backoff if it succeeds
                return True
            
            except (kafka_errors.KafkaTimeoutError,
                kafka_errors.NoBrokersAvailable,
                kafka_errors.KafkaError) as e:
            
                attempts += 1

                # Dynamic (exponential) backoff: 1s, 2s, 4s, 8s... up to max 60s
                backoff_time = min(2 ** attempts, 60)
                print(f"Error sending message (attempt {attempts}/{max_retries}): {e}")
                print(f"Retrying in {backoff_time:.2f} seconds...")
                
                time.sleep(backoff_time)

        print(f"Failed to deliver message after {max_retries} retries.")
        return False
    
    def close(self):
        """Flushes and safely closes the producer."""
        try:
            self.producer.flush()
            self.producer.close()
            logger.info("Kafka producer closed successfully.")
        except Exception as e:
            logger.warning(f"Error closing Kafka producer: {e}")

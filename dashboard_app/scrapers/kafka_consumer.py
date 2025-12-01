from kafka import KafkaConsumer
import asyncio
import json
import logging
import time
from dashboard_app.scrapers.cross_ref_scraper import CrossRefScraper
from dashboard_app.scrapers.kafka_producer import KafkaProducer_WithBackOff

import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard.settings")  # Adjust if your settings module is named differently
django.setup()


from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from asgiref.sync import sync_to_async
import httpx

logger = logging.getLogger(__name__)

class CrossRefKafkaWorker:
    def __init__(self, bootstrap_servers='kafka:9092', consume_topic='crossref_tasks', produce_topic='crossref_tasks'):
        self.consumer = KafkaConsumer(
            consume_topic,
            bootstrap_servers=bootstrap_servers,
            value_deserializer=lambda v: json.loads(v.decode('utf-8')),
            group_id='crossref_worker',
            auto_offset_reset='earliest'
        )
        self.scraper = CrossRefScraper()
        self.producer = KafkaProducer_WithBackOff()
        self.produce_topic = produce_topic

    def consume_and_scrape(self, max_depth=2, current_depth=0, polite_delay=1.0):
        logger.info(f"[CONSUMER] Started listening on Kafka topic '{self.consumer.subscription()}'")

        for message in self.consumer:
            try:
                data = message.value
                title = data.get("title")
                current_depth = data.get("depth", 0)

                if not title:
                    logger.warning("[CONSUMER] Skipping message with missing title.")
                    continue

                logger.info(f"[CONSUMER] Depth {current_depth} | Processing: {title}")
                metadata = self.scraper.fetch(title)

                if not metadata:
                    logger.warning(f"[CONSUMER] No metadata found for '{title}'")
                    continue

                # Save main paper
                paper_dict = self.scraper.build_paper_dict(
                    self.scraper.get_title(metadata, from_metadata=False),
                    metadata.get("DOI"),
                    metadata.get("created", {}).get("date-parts", [[None]])[0][0],
                    metadata.get("abstract"),
                    self.scraper.get_authors(metadata),
                    metadata.get("is-referenced-by-count", 0),
                    metadata.get("URL"),
                    self.scraper.get_paper_type(metadata),
                )
                self.scraper.save_to_db(paper_dict)

                # Retrieve referenced papers and produce new Kafka tasks
                new_titles = self.scraper.RetrieveNewPapers(metadata)
                if new_titles:
                    logger.info(f"[CONSUMER] Found {len(new_titles)} new references for '{title}'")

                    if max_depth == -1 or current_depth < max_depth:
                        for t in new_titles:
                            self.producer.send_message(
                                self.produce_topic,
                                {"title": t, "depth": current_depth + 1}
                            )
                            # polite delay to respect Crossref’s rate limits
                            time.sleep(polite_delay)
                    else:
                        logger.info(f"[CONSUMER] Max depth reached for '{title}'")
                else:
                    logger.info(f"[CONSUMER] No references found for '{title}'")
                time.sleep(2)

            except Exception as e:
                logger.error(f"[CONSUMER] Error processing message: {e}", exc_info=True)
                time.sleep(3)  # backoff to avoid crash loops
                
class CrossRefKafkaWorkerAsync:
    def __init__(self, bootstrap_servers='kafka:9092', consume_topic='crossref_tasks', produce_topic='crossref_tasks'):
        self.bootstrap_servers = bootstrap_servers
        self.consume_topic = consume_topic
        self.produce_topic = produce_topic
        self.scraper = CrossRefScraper()
        self.concurency_limit = 5

    async def start(self, max_depth=2, polite_delay=2):
        """Start consuming and processing Kafka messages asynchronously."""
        consumer = AIOKafkaConsumer(
            self.consume_topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id='crossref_worker',
            value_deserializer=lambda v: json.loads(v.decode('utf-8')),
            auto_offset_reset='earliest'
        )
        producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

        await consumer.start()
        await producer.start()
        
        self.semaphore = asyncio.Semaphore(self.concurency_limit)
        self.client = httpx.AsyncClient(timeout=30.0)

        
        logger.info(f"[ASYNC CONSUMER] Listening on topic '{self.consume_topic}'")

        try:
            async for message in consumer:
                # limit concurrency
                await self.semaphore.acquire()
                asyncio.create_task(self.handle_message(message, producer, max_depth, polite_delay))
       
        except Exception as e:
            logger.error(f"[ASYNC CONSUMER] Error: {e}", exc_info=True)
            
        finally:
            await consumer.stop()
            await producer.stop()
            await self.client.aclose()

    async def handle_message(self, message, producer, max_depth=3, polite_delay=2):
        """Handle a single Kafka message asynchronously."""
        try:
            data = message.value
            title = data.get("title")
            depth = data.get("depth", 0)

            if not title:
                logger.warning("[CONSUMER] Skipping message with missing title.")
                return

            logger.info(f"[ASYNC CONSUMER] Depth {depth} | Processing: {title}")

            # --- Async scraping ---
            # async with self.scraper_lock():
            #     async with self.scraper_client() as client:
            metadata = await self.scraper.fetch_async(self.client, title)

            if not metadata:
                logger.warning(f"[ASYNC CONSUMER] No metadata found for '{title}'")
                return

            # --- Save to DB (sync but safe) ---
            paper_dict = self.scraper.build_paper_dict(
                self.scraper.get_title(metadata, from_metadata=False),
                metadata.get("DOI"),
                metadata.get("created", {}).get("date-parts", [[None]])[0][0],
                metadata.get("abstract"),
                metadata.get("is-referenced-by-count", 0),
                metadata.get("URL"),
                self.scraper.get_paper_type(metadata),
            )
            author_dict = await sync_to_async(self.scraper.build_author_dict)(
                self.scraper.get_authors(metadata))
            
            topics_dict = await sync_to_async(self.scraper.build_keyword_dict)(metadata.get("abstract"))
            await self.scraper.save_to_db(paper_dict, author_dict, topics_dict)

            # --- Queue referenced papers ---
            new_titles = self.scraper.RetrieveNewPapers(metadata)
            if new_titles:
                logger.info(f"[ASYNC CONSUMER] Found {len(new_titles)} new references for '{title}'")
                if max_depth == -1 or depth < max_depth:
                    for t in new_titles:
                        await producer.send_and_wait(
                            self.produce_topic,
                            {"title": t, "depth": depth + 1}
                        )
                        await asyncio.sleep(polite_delay)
                else:
                    logger.info(f"[ASYNC CONSUMER] Max depth reached for '{title}'")
            else:
                logger.info(f"[ASYNC CONSUMER] No references found for '{title}'")

        except Exception as e:
            logger.error(f"[ASYNC CONSUMER] Error processing message: {e}", exc_info=True)
            await asyncio.sleep(2)
            
        finally:
            self.semaphore.release()

    # --- Optional helper context managers ---
    def scraper_client(self):
        """Helper context for httpx.AsyncClient reuse."""
        import httpx
        return httpx.AsyncClient(timeout=30.0)

    def scraper_lock(self):
        """Ensure concurrency control when needed."""
        return asyncio.Semaphore(5)
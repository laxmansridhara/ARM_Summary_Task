import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard.settings")
django.setup()

from kafka import KafkaProducer, KafkaConsumer
import selenium
import habanero
import csv
import asyncio
from dashboard_app.models import Papers, Authors, Author_Papers
from dashboard_app.scrapers import cross_ref_scraper,kafka_consumer,kafka_producer, utils



def run_scraper(seeds_csv="seeds.csv", max_depth=3, run_indefinitely=False):
    print("Let's Scrape. \nGenerating Seeds......")
    starting_papers = utils.Generate_Seeds(seeds_csv)
    if not starting_papers:
        print(" The CSV either does not exist or is empty.")
        return -1

    print(" Seeds Generated. Sending to Kafka...")
    kafka_prod = kafka_producer.KafkaProducer_WithBackOff()
    for query in starting_papers:
        kafka_prod.send_message("crossref_tasks", {"title": query})
    kafka_prod.close()

    print("All seed titles sent. Starting consumer loop.")
    kafka_cons = kafka_consumer.CrossRefKafkaWorkerAsync()
    depth = -1 if run_indefinitely else max_depth
    asyncio.run(kafka_cons.start(max_depth=depth))
    return 0


def CheckingForErrors(value: int):
    print("=" * 80)
    if value == 0:
        print("Everything went fine!")
    elif value == -1:
        print("The CSV either does not exist or is empty.")
    print(f"Finished run_scraper() with code: {value}")
    
if __name__ == "__main__":
    run_scraper(max_depth=3)

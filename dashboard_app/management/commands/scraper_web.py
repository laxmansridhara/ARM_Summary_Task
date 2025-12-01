from django.core.management.base import BaseCommand
from dashboard_app.scrapers.kafka_producer import send_scrape_job
import csv

class Command(BaseCommand):
    help = "Dispatches scraping jobs from a CSV file."

    def add_arguments(self, parser):
        parser.add_argument("--csv", type=str, help="Path to CSV with seed queries")

    def handle(self, *args, **options):
        csv_path = options["csv"]
        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                query = row[0]
                send_scrape_job(query)
                self.stdout.write(self.style.SUCCESS(f"Queued job for: {query}"))

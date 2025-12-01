import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard.settings")  # Adjust if your settings module is named differently
django.setup()

from asgiref.sync import sync_to_async
from dashboard_app.scrapers import utils
import logging
from dashboard_app.scrapers.base_scraper import BaseScraper
from dashboard_app.models import Papers, Authors, Author_Papers
from dashboard_app.const import PaperTypes, Config
import tqdm
from django.db import IntegrityError, transaction
import asyncio
import httpx
import requests
import json
import time
import random
from pyalex import Works

logger = logging.getLogger(__name__)

os.environ["OPENALEX_EMAIL"] = "dashboardarm@gmail.com"

class OpenAlexScraper(BaseScraper):
    #---------------General Helper functions----------------------#
    def get_title(metadata):
        try:
            return metadata.get("title")
        except Exception as e:
            print(e)
            
    def get_other_titles_by_OA_id(metadta):
        try:
            references =  metadta.get("referenced_works")
            if references:
                return references
            else:
                raise ValueError("Empty References")
        except Exception() as e:
            print(e)
            
    def get_citations(metadata):
            citations = metadata.get("cited_by_count") if metadata.get("cited_by_count") else 0
            
    #--------------- Function for returning author data, results coma as tuples of (name, orcid)-----------------#
    def get_authors(metadata):
        try:
            preproceesed_authors = metadata.get("authorships")
            results = []
            for author in preproceesed_authors:
                author_data = author.get("author")
                author_name = author_data.get("display_name")
                author_orcid = author_data.get("orcid") if author_data.get("orcid") else ""
                results.append((author,author_orcid))
            return results
                
        except Exception as e:
            print(e)
            return -1

    def get_paper_type(metadata):
        try:
            return metadata.get("type")
        except Exception as e:
            print(e)
            
    def get_topics(metadata):
        try:
            preprocesed_topics = metadata.get("primary_topic")         
            main_topic = preprocesed_topics.get("display_name")   
            domain = preprocesed_topics.get("domain").get("display_name")
            field = preprocesed_topics.get("field").get("display_name")
            subfield = preprocesed_topics.get("subfield").get("display_name")
            return [main_topic, domain, field, subfield]
        except Exception as e:
            print(e)
            
    def get_doi(metadata):
        return metadata.get("doi")[len(Config.DOI_PREFIX) - 1:]
    
    def test_metadata(title, doi, date, abstract, authors, citation, link, paper_type, topics):
        if not title:
            print(ValueError("Missing Title"))
            return -1
        
        if not doi:
            print(ValueError("Missing DOI"))
            return -2
        
        if not date:
            print(ValueError("Missing Date"))
            return -3
        
        if not abstract:
            print(ValueError("Missing Abstract"))
            return -4
        
        if not authors:
            print(ValueError("Missing Authors"))
            return -5
        
        if citation < 0:
            print(ValueError("Missing Citations"))
            return -6
        
        if not link:
            print(ValueError("Missing Link"))
            return -7
        
        if not paper_type:
            print(ValueError("Missing Paper_Type"))
            return -8
        
        if not topics:
            print(ValueError("Missing topics"))
            return -9
        
        return 0
    
    #----------------Async Core Scraper---------------------------#
    class AsyncOpenAlexScraper():
        def __init__(self):
            pass
        
    #----------------Sync CORE Scraper----------------------------#
    class SyncOpenAlexScraper():
        def __init__(self):
            pass
    
        
def main():
    # Initialize a sync scraper for testing purproses
    #scraper = OpenAlexScraper.SyncOpenAlexScraper()
    
    #Create the seeds
    input_csv = "seeds.csv"
    seeds = utils.Generate_Seeds(input_csv)
    test = seeds[random.randint(0, len(seeds))]
    output_dir = os.path.abspath(os.path.dirname(__file__))  # current directory of this script
    project_root = os.path.abspath(os.path.join(output_dir, "../../"))
    try:
        print(f"🔍 Searching OpenAlex for: {test}")
        results = Works().search(test).get()

        if not results:
            print("No matching papers found.")
        else:
            work_summary = results[0]
            work_id = work_summary['id']  # e.g. https://openalex.org/W4214014307

            # Fetch the FULL record
            work = Works().get(work_id)

            safe_title = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in test)
            filename = f"OpenAlex_Scraper_{safe_title[:100]}_.json"
            filepath = os.path.join(project_root, filename)

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(work, f, indent=2, ensure_ascii=False)

            print(f"💾 Saved full metadata to: {filepath}")
            print(f"📈 Citations: {work.get('cited_by_count', 'N/A')}")

    except Exception as e:
        print(f"Error fetching paper '{test}': {e}")


if __name__ == "__main__":
    main()
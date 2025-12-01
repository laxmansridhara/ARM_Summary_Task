import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard.settings")  # Adjust if your settings module is named differently
django.setup()

from habanero import Crossref
from asgiref.sync import sync_to_async
from dashboard_app.scrapers import utils
import logging
from dashboard_app.Keyword_extraction import KeywordExtractor
from dashboard_app.const import Config
from dashboard_app.scrapers.base_scraper import BaseScraper
from dashboard_app.models import Papers, Authors, Keywords, Keywords_Paper, Author_Papers
from dashboard_app.const import PaperTypes
from django.db.models import F, Func, Max, Value
from django.db.models.functions import Cast, Substr
from django.db import models
import tqdm
from django.db import IntegrityError, transaction
import asyncio
import httpx
import requests
import json
import time
import random

CROSSREF_API = "https://api.crossref.org/works/"
cr = Crossref(mailto="dashboardarm@gmail.com")

def GetTitle(reference, from_metadata=True) ->str:
    if from_metadata:
        if  reference.get("article-title"):
            return reference.get("article-title")
        elif reference.get("journal-title"):
            return  reference.get("journal-title")
        elif reference.get("volume-title"):
            return   reference.get("volume-title")
        else:
            return  "None"
    else:
        title = reference.get("title")


        return title

        
def GetAuthors(reference):
    preprocesed_authors = reference.get("author")
    post_processed_authors = []
    if preprocesed_authors:
        for author in preprocesed_authors:
            given_name = author.get("given")
            family_name = author.get("family")
            name =given_name + ' ' + family_name
            post_processed_authors.append(name)
            
    return post_processed_authors
        
def GetPaperType(reference):
    if  reference.get("article-title"):
        return PaperTypes.ARTICLE.name
    elif reference.get("journal-title"):
        return PaperTypes.JOURNAL.name
    elif reference.get("volume-title"):
        return PaperTypes.VOLUME.name
    else:
        print(ValueError("Missing Value - Unstructured"))
        return PaperTypes.UNSTRUCTURED.name

def TestMetadata(title, doi, date, abstract, authors, citation, link, paper_type):
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
    
    return 0
    
def fetch_metadata_by_title(title, cr_client):
    try:
        results = cr_client.works(query=title, limit=1)
        items = results.get("message", {}).get("items", [])
        if not items:
            print(f"[WARN] No results found for: {title}")
            return -1
        return items[0]
    except Exception as e:
        print(f"[ERROR] Failed to fetch title '{title}': {e}")
        return None
    
def BuildPaperDict(title, doi, date, abstract, authors, citation, link, paper_type):
    return {
        "title": title,
        "doi": doi,
        "published_date": date,
        "abstract": abstract,
        "citations_count": citation,
        "link": link,
        "paper_type": paper_type,
    }
    
def main():
    
    #-------------------------Generate the Seeds for scraping-----------#
    input_csv = "seeds.csv"
    titles = utils.Generate_Seeds(input_csv)
    print(f"[INFO] Loaded {len(titles)} titles from {input_csv}")
   
    results = []
    other_papers = []
    #----------------Iterate through each paper and grab the data--------#
    for idx, title in enumerate(titles):
        print("="*80)
        print(f"[{idx}/{len(titles)}] Searching metadata for: {title}")
        metadata = fetch_metadata_by_title(title, cr)
        if metadata:
            results.append(metadata)
            
            #--------------------- Paper Data----------------------------#
            paper_title = GetTitle(metadata, from_metadata=False)
            paper_doi = metadata.get("DOI")
            
            date_parts = metadata.get("created", {}).get("date-parts", [])
            paper_date = date_parts[0][0] if date_parts else None
            
            paper_abstract = metadata.get("abstract")  if metadata.get("abstract") else " "
            authors = GetAuthors(metadata) if GetAuthors(metadata) else " "
            citation = metadata.get("is-referenced-by-count") if metadata.get("is-referenced-by-count") else 0
            additional_link = metadata.get("URL")
            paper_type = GetPaperType(metadata) if GetPaperType(metadata) else "None"
            
            #--------------------- Test Retrieved Metadata --------------#
            if TestMetadata(paper_title, paper_doi, paper_date, paper_abstract, authors, citation, additional_link, paper_type) != 0:
                continue
            else:
                print(f"Metadata for paper at index {idx+1} passed the tests.\n\
                    Title: {paper_title}\n\
                    DOI: {paper_doi}\n\
                    Publishing Date: {paper_date}\n\
                    Paper_Abstract: {paper_abstract[:min(len(paper_abstract), 25)]}\n\
                    Authors: {authors}\n\
                    Citations Count: {citation}\n\
                    Additional_Link: {additional_link}\n\
                    Paper_Type: {paper_type}\n\
                    Starting getting references for paper at index {idx + 1}.")
                
                
            
            
            #--------------------Getting Other Papers Title--------------#
            references = metadata.get("reference")
            if references is not None:
                for index, reference in enumerate(references):
                    
                    #If a reference does not go under one of the 3 main branches, it means that the title comes as unstructured or flat-out is missing
                    #this seems to be prelevant in patents or questionable sources
                    retrieved_title = GetTitle(reference)
                    if (retrieved_title == None) or (retrieved_title in "Missing title at") or (retrieved_title == 'None'):
                        #print(f"\n\
                            #{retrieved_title}\
                            #\n{reference}\n")
                            continue
                    else:
                        try:
                            other_papers.append(retrieved_title)
                        except Exception as e:
                            print(e)
                            break
        else:
            print("[!] No metadata found")
        time.sleep(1.0)  # polite delay (CrossRef recommends ≤ 1 req/sec)
    for index, paper in enumerate(other_papers):
        print(f"Paper {index}: {paper}")

if __name__ == "__main__":
    main()

class CrossRefScraper(BaseScraper):
    logger = logging.getLogger(__name__)
    def __init__(self, queries=utils.Generate_Seeds("seeds.csv")):
        self.queries = queries
        self.other_papers = []
    
    #----------------------------Sync Scraping------------------------------#
    def RunScraper(self):
        for query in self.queries:
            metadata = self.fetch(query)
            if metadata:                
                #--------------------- Paper Data----------------------------#
                paper_title = self.get_title(metadata, from_metadata=False)
                paper_doi = metadata.get("DOI")
                
                date_parts = metadata.get("created", {}).get("date-parts", [])
                paper_date = date_parts[0][0] if date_parts else None
                
                paper_abstract = metadata.get("abstract")  if metadata.get("abstract") else " "
                authors = self.get_authors(metadata) if self.get_authors(metadata) else " "
                citation = metadata.get("is-referenced-by-count") if metadata.get("is-referenced-by-count") else 0
                additional_link = metadata.get("URL")
                paper_type = self.get_paper_type(metadata) if self.get_paper_type(metadata) else "None"
                
                #--------------------- Test Retrieved Metadata --------------#
                if self.test_metadata(paper_title, paper_doi, paper_date, paper_abstract, authors, citation, additional_link, paper_type) != 0:
                    continue
                else:
                    self.logger.info(f"Metadata for paper {paper_title} passed the tests.\n\
                        Title: {paper_title}\n\
                        DOI: {paper_doi}\n\
                        Publishing Date: {paper_date}\n\
                        Paper_Abstract: {paper_abstract[:min(len(paper_abstract), 25)]}\n\
                        Authors: {authors}\n\
                        Citations Count: {citation}\n\
                        Additional_Link: {additional_link}\n\
                        Paper_Type: {paper_type}\n\
                        Saving To Database")
                    paper_ref = self.build_paper_dict(paper_title, paper_doi, paper_date, paper_abstract, authors, citation, additional_link, paper_type)
                    self.save_to_db(paper_ref)
                    
                    self.logger.info(f"Starting getting references for paper {paper_title}.")
                
                #--------------------Getting Other Papers Title--------------#
                references = metadata.get("reference")
                self.other_papers=[]
                if references is not None:
                    for index, reference in enumerate(references):
                        retrieved_title = self.get_title(reference)
                        if (retrieved_title == None) or (retrieved_title in "Missing title at") or (retrieved_title == 'None'):
                            #print(f"\n\
                                #{retrieved_title}\
                                #\n{reference}\n")
                                continue
                        else:
                            try:
                                self.other_papers.append(retrieved_title)
                            except Exception as e:
                                print(e)
                                break
            else:
                self.logger.warning("[!] No metadata found")
            time.sleep(1.0)  # polite delay (CrossRef recommends ≤ 1 req/sec)
        for index, paper in enumerate(self.other_papers):
            self.logger.info(f"Paper {index}: {paper}")
    
    #-------------------Async Scraping-----------------------------------#
    async def RunScraperAsync(self, batch_size: int = 100, concurrency_limit: int = 50):
        all_titles = self.queries
        total_batches = (len(all_titles) + batch_size - 1) // batch_size
        self.logger.info(f"Starting async scraping of {len(all_titles)} titles in {total_batches} batches.")

        for i in tqdm(range(0, len(all_titles), batch_size), desc="Scraping Progress", unit="batch"):
            batch = all_titles[i:i + batch_size]
            self.logger.info(f"Processing batch {i // batch_size + 1}/{total_batches} ({len(batch)} titles).")

            # Fetch metadata asynchronously
            metadata_list = await self.fetch_all_async(batch, limit=concurrency_limit)
            buffer = []
            
            for metadata in metadata_list:
                if not metadata:
                    continue

                paper_title = self.get_title(metadata, from_metadata=False)
                paper_doi = metadata.get("DOI")
                date_parts = metadata.get("created", {}).get("date-parts", [])
                paper_date = date_parts[0][0] if date_parts else None
                paper_abstract = metadata.get("abstract") or " "
                authors = self.get_authors(metadata) or " "
                citation = metadata.get("is-referenced-by-count") or 0
                link = metadata.get("URL")
                paper_type = self.get_paper_type(metadata) or "None"

                if self.test_metadata(paper_title, paper_doi, paper_date, paper_abstract, authors, citation, link, paper_type) != 0:
                    continue

                paper_dict = self.build_paper_dict(paper_title, paper_doi, paper_date, paper_abstract, authors, citation, link, paper_type)
                buffer.append(paper_dict)
                
            if buffer:
                self.bulk_save(buffer)
                self.logger.info(f"[DB] Batch {i // batch_size + 1}: {len(buffer)} papers inserted.")

        self.logger.info("Async scraping complete.")
    #--------------------Sync Fetching Function--------------------------#
    def fetch(self, query: str):
        try:
            results = cr.works(query=query, limit=1)
            items = results.get("message", {}).get("items", [])
            if not items:
                self.logger.warning(f"[WARN] No results found for: {query}")
                return -1
            return items[0]
        except Exception as e:
            self.logger.error(f"[ERROR] Failed to fetch title '{query}': {e}")
            return None
    
    #--------------------------Async Fetching Function--------------------#
    async def fetch_async(self, client, title: str, retries: int = 5):
        for attempt in range(retries):
            try:
                params = {"query": title, "rows": 1}
                headers={"User-Agent": "CS_Dashboard (mailto:dashboardarm@gmail.com)"}
                response = await client.get(CROSSREF_API, params=params, headers=headers, timeout=30.0)
                response.raise_for_status()  # Raises HTTPStatusError for 4xx/5xx
                data = response.json()
                items = data.get("message", {}).get("items", [])
                return items[0] if items else None

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    retry_after = int(e.response.headers.get("Retry-After", 3600 * random.randint(10,21)//10))
                    self.logger.warning(f"[WARN] 429 Too Many Requests. Waiting {retry_after}s before retry.")
                    await asyncio.sleep(retry_after)
                else:
                    status_code = e.response.status_code
                    self.logger.warning(
                        f"[WARN] HTTP {status_code} Retry {attempt+1}/{retries} for '{title}' after {2**attempt}s ({e})"
                    )

            except (httpx.ReadTimeout, httpx.ConnectTimeout) as e:
                # Network timeouts, no status code
                self.logger.warning(
                    f"[WARN] Timeout Retry {attempt + 1}/{retries} for '{title}' after {2**attempt}s ({e})"
                )

            except Exception as e:
                # Catch-all for other exceptions
                self.logger.warning(
                    f"[WARN] Retry {attempt + 1}/{retries} for '{title}' after {2**attempt}s ({e})"
                )

            await asyncio.sleep((2 ** (attempt+1)) + random.uniform(0, 1))

        self.logger.error(f"[ERROR] Failed to fetch '{title}' after {retries} retries.")
        return None

    
    #-------------------Async Batching & Fetching function----------------#
    async def fetch_all_async(self, titles: list[str], limit: int = 1):
        """Fetch many titles concurrently (limit = concurrency window)."""
        results = []
        sem = asyncio.Semaphore(limit)  # prevents overload on Crossref

        async def bound_fetch(client, t):
            async with sem:
                return await self.fetch_async(client, t)

        async with httpx.AsyncClient() as client:
            tasks = [bound_fetch(client, title) for title in titles]
            for coro in asyncio.as_completed(tasks):
                result = await coro
                if result:
                    results.append(result)
        return results
    
    def get_title(self, reference, from_metadata=True):
        if from_metadata:
            if  reference.get("article-title"):
                return reference.get("article-title")
            elif reference.get("journal-title"):
                return  reference.get("journal-title")
            elif reference.get("volume-title"):
                return   reference.get("volume-title")
            else:
                return  "None"
        else:
            title = reference.get("title")
            if isinstance(title, list) and len(title) > 0:
                return title[0]
            elif isinstance(title, str):
                return title
            else:
                return None
        
    def get_paper_type(self, reference):
        if  reference.get("article-title"):
            return PaperTypes.ARTICLE.name
        elif reference.get("journal-title"):
            return PaperTypes.JOURNAL.name
        elif reference.get("volume-title"):
            return PaperTypes.VOLUME.name
        else:
            print(ValueError("Missing Value - Unstructured"))
            return PaperTypes.UNSTRUCTURED.name
    
    def get_authors(self, reference):
        preprocesed_authors = reference.get("author")
        post_processed_authors = []
        if preprocesed_authors:
            for author in preprocesed_authors:
                given_name = author.get("given")
                family_name = author.get("family")
                name =given_name + ' ' + family_name
                post_processed_authors.append(name)
            
        return post_processed_authors
    
    def test_metadata(self, title, doi, date, abstract, authors, citation, link, paper_type):
        if not title:
            self.logger.error(ValueError("Missing Title"))
            return -1
        
        if not doi:
            self.logger.error(ValueError("Missing DOI"))
            return -2
        
        if not date:
            self.logger.error(ValueError("Missing Date"))
            return -3
        
        if not abstract:
            self.logger.error(ValueError("Missing Abstract"))
            return -4
        
        if not authors:
            self.logger.error(ValueError("Missing Authors"))
            return -5
        
        if citation < 0:
            self.logger.error(ValueError("Missing Citations"))
            return -6
        
        if not link:
            self.logger.error(ValueError("Missing Link"))
            return -7
        
        if not paper_type:
            self.logger.error(ValueError("Missing Paper_Type"))
            return -8
        
        return 0
    
    def build_paper_dict(self, title, doi, date, abstract, citation, link, paper_type):
        return {
            "title": title,
            "doi": doi,
            "published_date": date,
            "abstract": abstract,
            "citations_count": citation,
            "link": link,
            "paper_type": paper_type,
        }
        
    def build_author_dict(self, authors, orcid=''):
        author_list = []
        for i, name in enumerate(authors):
            max_id = (
                Authors.objects.annotate(
                    id_text=Cast(F("id"), output_field=models.CharField()),
                    num_id=Func(
                        Substr(F("id_text"), len(Config.AUTHORS_ID_PREFIX) + 1),
                        function="CAST",
                        template="CAST(%(expressions)s AS INTEGER)"
                    )
                ).aggregate(Max("num_id"))["num_id__max"]
            )
            next_id_num = (max_id or 0) + 1
            new_id = f"{Config.AUTHORS_ID_PREFIX}{next_id_num}"
            author_list.append({
                "id": new_id,
                "name": name,
                "orcid": orcid,
            })
        return author_list
    
    def build_keyword_dict(self, abstract):
        
        if not abstract or not isinstance(abstract, str) or len(abstract.strip()) == 0:
            return []
        
        kw_model = KeywordExtractor()
        keywords = kw_model.ExtractTopics(abstract)
        kw_list = []
        for keyword in keywords:
            max_id =(
                    Keywords.objects.annotate( 
                        id_text=Cast(F("id"), output_field=models.CharField()),
                        num_id=Func(
                        Substr(F("id_text"), len(Config.KEYWORDS_ID_PREFIX) + 1),
                        function="CAST",
                        template="CAST(%(expressions)s AS INTEGER)"
                    )
                )
                .aggregate(Max("num_id"))["num_id__max"]
            )
            next_id_num = (max_id or 0) + 1
            new_id = f"{Config.KEYWORDS_ID_PREFIX}{next_id_num}"
            kw_list.append({
                "id": new_id,
                'keyword': keyword,
            })
            return kw_list
    
    def RetrieveNewPapers(self, metadata):
        if metadata:
            other_papers = []
            references = metadata.get("reference")
            if references is not None:
                for index, reference in enumerate(references):
                    title = GetTitle(reference)
                    if (title == None) or (title in "Missing title at") or (title == 'None'):
                        continue
                    else:
                        try:
                            other_papers.append(title)
                        except Exception as e:
                            self.logger.error(e)
                            break
            return other_papers            
        else:
            self.logger.warning("[!] No metadata found")
            
   
                        
    @sync_to_async
    def save_to_db(self, paper, authors, topics):
        doi = paper.get("doi")
        if not doi:
            self.logger.warning("[WARN] Missing DOI — skipping paper.")
            return
        
        try:
             # ---- PAPER ----#
            with transaction.atomic():
                obj, created = Papers.objects.get_or_create(
                    doi=doi,
                    defaults={
                        "title": paper.get("title"),
                        "abstract": paper.get("abstract"),
                        "citations_count": paper.get("citations_count"),
                        "publishing_year": paper.get("published_date"),
                        "link": paper.get("link"),
                        "paper_type": paper.get("paper_type"),
                    },
                )
                if created:
                    self.logger.info(f"[DB] Saved: {paper.get('title')}")
                else:
                    self.logger.info(f"[DB] Already exists: {doi}")
                
                # ---- AUTHORS ----
                author_objs = []
                for a in authors:
                    try:
                        author_obj, _ = Authors.objects.get_or_create(
                            id=a.get("id"),
                            defaults={
                                "name": a.get("name") or "Unknown Author",
                                "orcid": a.get("orcid"),
                            },
                        )
                        author_objs.append(author_obj)
                    except IntegrityError as e:
                        self.logger.warning(f"[DB] Skipped duplicate author: {a.get('name')} ({e})")

                # ---- KEYWORDS ----
                keyword_objs = []
                for k in topics:
                    try:
                        keyword_obj, _ = Keywords.objects.get_or_create(
                            id=k.get("id"),
                            defaults={"keyword": k.get("keyword") or "unknown"},
                        )
                        keyword_objs.append(keyword_obj)
                    except IntegrityError as e:
                        self.logger.warning(f"[DB] Skipped duplicate keyword: {k.get('keyword')} ({e})")

                # --- Create junctions (ignore existing ones) ---
                if author_objs:
                    Author_Papers.objects.bulk_create(
                        [Author_Papers(doi=obj, author_id=a) for a in author_objs],
                        ignore_conflicts=True,
                    )

                if keyword_objs:
                    Keywords_Paper.objects.bulk_create(
                        [Keywords_Paper(doi=obj, keyword_id=k) for k in keyword_objs],
                        ignore_conflicts=True,
                    )

                self.logger.info(
                    f"[DB] Linked {len(author_objs)} authors & {len(keyword_objs)} keywords to {obj.title}"
                )


        except IntegrityError as e:
            self.logger.error(f"[DB] IntegrityError: {e}")
        except Exception as e:
            self.logger.error(f"[DB] Unexpected error: {e}")
            
            
    def bulk_save(self, papers, authors, topics):
        objs = []
        for paper in papers:
            objs.append(Papers(
                doi=paper.get("doi"),
                title=paper.get("title"),
                abstract=paper.get("abstract"),
                citations_count=paper.get("citations_count"),
                publishing_year=paper.get("published_date"),
                link=paper.get("link"),
                paper_type=paper.get("paper_type"),
            ))
        try:
            Papers.objects.bulk_create(objs, ignore_conflicts=True)
        except IntegrityError:
            pass  # safe to ignore since we used ignore_conflicts
        obj_auth = [Authors(id=a["id"], name=a["name"]) for a in authors]
        try:
            Authors.objects.bulk_create(obj_auth, ignore_conflicts=True)
        except IntegrityError:
            self.logger.warning("[DB] Some authors already existed — ignored.")
            
        obj_topics = [Keywords(id=t["id"], keyword=t["keyword"]) for t in topics]
        try:
            Keywords.objects.bulk_create(obj_topics, ignore_conflicts=True)
        except IntegrityError:
            self.logger.warning("[DB] Some topics already existed — ignored.")
            

from django.core.management.base import BaseCommand
from dashboard_app.models import Papers, Authors, Author_Papers, Keywords
import requests
from datetime import datetime
import time
import traceback
import re
import json
import os
from django.db import transaction
import random


class Command(BaseCommand):
    help = "Scrape CS papers from Crossref, store papers, authors, and CS-related keywords. Fully resumable between runs."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10)
        parser.add_argument("--max_keywords", type=int, default=50)

    def handle(self, *args, **options):
        limit = options["limit"]
        MAX_NEW_KEYWORDS = options["max_keywords"]

        print(f"\n=== Scraper Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")

        from django.core.management import call_command
        call_command("migrate", interactive=False)
        print("Database is up to date.\n")

        STATE_FILE = "scraper_state.json"

        seed_keywords = [
            "computer science", "machine learning", "deep learning", "artificial intelligence",
            "data mining", "neural networks", "natural language processing", "computer vision",
            "cloud computing", "blockchain", "cybersecurity", "big data",
            "graph neural networks", "knowledge graphs", "distributed systems",
            "quantum computing", "software engineering", "bioinformatics",
            "reinforcement learning", "internet of things", "data science",
            "recommender systems", "computational linguistics"
        ]

        errored_terms = []
        new_papers = []

        # === ID Generators ===
        def generate_next_author_id():
            last_num = 0
            for aid in Authors.objects.values_list("id", flat=True):
                try:
                    num = int(re.sub(r"[^0-9]", "", str(aid)))
                    last_num = max(last_num, num)
                except:
                    continue
            return f"at{last_num + 1:04d}"

        def generate_next_keyword_id():
            last_num = 0
            for kid in Keywords.objects.values_list("id", flat=True):
                try:
                    num = int(re.sub(r"[^0-9]", "", str(kid)))
                    last_num = max(last_num, num)
                except:
                    continue
            return f"kd{last_num + 1:04d}"

        # === CS classification helper (metadata + keyword scan) ===
        def is_cs_related(item) -> bool:
            """Determine if a paper or keyword is Computer Science–related."""
            subjects = [s.lower() for s in item.get("subject", [])]
            title = " ".join(item.get("title", [])).lower()
            abstract = item.get("abstract", "").lower()

            # ✅ Metadata-based classification
            if any(
                word in subjects_text
                for subjects_text in subjects
                for word in ["computer", "information", "technology", "artificial intelligence", "informatics"]
            ):
                return True

            # ✅ Fallback text-based classification
            core_terms = [
                "computer", "data", "algorithm", "learning", "network", "neural",
                "artificial", "intelligence", "software", "hardware", "machine",
                "computing", "programming", "robot", "system", "security",
                "cloud", "blockchain", "bioinformatics", "vision", "processing",
                "graph", "distributed", "quantum", "reinforcement", "cyber",
                "recommender", "language", "informatics", "automation", "database"
            ]

            # Require at least one CS indicator in title or abstract
            return any(term in title or term in abstract for term in core_terms)

        # === Keyword Cleaning Helper ===
        def clean_keyword(term: str) -> str | None:
            """Clean and validate extracted keyword phrases."""
            term = term.strip().lower()
            term = re.sub(r"[^a-z0-9\s\-\+]", "", term)
            term = re.sub(r"\s+", " ", term).strip()

            # Skip too long or too short phrases
            if len(term.split()) > 4 or len(term) < 3:
                return None

            # Skip common non-keyword boilerplate
            stop_phrases = [
                "proceedings", "conference", "workshop", "symposium", "journal",
                "transactions", "volume", "issue", "international", "book", "chapter",
                "introduction", "editorial", "poster", "abstract", "review", "study",
                "paper", "report", "meeting"
            ]
            if any(word in term for word in stop_phrases):
                return None

            # Auto-trim common patterns like “proceedings of the ieee…”
            term = re.sub(r"^(proceedings|conference|journal|international)\s+of\s+(the\s+)?", "", term)
            return term.strip() or None

        # === Keyword Add Function ===
        @transaction.atomic
        def add_keyword(term):
            cleaned = clean_keyword(term)
            if not cleaned:
                return None

            dummy_item = {"subject": [], "title": [cleaned], "abstract": ""}
            if not is_cs_related(dummy_item):
                print(f" Skipped non-CS keyword: '{cleaned}'")
                return None

            if Keywords.objects.filter(keyword__iexact=cleaned).exists():
                return None

            new_id = generate_next_keyword_id()
            Keywords.objects.create(id=new_id, keyword=cleaned)
            print(f" Added new keyword: '{cleaned}' ({new_id})")
            return cleaned

        # === Extract new keywords dynamically ===
        def extract_new_keywords(item):
            new_terms = set()
            for field in ["subject", "container-title", "subtitle", "short-container-title"]:
                if field in item:
                    for entry in item[field]:
                        if len(entry) > 3:
                            new_terms.add(entry.lower())

            for ref in item.get("reference", []):
                ref_title = ref.get("article-title") or ref.get("series-title") or ref.get("journal-title")
                if ref_title and len(ref_title) > 5:
                    words = re.findall(r"[a-zA-Z][a-zA-Z\s\-]{3,50}", ref_title)
                    for w in words:
                        if 4 < len(w) < 40:
                            new_terms.add(w.lower().strip())

            new_terms = {re.sub(r"[^a-z0-9\s\-]", "", n).strip() for n in new_terms if n.strip()}
            return list(new_terms)

        # === Load scraper state ===
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    state = json.load(f)
                pending_keywords = state.get("pending_keywords", [])
                processed_keywords = set(state.get("processed_keywords", []))
                processed_dois = set(state.get("processed_dois", []))
                print(f"Loaded state: {len(pending_keywords)} pending keywords, {len(processed_dois)} papers processed.\n")
            except Exception:
                pending_keywords = [k.lower() for k in seed_keywords]
                processed_keywords, processed_dois = set(), set()
        else:
            pending_keywords = [k.lower() for k in seed_keywords]
            processed_keywords, processed_dois = set(), set()

        new_keywords_this_run = 0

        # === Main Scraper Loop ===
        while pending_keywords and new_keywords_this_run < MAX_NEW_KEYWORDS:
            term = pending_keywords.pop(0)
            if term in processed_keywords:
                continue
            processed_keywords.add(term)
            add_keyword(term)

            print(f"\n🔍 Searching Crossref for: '{term}'")
            url = "https://api.crossref.org/works"
            params = {"query.title": term, "rows": limit}

            try:
                # Add polite delay before each request
                time.sleep(random.uniform(2, 4))  # wait 2–4 seconds between requests
                response = requests.get(url, params=params)
                if response.status_code == 429:
                    print(f"[WARN] Rate limit hit for '{term}', waiting 10 seconds before retry...")
                    time.sleep(10)
                    response = requests.get(url, params=params)  # retry once
                    if response.status_code != 200:
                        print(f"Failed to fetch data from Crossref ({response.status_code}) for {term}")
                        errored_terms.append(term)
                        continue


                items = response.json().get("message", {}).get("items", [])
                if not items:
                    print(f"No results for '{term}'")
                    continue

                for item in items:
                    if not is_cs_related(item):
                        print(f" Skipped non-CS paper: {item.get('title', ['N/A'])[0]}")
                        continue

                    doi = item.get("DOI")
                    if not doi or doi in processed_dois:
                        continue

                    title = " ".join(item.get("title", [])) or "N/A"
                    year = 0
                    for key in ["published-print", "published-online", "created"]:
                        if key in item and "date-parts" in item[key]:
                            parts = item[key]["date-parts"][0]
                            if parts:
                                year = parts[0]
                                break

                    abstract = item.get("abstract", "N/A")
                    citations = item.get("is-referenced-by-count", 0)
                    link = item.get("URL", "")
                    paper_type = item.get("type", "unknown")

                    if not Papers.objects.filter(doi=doi).exists():
                        Papers.objects.create(
                            doi=doi,
                            title=title,
                            publishing_year=year,
                            abstract=abstract,
                            citations_count=citations,
                            link=link,
                            paper_type=paper_type
                        )
                        new_papers.append(title)
                        print(f" Saved paper: {title}")
                    else:
                        print(f" Paper already in database: {doi}")

                    processed_dois.add(doi)

                    authors = item.get("author", [])
                    for author in authors:
                        name = f"{author.get('given', '')} {author.get('family', '')}".strip()
                        orcid = author.get("ORCID", None)
                        if orcid:
                            orcid = orcid.split("/")[-1]
                        if not name:
                            continue
                        existing_author = Authors.objects.filter(name=name).first()
                        if not existing_author:
                            new_id = generate_next_author_id()
                            Authors.objects.create(id=new_id, name=name, orcid=orcid)
                            print(f"Added author: {name} ({new_id})")
                        else:
                            new_id = existing_author.id
                        author_ref = Authors.objects.get(id=new_id)
                        Author_Papers.objects.get_or_create(doi_id=doi, author_id=author_ref)

                    discovered = extract_new_keywords(item)
                    for kw in discovered:
                        if new_keywords_this_run >= MAX_NEW_KEYWORDS:
                            break
                        added = add_keyword(kw)
                        if added and added not in processed_keywords:
                            pending_keywords.append(added)
                            new_keywords_this_run += 1

                time.sleep(1)

            except Exception as e:
                print(f"Error while processing '{term}': {e}")
                traceback.print_exc()
                errored_terms.append(term)

        # === Save state ===
        with open(STATE_FILE, "w") as f:
            json.dump({
                "pending_keywords": pending_keywords,
                "processed_keywords": list(processed_keywords),
                "processed_dois": list(processed_dois)
            }, f, indent=4)

        print("\n Saved scraper state for next run.")
        print(f"Remaining pending keywords: {len(pending_keywords)}")
        print(f"Total papers processed: {len(processed_dois)}\n")

        print("=== Summary ===")
        print(f"Errored Terms ({len(errored_terms)}): {errored_terms}")
        print(f"New Papers Added ({len(new_papers)}): {new_papers[:10]} ...")
        print(f"=== Scraper Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")

from abc import ABC, abstractmethod
import logging
#from rake_nltk import Rake

logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    @abstractmethod
    def fetch(self, query: str, **kwargs):
        """Fetch data for a given query or DOI."""
        pass

    @staticmethod
    def normalize_entry(entry: dict):
        """Ensure consistent structure."""
        return {
            "title": entry.get("title", [""])[0],
            "authors": ", ".join([a.get("given", "") + " " + a.get("family", "") for a in entry.get("author", [])]),
            "abstract": entry.get("abstract", ""),
            "doi": entry.get("DOI", ""),
            "source": "CrossRef",
            "link": entry.get("URL", ""),
            "published_date": entry.get("issued", {}).get("date-parts", [[None]])[0][0],
        }

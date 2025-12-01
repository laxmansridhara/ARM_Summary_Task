import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard.settings")  # Adjust if your settings module is named differently
django.setup()

import nltk
nltk.download('stopwords', quiet=True)
nltk.download('punkt', quiet=True)
nltk.download('punkt_tab', quiet=True)

from keybert import KeyBERT
from nltk.corpus import stopwords
from dashboard_app.models import Papers, Keywords, Keywords_Paper
from dashboard_app import const
import random


kw_model = KeyBERT(model="all-MiniLM-L6-v2")
custom_stopwords = stopwords.words('english')

# Add your own words (case-insensitive!)
custom_stopwords.extend([
     'study', 'result', 'results', 'paper', 'approach', 'method', 'methods',
        'proposed', 'research', 'system', 'data', 'analysis', 'problem', 'based',
        'use', 'using', 'model', 'models', 'experiment', 'experiments', 'performance',
        'propose', 'provide', 'present', 'different', 'new', 'show', 'demonstrate',
        'high', 'low', 'good', 'better', 'work', 'works', 'set', 'used', 'done',
        'important', 'various', 'including', 'example', 'number', 'paper', 'aim', 'jats'
])

def extract_keywords_from_text(abstract, top_n=30):
    """Extracts keywords using RAKE + NLTK."""
    if not abstract or not abstract.strip():
        return []

    keywords = kw_model.extract_keywords(
        abstract,
        keyphrase_ngram_range=(1, 5),  
        stop_words=custom_stopwords,
        use_mmr=True,  # diversity
        diversity=0.25,
        top_n=top_n,
    )
    
    new_text = ' '.join([kw for kw, _ in keywords])
    
    procesed_keywords = kw_model.extract_keywords(
        
        new_text,
        keyphrase_ngram_range=(1, 2),  
        stop_words=custom_stopwords,
        use_mmr=False, 
        top_n=5,
    )
    
    print(f"Original Keywords: {[kw for kw, _ in keywords]} \n")
    print(f"Procesed Keywords: {[kw for kw, _ in procesed_keywords]}\n")
    
    return [kw for kw, _ in keywords]


def attach_keywords_to_paper(paper, top_n=5):
    """Extracts and attaches keywords to a given Paper object."""
    if not paper.abstract:
        print(f"Paper '{paper.title}' has no abstract, skipping.")
        return

    extracted_keywords = extract_keywords_from_text(paper.abstract, top_n=top_n)
    if not extracted_keywords:
        print(f"No keywords extracted for '{paper.title}'.")
        return

    for kw in extracted_keywords:
        kw = kw.strip().lower()

        # Check if keyword already exists
        keyword_obj = Keywords.objects.filter(keyword=kw).first()

        # If not, create new keyword with custom ID format
        if not keyword_obj:
            count = Keywords.objects.count() + 1
            custom_id = f"kw{count}"
            keyword_obj = Keywords.objects.create(id=custom_id, keyword=kw)

        # Link keyword ↔ paper
        Keywords_Paper.objects.get_or_create(keyword_id=keyword_obj, doi=paper)

    print(f"Added {len(extracted_keywords)} keywords to '{paper.title}'.")
        
def main():
    papers = list(Papers.objects.all())  # Ensure we can get a random element
    if not papers:
        print("No papers found in the database.")
        return

    index = random.randint(0, len(papers))
    abstract = papers[index].abstract 
    extract_keywords_from_text(abstract)
    print(f"\n Paper: {papers[index].title}\n")
    print(f"Abstract: {abstract[:500]}...\n")
    
    kw = extract_keywords_from_text(abstract)
    #
    # print(f"Keywords attached for paper: {kw}")
    
if __name__=="__main__":
    main()
    
class KeywordExtractor():
    def __init__(self, top_n=5):
        self.model =  KeyBERT(model="all-MiniLM-L6-v2")
        
        self.custom_stopwords = stopwords.words('english')
        self.custom_stopwords.extend([
            'study', 'result', 'results', 'paper', 'approach', 'method', 'methods',
                'proposed', 'research', 'system', 'data', 'analysis', 'problem', 'based',
                'use', 'using', 'model', 'models', 'experiment', 'experiments', 'performance',
                'propose', 'provide', 'present', 'different', 'new', 'show', 'demonstrate',
                'high', 'low', 'good', 'better', 'work', 'works', 'set', 'used', 'done',
                'important', 'various', 'including', 'example', 'number', 'paper', 'aim', 'jats'
        ])
        self.top_n = top_n
        
    def ExtractTopics(self, text):
        
        if text is None:
            raise ValueError("No text has been passed to the extractor")
        
        preprocessed_keywords = self.model.extract_keywords(
            text,
            keyphrase_ngram_range=(1, 5),  
            stop_words=self.custom_stopwords,
            use_mmr=True,  # diversity
            diversity=0.25,
            top_n=self.top_n**2,
        )
        
        new_text = ' '.join([kw for kw, _ in preprocessed_keywords])
    
        procesed_keywords = self.model.extract_keywords(
            new_text,
            keyphrase_ngram_range=(1, 2),  
            stop_words=self.custom_stopwords,
            use_mmr=False, 
            top_n=self.top_n,
        )
        
        return [kw for kw,_ in procesed_keywords]
from transformers import pipeline
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re, numpy as np


tokenizer = AutoTokenizer.from_pretrained("sshleifer/distilbart-cnn-12-6")
model_name = "sshleifer/distilbart-cnn-12-6"
SUMMARIZER = AutoModelForSeq2SeqLM.from_pretrained(model_name)



#  MODEL LOADING (DISTILBART)

def _get_summarizer():
    global SUMMARIZER
    return SUMMARIZER



#  TEXT CLEANING

def clean_text(html_or_text: str) -> str:
    return re.sub(r"<[^>]+>", "", html_or_text or "").strip()


#  FALLBACK SUMMARIZER (TF-IDF)

def _tfidf_fallback(text: str, min_percent: int, max_percent: int) -> str:
    sentences = re.split(r'(?<=[.!?]) +', text)
    if len(sentences) <= 2:
        return text.strip()

    tfidf = TfidfVectorizer(stop_words="english")
    tfidf_matrix = tfidf.fit_transform(sentences)
    scores = cosine_similarity(tfidf_matrix, tfidf_matrix).sum(axis=1)
    ranked_idx = np.argsort(scores)[::-1]

    min_sent = max(1, int(len(sentences) * (min_percent / 100.0)))
    max_sent = max(min_sent + 1, int(len(sentences) * (max_percent / 100.0)))

    chosen = [sentences[i] for i in ranked_idx[:max_sent]]
    return " ".join(chosen).strip()



#  MAIN SUMMARIZATION FUNCTION

def summarize_text(text: str, min_percent: int = 30, max_percent: int = 60) -> str:
    txt = clean_text(text)
    if not txt:
        return "No abstract available to summarize."

    total_words = len(txt.split())
    if total_words < 20:
        return f"Abstract too short ({total_words} words)."

    # validate input %
    try:
        min_percent, max_percent = int(min_percent), int(max_percent)
    except:
        min_percent, max_percent = 30, 60

    if min_percent > max_percent:
        min_percent, max_percent = max_percent, min_percent

    min_percent = max(5, min(80, min_percent))
    max_percent = max(min_percent + 5, min(90, max_percent))

    print(f"SUMMARY SETTINGS: min={min_percent}%, max={max_percent}%, total_words={total_words}")

    summarizer = _get_summarizer()

    
    #  FIXED TOKENIZATION
    
    inputs = tokenizer(
        txt,
        return_tensors="pt",
        truncation=True,
        max_length=1024
    )

    # PRINT NUMBER OF INPUT TOKENS
    input_tokens = inputs["input_ids"].shape[1]
    print(f"INPUT TOKENS: {input_tokens}")

    
    #  CASE 1: Model available
    
    if summarizer:
        try:
            min_tokens = max(25, int(input_tokens * (min_percent / 100.0)))
            max_tokens = max(min_tokens + 10, round(input_tokens * (max_percent / 100.0)))

            print(f"Using model summarizer: min_tokens={min_tokens}, max_tokens={max_tokens}")

            summary_ids = summarizer.generate(
                **inputs,
                min_length=min_tokens,
                max_length=max_tokens,

                #  ENABLE SAMPLING — REQUIRED for DistilBART to change length
                do_sample=True,
                #top_p=0.90,
                temperature=0.85,

                # encourage longer output
                length_penalty=10,#9,
                #no_repeat_ngram_size=3,
                early_stopping=False
            )

            output_tokens = len(summary_ids[0])
            print(f"OUTPUT TOKENS: {output_tokens}")
            # Decode output
            summary = tokenizer.decode(summary_ids[0], skip_special_tokens=True).strip()

            # PRINT NUMBER OF OUTPUT TOKENS
            output_tokens = len(summary_ids[0])
            print(f"OUTPUT TOKENS: {output_tokens}")

            if not summary:
                raise ValueError("Empty model summary")

            print("Model summarization successful.")
            return summary

        except Exception as e:
            print(f"[WARN] Model summarization failed: {e}")

    
    #  CASE 2: Fallback mode
    
    print("Falling back to TF-IDF summarizer.")
    return _tfidf_fallback(txt, min_percent, max_percent)

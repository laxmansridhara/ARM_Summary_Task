import django, os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard.settings")
django.setup()

from django.db import transaction
from dashboard_app.models import Papers, Authors, Keywords, Author_Papers, Keywords_Paper

@transaction.atomic
def clean_duplicates():
    print("🧹 Starting database cleanup...")

    # ---------- REMOVE EMPTY IDs ----------
    print("🗑️ Removing invalid or empty rows...")

    # Delete entries with empty primary keys or critical foreign keys
    invalid_papers = Papers.objects.filter(doi__isnull=True) | Papers.objects.filter(doi__exact="")
    deleted_papers = invalid_papers.count()
    invalid_papers.delete()

    invalid_authors = Authors.objects.filter(id__isnull=True) | Authors.objects.filter(name__exact="")
    deleted_authors = invalid_authors.count()
    invalid_authors.delete()

    invalid_keywords = Keywords.objects.filter(id__isnull=True) | Keywords.objects.filter(keyword__exact="")
    deleted_keywords = invalid_keywords.count()
    invalid_keywords.delete()

    invalid_author_papers = Author_Papers.objects.filter(
        doi__isnull=True
    ) | Author_Papers.objects.filter(
        author_id__isnull=True
    )
    deleted_author_papers = invalid_author_papers.count()
    invalid_author_papers.delete()

    invalid_keyword_papers = Keywords_Paper.objects.filter(
        doi__isnull=True
    ) | Keywords_Paper.objects.filter(
        keyword_id__isnull=True
    )
    deleted_keyword_papers = invalid_keyword_papers.count()
    invalid_keyword_papers.delete()

    print(f" - Deleted {deleted_papers} invalid Papers")
    print(f" - Deleted {deleted_authors} invalid Authors")
    print(f" - Deleted {deleted_keywords} invalid Keywords")
    print(f" - Deleted {deleted_author_papers} invalid Author_Papers")
    print(f" - Deleted {deleted_keyword_papers} invalid Keywords_Paper")

    # ---------- PAPERS ----------
    print("🔍 Checking Papers for duplicates...")
    seen_titles = {}
    for paper in Papers.objects.all().order_by("doi"):
        key = paper.title.strip().lower()
        if key in seen_titles:
            print(f"Duplicate paper: {paper.title} -> deleting {paper.doi}")
            # Re-link junctions before deleting
            Author_Papers.objects.filter(doi=paper).update(doi=seen_titles[key])
            Keywords_Paper.objects.filter(doi=paper).update(doi=seen_titles[key])
            paper.delete()
        else:
            seen_titles[key] = paper

    # ---------- AUTHORS ----------
    print("🔍 Checking Authors for duplicates...")
    seen_authors = {}
    for author in Authors.objects.all():
        key = (author.name.strip().lower(), author.orcid or "")
        if key in seen_authors:
            print(f"Duplicate author: {author.name} -> deleting {author.id}")
            Author_Papers.objects.filter(author_id=author).update(author_id=seen_authors[key])
            author.delete()
        else:
            seen_authors[key] = author

    # ---------- KEYWORDS ----------
    print("🔍 Checking Keywords for duplicates...")
    seen_keywords = {}
    for kw in Keywords.objects.all():
        key = kw.keyword.strip().lower()
        if key in seen_keywords:
            print(f"Duplicate keyword: {kw.keyword} -> deleting {kw.id}")
            Keywords_Paper.objects.filter(keyword_id=kw).update(keyword_id=seen_keywords[key])
            kw.delete()
        else:
            seen_keywords[key] = kw

    # ---------- AUTHOR_PAPERS ----------
    print("🔍 Checking Author_Papers junctions...")
    seen_pairs = set()
    for ap in Author_Papers.objects.all():
        pair = (ap.doi_id, ap.author_id_id)
        if pair in seen_pairs:
            ap.delete()
        else:
            seen_pairs.add(pair)

    # ---------- KEYWORDS_PAPER ----------
    print("🔍 Checking Keywords_Paper junctions...")
    seen_kw_pairs = set()
    for kp in Keywords_Paper.objects.all():
        pair = (kp.doi_id, kp.keyword_id_id)
        if pair in seen_kw_pairs:
            kp.delete()
        else:
            seen_kw_pairs.add(pair)

    print("✅ Cleanup complete!")

if __name__ == "__main__":
    clean_duplicates()

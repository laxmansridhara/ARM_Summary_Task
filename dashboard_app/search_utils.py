import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard.settings")  # Adjust if your settings module is named differently
django.setup()

from django.shortcuts import render
from django.db.models import Q
from .models import Papers, Authors, Keywords, Author_Papers, Keywords_Paper


def Search_Query(request):
    query = request.GET.get("q","").strip()
    authors = []
    papers = []
    
    if query:
        authors = Authors.objects.filter(Q(name__icontains=query) | Q(orcid__icontains=query))
        
        if authors.exists():
            author_papers = Author_Papers.objects.filter(author_id__in=authors)
            authors_doi = author_papers.values_list("doi", flat=True).distinct()
        else:
            authors_doi = []
            
        keyword_matches = Keywords.objects.filter(keyword__icontains=query)
        keyword_dois = Keywords_Paper.objects.filter(keyword_id__in=keyword_matches).values_list("doi", flat=True).distinct()

        text_dois = Papers.objects.filter(
            Q(title__icontains=query) | Q(abstract__icontains=query)
        ).values_list("doi", flat=True)

        all_related_dois = set(authors_doi) | set(keyword_dois) | set(text_dois)
        papers = Papers.objects.filter(doi__in=all_related_dois).order_by("-citations_count", "-publishing_year")

        if not authors.exists() and not papers.exists():
            papers = Papers.objects.filter(
                Q(title__icontains=query) | Q(abstract__icontains=query)
            ).order_by("-citations_count", "-publishing_year")

    context = {
        "authors": authors,
        "papers": papers,
    }
    return render(request, "search.html", context)
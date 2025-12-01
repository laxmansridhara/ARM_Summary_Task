from django.shortcuts import render, get_object_or_404
from .models import Papers, Authors, Keywords, Author_Papers, Keywords_Paper
from .summarize_utils import summarize_text

def Render_Paper(request):
    doi = request.GET.get("doi")
    if not doi:
        return render(request, "paper.html", {"error": "No DOI provided."})

    paper = get_object_or_404(Papers, doi=doi)

    authors = Authors.objects.filter(
        id__in=Author_Papers.objects.filter(doi=paper).values_list("author_id", flat=True).distinct()
    ).order_by("name").distinct()

    topics = Keywords.objects.filter(
        id__in=Keywords_Paper.objects.filter(doi=paper).values_list("keyword_id", flat=True).distinct()
    ).order_by("keyword").distinct()

    try:
        min_percent = int(request.GET.get("min_percent", "30"))
    except ValueError:
        min_percent = 30

    try:
        max_percent = int(request.GET.get("max_percent", "60"))
    except ValueError:
        max_percent = 60

    summary_text = ""
    if paper.abstract:
        summary_text = summarize_text(
            paper.abstract,
            min_percent=min_percent,
            max_percent=max_percent,
        )

    context = {
        "paper": paper,
        "authors": authors,
        "topics": topics,
        "summary": summary_text,
        "min_percent": min_percent,
        "max_percent": max_percent,
    }
    return render(request, "paper.html", context)

from django.shortcuts import render, get_object_or_404
from .models import Authors, Papers, Author_Papers, Keywords, Keywords_Paper
from django.db.models import Sum, Count


def Render_Author(request):
    # Get author by ?name= query param
    name = request.GET.get("name")
    if not name:
        return render(request, "error.html", {"message": "Author name is required"})

    author = get_object_or_404(Authors, name=name)

    # All papers by author
    paper_ids = Author_Papers.objects.filter(author_id=author.id).values_list("doi", flat=True)
    papers = Papers.objects.filter(doi__in=paper_ids)

    # Total citations
    total_citations = papers.aggregate(total=Sum("citations_count"))["total"] or 0

    # Get keyword counts
    keyword_ids = Keywords_Paper.objects.filter(doi__in=paper_ids).values_list("keyword_id", flat=True)

    top_topics = (
        Keywords.objects.filter(id__in=keyword_ids)
        .values_list("keyword")
        .annotate(count=Count("keyword"))
        .order_by("-count")[:10]
    )

    context = {
        "author": author,
        "papers": papers,
        "total_citations": total_citations,
        "top_topics": top_topics,
    }

    return render(request, "author.html", context)

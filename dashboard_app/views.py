from django.shortcuts import render, redirect
from django.db.models.functions import Length
from dashboard_app.models import Papers
from dashboard_app.summarize_utils import summarize_text

# Utility modules
from dashboard_app import home_utils, search_utils, paper_utils, author_utils


def home(request):
    return home_utils.DomainAnalysis(request)


def profile(request):
    return render(request, "profile.html")


def search(request):
    return search_utils.Search_Query(request)


def paper_detail(request):
    # Handles /paper/?doi=xxxx
    return paper_utils.Render_Paper(request)


def author_detail(request):
    # Handles /author/?name=xxxxx
    return author_utils.Render_Author(request)


def login_view(request):
    return render(request, "login.html")


def signup_view(request):
    return render(request, "signin.html")


# ------------------------------------------------------------
# Auxiliary Summary Lab (Developer Tool)
# ------------------------------------------------------------

def summarizer_lab(request):
    """
    Picks random papers, generates summaries, displays them.
    Useful for quality checking summarization.
    """

    try:
        n = int(request.GET.get("n", "5"))
    except ValueError:
        n = 5

    n = max(1, min(20, n))

    qs = (
        Papers.objects
        .exclude(abstract__isnull=True)
        .exclude(abstract__exact="")
        .annotate(abstract_len=Length("abstract"))
        .order_by("-abstract_len")
    )

    import random
    papers = list(qs[:200])
    random.shuffle(papers)
    papers = papers[:n]

    rows = []
    for p in papers:
        try:
            s = summarize_text(p.abstract)
        except Exception:
            s = ""

        rows.append({
            "doi": p.doi,
            "title": p.title,
            "abstract": p.abstract,
            "summary": s,
            "link": p.link,
        })

    return render(request, "aux_summary.html", {"rows": rows, "count": len(rows)})


# ------------------------------------------------------------
# Generate Summary for Single Paper (POST)
# ------------------------------------------------------------

def generate_summary_view(request):
    if request.method == "POST":
        paper_id = request.POST.get("paper_id")
        word_limit = int(request.POST.get("word_limit", 100))

        paper = Papers.objects.get(id=paper_id)

        summary_text = summarize_text(
            paper.abstract,
            word_limit=word_limit
        )

        return render(request, "paper_detail.html", {
            "paper": paper,
            "summary": summary_text,
            "word_limit": word_limit,
        })

    return redirect("dashboard-home")

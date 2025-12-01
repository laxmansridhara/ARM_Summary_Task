import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard.settings")  # Adjust if your settings module is named differently
django.setup()


from dashboard_app.scrapers import utils
import logging
from django.utils import timezone
from io import BytesIO
from django.db.models import Count, Max
from dashboard_app.models import Papers, Keywords, Keywords_Paper
import base64
from django.shortcuts import render
import matplotlib
matplotlib.use("Agg") 
import matplotlib.pyplot as plt
from collections import Counter, defaultdict


def Get_All_Papers(limit=None):
    papers = Papers.objects.all() if not limit else Papers.objects.all()[:limit]
    return papers

def DomainAnalysis(request):
    
     # --- Read search range from query parameters ---
    try:
        min_year = int(request.GET.get("min_year")) if request.GET.get("min_year") else  Papers.objects.order_by('publishing_year').first().publishing_year
        max_year = int(request.GET.get("max_year")) if request.GET.get("max_year") else  Papers.objects.order_by('-publishing_year').first().publishing_year
    except ValueError:
        min_year, max_year = None, None

    # --- Filter papers by year range ---
    papers = Papers.objects.all()
    if min_year:
        papers = papers.filter(publishing_year__gte=min_year)
    if max_year:
        papers = papers.filter(publishing_year__lte=max_year)

    # --- Yearly paper count ---
    data = Papers.objects.values('publishing_year').annotate(total=Count('doi')).order_by('publishing_year')
    labels = [d['publishing_year'] for d in data]
    values = [d['total'] for d in data]
    
    total_papers = sum(values)
    avg_papers = total_papers // len(values) if values else 0
    
    current_year = timezone.now().year
    papers_this_year = Papers.objects.filter(publishing_year=current_year).count()

    # --- Chart generation ---
    plt.figure(figsize=(8, 5))
    plt.plot(labels, values, marker='o', linestyle='-', color='g')
    plt.title("Publications per Year")
    plt.xlabel("Year")
    plt.ylabel("Number of Papers")
    plt.grid(True)
    plt.tight_layout()

    # Save to a BytesIO buffer instead of a file
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    plt.close()
    buffer.seek(0)

    image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    keyword_to_papers = defaultdict(list)
    all_kp = Keywords_Paper.objects.select_related('keyword_id', 'doi').all()
    for kp in all_kp:
        keyword_to_papers[kp.keyword_id.id].append(kp.doi)  
        
    topic_total_count = Counter()
    topic_yearly_count = defaultdict(lambda: Counter())
    for keyword_id, papers_list in keyword_to_papers.items():
        for paper in papers_list:
            if min_year <= paper.publishing_year <= max_year:
                topic_total_count[keyword_id] += 1
                topic_yearly_count[keyword_id][paper.publishing_year] += 1

    keyword_id_to_name = {k.id: k.keyword for k in Keywords.objects.filter(id__in=topic_total_count.keys())}

    # --- Top N topics for pie chart and list ---
    top_n = 10
    top_keywords = topic_total_count.most_common(top_n)
    top_keywords_names = [(keyword_id_to_name[k[0]], k[1]) for k in top_keywords]

    # --- Pie chart ---
    labels = [t[0] for t in top_keywords_names]
    counts = [t[1] for t in top_keywords_names]
    total_papers_in_range = sum(topic_total_count.values())
    other_count = max(total_papers_in_range - sum(counts), 0)
    if other_count > 0:
        labels.append("Other")
        counts.append(other_count)

    plt.figure(figsize=(6, 6))
    plt.pie(counts, labels=labels, autopct='%1.1f%%', startangle=140)
    plt.title(f"Top {len(top_keywords_names)} Topics Distribution")
    plt.tight_layout()
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    plt.close()
    buffer.seek(0)
    pie_chart_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    # --- Determine top 10 topics in max_year for trend lines ---
    topic_count_max_year = {k: v.get(max_year, 0) for k, v in topic_yearly_count.items()}
    top_10_keyword_ids_max_year = sorted(topic_count_max_year, key=topic_count_max_year.get, reverse=True)[:10]

    # --- Prepare cumulative trend data for top 10 in max_year ---
    all_years = list(range(min_year, max_year + 1))
    top_topic_trends = {}
    for keyword_id in top_10_keyword_ids_max_year:
        cumulative = 0
        yearly_counts = []
        for year in all_years:
            count = topic_yearly_count[keyword_id].get(year, 0)
            cumulative += count
            yearly_counts.append(cumulative)
        top_topic_trends[keyword_id_to_name[keyword_id]] = yearly_counts

    # --- Plot cumulative trend lines ---
    plt.figure(figsize=(10, 6))

    for topic, cumulative_counts in top_topic_trends.items():
        plt.plot(
            all_years,
            cumulative_counts,
            linewidth=2.5,   # make lines thicker
            alpha=0.8,       # slightly transparent to reduce overlap
            label=topic
            # marker removed
        )

    plt.xlabel("Year")
    plt.ylabel("Cumulative Number of Papers")
    plt.title(f"Cumulative Top 10 Trending Topics ({min_year}-{max_year}) — Based on {max_year}")
    plt.grid(True)
    plt.legend(loc='best', fontsize='small')
    plt.tight_layout()

    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    plt.close()
    buffer.seek(0)
    topics_trend_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    # --- 8. Render template ---
    context = {
        'chart': image_base64,
        'topics_trend_chart': topics_trend_base64,
        'topics_pie_chart': pie_chart_base64,
        'avg_papers': avg_papers,
        'papers_this_year': papers_this_year,
        'total_papers': total_papers,
        'current_year': current_year,
        'latest_year': max_year,
        'top_topics': top_keywords_names[:10],
        'min_year': min_year,
        'max_year': max_year,
    }
    
    return render(request, 'index.html', context)



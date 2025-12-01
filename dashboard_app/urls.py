from django.urls import path
from dashboard_app import views

urlpatterns = [
    path("", views.home, name="dashboard-home"),
    path("profile/", views.profile, name="profile"),
    path("search/", views.search, name="search"),
    path("paper/", views.paper_detail, name="paper_detail"),   # <-- FIXED
    path("login/", views.login_view, name="login"),
    path("signup/", views.signup_view, name="signup"),
    path("author/", views.author_detail, name="author_detail"),
]


from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    path("discover/", views.DiscoverView.as_view(), name="discover"),
    path("moods/", views.MoodsView.as_view(), name="moods"),
    path("social/", views.SocialView.as_view(), name="social"),
]

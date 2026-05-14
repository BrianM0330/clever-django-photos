from django.urls import path

from . import views

app_name = "photos"

urlpatterns = [
    path("", views.PhotoListView.as_view(), name="index"),
    path("<int:pk>/", views.PhotoDetailView.as_view(), name="detail"),
    path("<int:pk>/like/", views.LikeToggleView.as_view(), name="like_toggle"),
    path("<int:pk>/comments/", views.CommentCreateView.as_view(), name="comment_create"),
    path("comments/<int:pk>/", views.CommentDestroyView.as_view(), name="comment_destroy"),
]

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView

from apps.photos.models import Comment, Like, Photo


class PhotoListView(LoginRequiredMixin, ListView):
    model = Photo
    context_object_name = "photos"
    template_name = "photos/photo_list.html"

    def get_queryset(self):
        return Photo.objects.order_by("id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        photos = list(context["photos"])
        liked_photo_ids = Photo.liked_ids_for(self.request.user, photos)
        for photo in photos:
            photo.liked_by_current_user = photo.pk in liked_photo_ids
        context["photos"] = photos
        context["liked_photo_ids"] = liked_photo_ids
        return context


class PhotoDetailView(LoginRequiredMixin, DetailView):
    model = Photo
    context_object_name = "photo"
    template_name = "photos/photo_detail.html"

    def get_queryset(self):
        return Photo.objects.prefetch_related("comments__user")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.object.liked_by_current_user = self.object.liked_by(
            self.request.user)
        context["comments"] = self.object.comments.select_related(
            "user").order_by("created_at")
        return context


class LikeToggleView(LoginRequiredMixin, View):
    def post(self, request, pk):
        photo = get_object_or_404(Photo, pk=pk)
        if request.POST.get("_method", "").lower() == "delete":
            Like.delete_for(user=request.user, photo=photo)
            return self.render_response(request, photo, liked=False)

        Like.create_for(user=request.user, photo=photo)
        return self.render_response(request, photo, liked=True)

    def delete(self, request, pk):
        photo = get_object_or_404(Photo, pk=pk)
        Like.delete_for(user=request.user, photo=photo)
        return self.render_response(request, photo, liked=False)

    def render_response(self, request, photo, *, liked: bool):
        photo.refresh_from_db(fields=["likes_count"])
        photo.liked_by_current_user = liked
        if request.headers.get("HX-Request"):
            return render(request, "photos/_like_button.html", {"photo": photo, "liked": liked})

        if next_url := request.POST.get("next"):
            return redirect(next_url)

        return JsonResponse({"liked": liked, "likes_count": photo.likes_count})


class CommentCreateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        photo = get_object_or_404(Photo, pk=pk)
        try:
            comment = Comment.create_for(
                user=request.user, photo=photo, body=request.POST.get("body", ""))
        except ValidationError as error:
            if request.headers.get("HX-Request"):
                return render(request, "photos/_comment_error.html", {"error": error}, status=400)

            return JsonResponse({"errors": error.message_dict}, status=400)

        if request.headers.get("HX-Request"):
            return render(request, "photos/_comment.html", {"comment": comment})

        return redirect(reverse("photos:detail", kwargs={"pk": photo.pk}))


class CommentDestroyView(LoginRequiredMixin, View):
    def delete(self, request, pk):
        comment = get_object_or_404(Comment, pk=pk, user=request.user)
        photo_pk = comment.photo_id
        comment.delete()

        if request.headers.get("HX-Request"):
            return JsonResponse({"deleted": True, "comment_id": pk})

        return redirect(reverse("photos:detail", kwargs={"pk": photo_pk}))

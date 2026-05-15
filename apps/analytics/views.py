from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from apps.analytics.models import UserAffinity
from apps.photos.models import Photo


class DiscoverView(LoginRequiredMixin, TemplateView):
    template_name = "analytics/discover.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        affinity_user_ids = UserAffinity.objects.filter(user=self.request.user).values_list('affinity_user_id', flat=True)
        liked_photo_ids = self.request.user.likes.values_list('photo_id', flat=True)
        
        # Photos liked by similar users, not yet liked by current user
        recommended_photos = Photo.objects.filter(
            likes__user_id__in=affinity_user_ids
        ).exclude(
            id__in=liked_photo_ids
        ).distinct()
        
        # Populate liked_by_current_user for consistency with _photo_card
        photo_list = list(recommended_photos)
        for photo in photo_list:
            photo.liked_by_current_user = False

        context["photos"] = photo_list
        return context


class MoodsView(TemplateView):
    template_name = "analytics/moods.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        moods_data = []
        for mood_val, mood_label in Photo.MOOD_CHOICES:
            photos = Photo.objects.filter(mood=mood_val)
            if photos.exists():
                photo_list = list(photos)
                if self.request.user.is_authenticated:
                    liked_photo_ids = Photo.liked_ids_for(self.request.user, photo_list)
                    for photo in photo_list:
                        photo.liked_by_current_user = photo.id in liked_photo_ids
                else:
                    for photo in photo_list:
                        photo.liked_by_current_user = False
                moods_data.append({
                    "label": mood_label,
                    "photos": photo_list
                })
        context["moods_data"] = moods_data
        return context


class SocialView(LoginRequiredMixin, TemplateView):
    template_name = "analytics/social.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        affinities = UserAffinity.objects.filter(user=self.request.user).select_related("affinity_user").order_by("-score")
        context["affinities"] = affinities
        return context

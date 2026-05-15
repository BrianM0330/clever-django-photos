from django.conf import settings
from django.db import models


class UserAffinity(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="user_affinities")
    affinity_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    score = models.FloatField()

    class Meta:
        db_table = "user_affinities"
        ordering = ["-score", "user_id", "affinity_user_id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "affinity_user"], name="uniq_user_affinity"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} -> {self.affinity_user_id} ({self.score:.3f})"

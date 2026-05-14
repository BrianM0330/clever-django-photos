from django.urls import path

from .views import AccountLoginView, AccountLogoutView, SignupView

app_name = "accounts"

urlpatterns = [
    path("login/", AccountLoginView.as_view(), name="login"),
    path("logout/", AccountLogoutView.as_view(), name="logout"),
    path("signup/", SignupView.as_view(), name="signup"),
]

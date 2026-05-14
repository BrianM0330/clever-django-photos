from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
from django.views.generic import CreateView

from .forms import SignupForm


class AccountLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field in form.fields.values():
            field.widget.attrs.update(
                {
                    "class": "block w-full rounded-xl border border-zinc-300 bg-white px-4 py-3 text-zinc-950 shadow-sm transition focus:border-clever-500 focus:outline-none focus:ring-2 focus:ring-clever-500/20 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white",
                }
            )
        return form


class AccountLogoutView(LogoutView):
    next_page = reverse_lazy("core:landing")


class SignupView(CreateView):
    form_class = SignupForm
    template_name = "accounts/signup.html"
    success_url = settings.LOGIN_REDIRECT_URL

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response

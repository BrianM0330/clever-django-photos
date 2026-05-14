from django.contrib.auth.forms import UserCreationForm


class SignupForm(UserCreationForm):
    """Stock signup form with project-level template styling hooks."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update(
                {
                    "class": "block w-full rounded-xl border border-zinc-300 bg-white px-4 py-3 text-zinc-950 shadow-sm transition focus:border-clever-500 focus:outline-none focus:ring-2 focus:ring-clever-500/20 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white",
                }
            )

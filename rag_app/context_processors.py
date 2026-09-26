"""Template context processors exposing feature flags to the UI.

Upload entry points (sidebar button, welcome "Upload First Document",
command-bar attach button) are only rendered when ``UPLOADS_ENABLED`` is
on. The setting defaults to off so a deployed Space never exposes an
upload path that the deployment plan deliberately defers.
"""

from django.conf import settings


def feature_flags(request):
    return {
        'uploads_enabled': settings.UPLOADS_ENABLED,
    }

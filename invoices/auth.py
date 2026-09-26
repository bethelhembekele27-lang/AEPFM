from datetime import timedelta

from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import TokenActivity

IDLE_TIMEOUT = timedelta(hours=12)


class ExpiringTokenAuthentication(TokenAuthentication):
    """
    Same as DRF's TokenAuthentication, plus sliding idle-expiry: a token
    unused for IDLE_TIMEOUT is rejected and deleted, forcing re-login.
    Any authenticated request resets the idle clock, so an actively working
    user is never logged out mid-session — only a token left sitting unused
    (stolen, or an abandoned browser tab) eventually stops working.

    Login is unchanged: it still get_or_creates the same Token row, and the
    first authenticated request creates the matching TokenActivity row.
    """

    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)

        activity, _ = TokenActivity.objects.get_or_create(token_key=token.key)
        if timezone.now() - activity.lastUsed > IDLE_TIMEOUT:
            token.delete()
            activity.delete()
            raise AuthenticationFailed('Session expired. Please log in again.')

        # Set the timestamp explicitly rather than relying on auto_now, so the
        # bump is visible at the call site and testable without save-time magic.
        activity.lastUsed = timezone.now()
        activity.save(update_fields=['lastUsed'])
        return user, token

from django.http import JsonResponse


def health_check(request):
    """
    GET /health/ — liveness probe for Render and uptime monitoring.

    Deliberately unauthenticated and deliberately trivial: a monitor should
    be able to reach it without credentials, and it must not touch the
    database or any provider, so a dependency outage doesn't get reported as
    "the app is down" when only a third party is. It answers "is this
    process serving requests", nothing more.
    """
    return JsonResponse({'status': 'ok'})

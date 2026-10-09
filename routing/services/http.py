import requests
from django.conf import settings

_session = requests.Session()
_session.headers["User-Agent"] = settings.HTTP_USER_AGENT


class ExternalServiceError(Exception):
    """A third-party API (routing/geocoding) failed or returned something unusable."""


def get_json(url, params=None):
    try:
        resp = _session.get(url, params=params, timeout=settings.HTTP_TIMEOUT_SECONDS)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise ExternalServiceError(f"Request to {url} failed: {exc}") from exc

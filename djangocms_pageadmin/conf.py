from django.conf import settings


PAGEADMIN_LIVE_URL_QUERY_PARAM_NAME = getattr(
    settings, "DJANGOCMS_PAGEADMIN_LIVE_URL_QUERY_PARAM_NAME", "live-URL"
)

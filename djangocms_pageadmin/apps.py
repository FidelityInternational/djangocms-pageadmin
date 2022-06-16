from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PageAdminConfig(AppConfig):
    name = "djangocms_pageadmin"
    verbose_name = _("django CMS Pages")

    def ready(self):
        import djangocms_pageadmin.monkeypatch  # noqa: F401

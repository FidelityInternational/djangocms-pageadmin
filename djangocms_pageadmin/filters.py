from django.conf import settings
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from cms.utils import get_current_site
from cms.utils.conf import get_cms_setting
from cms.utils.i18n import get_language_tuple, get_site_language_from_request

from djangocms_versioning.constants import UNPUBLISHED


class LanguageFilter(admin.SimpleListFilter):
    title = _("language")
    parameter_name = "language"

    def lookups(self, request, model_admin):
        return get_language_tuple()

    def queryset(self, request, queryset):
        language = self.value()
        if language is None:
            language = get_site_language_from_request(request)
        return queryset.filter(language=language)

    def choices(self, changelist):
        yield {
            "selected": self.value() is None,
            "query_string": changelist.get_query_string(remove=[self.parameter_name]),
            "display": _("Current"),
        }
        for lookup, title in self.lookup_choices:
            yield {
                "selected": self.value() == str(lookup),
                "query_string": changelist.get_query_string(
                    {self.parameter_name: lookup}
                ),
                "display": title,
            }


class UnpublishedFilter(admin.SimpleListFilter):
    title = _("unpublished")
    parameter_name = "unpublished"

    def lookups(self, request, model_admin):
        return (("1", _("Show")),)

    def queryset(self, request, queryset):
        show = self.value()
        if show == "1":
            return queryset.filter(versions__state=UNPUBLISHED)
        else:
            return queryset.exclude(versions__state=UNPUBLISHED)

    def choices(self, changelist):
        yield {
            "selected": self.value() is None,
            "query_string": changelist.get_query_string(remove=[self.parameter_name]),
            "display": _("Hide"),
        }
        for lookup, title in self.lookup_choices:
            yield {
                "selected": self.value() == str(lookup),
                "query_string": changelist.get_query_string(
                    {self.parameter_name: lookup}
                ),
                "display": title,
            }


class TemplateFilter(admin.SimpleListFilter):
    title = _("template")
    parameter_name = "template"

    def lookups(self, request, model_admin):
        site = get_current_site()
        site_templates = getattr(settings, "SITE_TEMPLATES", {})
        templates = site_templates.get(site.domain, None)
        if templates:
            return templates
        else:
            return get_cms_setting('TEMPLATES')

    def queryset(self, request, queryset):
        template = self.value()
        if not template:
            return queryset
        return queryset.filter(template=template)

    def choices(self, changelist):
        yield {
            "selected": self.value() is None,
            "query_string": changelist.get_query_string(remove=[self.parameter_name]),
            "display": _("All"),
        }
        for lookup, title in self.lookup_choices:
            yield {
                "selected": self.value() == str(lookup),
                "query_string": changelist.get_query_string(
                    {self.parameter_name: lookup}
                ),
                "display": title,
            }

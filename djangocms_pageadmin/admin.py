from django.contrib import admin
from django.contrib.sites.shortcuts import get_current_site
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.translation import ugettext_lazy as _

from cms.toolbar.utils import get_object_edit_url, get_object_preview_url
from cms.utils.i18n import get_language_tuple, get_site_language_from_request

from djangocms_versioning.constants import DRAFT
from djangocms_versioning.helpers import version_list_url
from djangocms_versioning.models import Version

from djangocms_version_locking.helpers import version_is_locked

from .helpers import original_model, proxy_model
from .models import PageContent


class LanguageFilter(admin.SimpleListFilter):
    title = _('language')
    parameter_name = 'language'

    def lookups(self, request, model_admin):
        return get_language_tuple()

    def queryset(self, request, queryset):
        language = self.value()
        if language is None:
            language = get_site_language_from_request(request)
        return queryset.filter(language=language)

    def choices(self, changelist):
        yield {
            'selected': self.value() is None,
            'query_string': changelist.get_query_string(remove=[self.parameter_name]),
            'display': _('Current'),
        }
        for lookup, title in self.lookup_choices:
            yield {
                'selected': self.value() == str(lookup),
                'query_string': changelist.get_query_string({self.parameter_name: lookup}),
                'display': title,
            }


class PageContentAdmin(admin.ModelAdmin):
    list_filter = (
        LanguageFilter,
    )
    search_fields = (
        'title',
    )

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            page__node__site=get_current_site(request),
        )

    def get_version(self, obj):
        return Version.objects.get_for_content(original_model(obj))

    def state(self, obj):
        version = self.get_version(obj)
        return version.get_state_display()
    state.short_description = _('state')

    def author(self, obj):
        version = self.get_version(obj)
        return version.created_by
    author.short_description = _('author')

    def lock(self, obj):
        version = self.get_version(obj)
        return getattr(version, 'versionlock', False)
    lock.short_description = _('lock')

    def locked(self, obj):
        version = self.get_version(obj)
        if version.state == DRAFT and version_is_locked(version):
            return render_to_string('djangocms_version_locking/admin/locked_icon.html')
        return ''
    locked.short_description = _('locked')

    def modified_date(self, obj):
        version = self.get_version(obj)
        return version.modified
    modified_date.short_description = _('modified date')

    def get_list_actions(self):
        return [
            self._get_preview_link,
            self._get_edit_link,
            self._get_duplicate_link,
            self._get_unpublish_link,
            self._get_manage_versions_link,
            self._get_basic_settings_link,
            self._get_advanced_settings_link,
        ]

    def _get_preview_link(self, obj, request, disabled=False):
        return render_to_string(
            'djangocms_pageadmin/admin/icons/preview.html',
            {
                'url': get_object_preview_url(obj),
                'disabled': disabled,
            }
        )

    def _get_edit_link(self, obj, request, disabled=False):
        version = self.get_version(obj)

        if version.state != DRAFT:
            # Don't display the link if it can't be edited
            return ''

        if not version.can_be_archived() or not version.check_archive.as_bool(request.user):
            disabled = True

        return render_to_string(
            'djangocms_pageadmin/admin/icons/edit.html',
            {
                'url': get_object_edit_url(obj),
                'disabled': disabled,
            }
        )

    def _get_duplicate_link(self, obj, request, disabled=False):
        # duplicate_url = reverse('admin:{app}_{model}_duplicate'.format(
        #     app=obj._meta.app_label, model=obj._meta.model_name,
        # ), args=(obj.pk,))

        return render_to_string(
            'djangocms_pageadmin/admin/icons/duplicate.html',
            {
                # 'url': duplicate_url,
                'disabled': disabled,
            }
        )

    def _get_unpublish_link(self, obj, request, disabled=False):
        version = proxy_model(self.get_version(obj))

        if not version.can_be_unpublished():
            # Don't display the link if it can't be unpublished
            return ''

        unpublish_url = reverse('admin:{app}_{model}_unpublish'.format(
            app=version._meta.app_label, model=version._meta.model_name,
        ), args=(version.pk,))

        if not version.can_be_unpublished() or not version.check_unpublish.as_bool(request.user):
            disabled = True

        return render_to_string(
            'djangocms_pageadmin/admin/icons/unpublish.html',
            {
                'url': unpublish_url,
                'disabled': disabled,
            }
        )

    def _get_manage_versions_link(self, obj, request, disabled=False):
        url = version_list_url(original_model(obj))
        return render_to_string(
            'djangocms_pageadmin/admin/icons/manage_versions.html',
            {
                'url': url,
                'disabled': disabled,
                'action': False,
            }
        )

    def _get_basic_settings_link(self, obj, request, disabled=False):
        url = reverse('admin:cms_pagecontent_change', args=(obj.pk,))
        return render_to_string(
            'djangocms_pageadmin/admin/icons/basic_settings.html',
            {
                'url': url,
                'disabled': disabled,
                'action': False,
            }
        )

    def _get_advanced_settings_link(self, obj, request, disabled=False):
        url = reverse('admin:cms_page_advanced', args=(obj.page_id,))
        return render_to_string(
            'djangocms_pageadmin/admin/icons/advanced_settings.html',
            {
                'url': url,
                'disabled': disabled,
                'action': False,
            }
        )

    def _list_actions(self, request):
        def list_actions(obj):
            """Display links to state change endpoints
            """
            return format_html_join(
                '',
                '{}',
                ((action(obj, request), ) for action in self.get_list_actions()),
            )
        list_actions.short_description = _('actions')
        return list_actions

    def get_list_display(self, request):
        return [
            'title',
            'author',
            'locked',
            'state',
            'modified_date',
            self._list_actions(request),
        ]

    def add_view(self, request, menu_content_id=None, form_url="", extra_context=None):
        return redirect(reverse('admin:cms_pagecontent_add'))

    def change_view(self, request, object_id, form_url='', extra_context=None):
        return redirect(reverse('admin:cms_pagecontent_change', args=(object_id, )))

    class Media:
        js = ('djangocms_pageadmin/js/actions.js',)
        css = {
            'all': ('djangocms_pageadmin/css/actions.css',)
        }

admin.site.register(PageContent, PageContentAdmin)

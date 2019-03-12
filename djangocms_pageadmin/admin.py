from django.conf.urls import url
from django.contrib import admin
from django.contrib.admin.utils import unquote
from django.contrib.sites.shortcuts import get_current_site
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.translation import ugettext_lazy as _

from cms import api
from cms.admin.pageadmin import PageContentAdmin as DefaultPageContentAdmin
from cms.extensions import extension_pool
from cms.models import PageContent
from cms.toolbar.utils import get_object_preview_url

from djangocms_version_locking.helpers import version_is_locked
from djangocms_versioning.admin import VersioningAdminMixin
from djangocms_versioning.constants import DRAFT, PUBLISHED
from djangocms_versioning.helpers import version_list_url
from djangocms_versioning.models import Version

from .filters import LanguageFilter, UnpublishedFilter
from .forms import DuplicateForm
from .helpers import proxy_model


class PageContentAdmin(VersioningAdminMixin, DefaultPageContentAdmin):
    change_list_template = "admin/djangocms_pageadmin/pagecontent/change_list.html"
    list_display_links = None
    list_filter = (LanguageFilter, UnpublishedFilter)
    search_fields = ("title",)

    def get_list_display(self, request):
        return [
            "title",
            "url",
            "author",
            "state",
            "modified_date",
            self._list_actions(request),
        ]

    def get_queryset(self, request):
        queryset = (
            super()
            .get_queryset(request)
            .filter(page__node__site=get_current_site(request))
        )
        return queryset.prefetch_related("versions")

    def get_version(self, obj):
        return Version.objects.get_for_content(obj)

    def state(self, obj):
        version = self.get_version(obj)
        return version.get_state_display()

    state.short_description = _("state")

    def url(self, obj):
        path = obj.page.get_path(obj.language)
        if path is not None:
            url = obj.page.get_absolute_url(obj.language)
            formatted_url = format_html('<a href="{url}">{url}</a>', url=url)
            lock = self.locked(obj)
            return lock + formatted_url

    url.short_description = _("url")

    def author(self, obj):
        version = self.get_version(obj)
        return version.created_by

    author.short_description = _("author")
    author.admin_order_field = "versions__author"

    def locked(self, obj):
        version = self.get_version(obj)
        if version.state == DRAFT and version_is_locked(version):
            return render_to_string("djangocms_version_locking/admin/locked_icon.html")
        return ""

    def modified_date(self, obj):
        version = self.get_version(obj)
        return version.modified

    modified_date.short_description = _("modified date")
    modified_date.admin_order_field = "versions__modified"

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
            "djangocms_pageadmin/admin/icons/preview.html",
            {"url": get_object_preview_url(obj), "disabled": disabled},
        )

    def _get_edit_link(self, obj, request, disabled=False):
        version = proxy_model(self.get_version(obj))

        if version.state not in (DRAFT, PUBLISHED):
            # Don't display the link if it can't be edited
            return ""

        if not version.check_edit_redirect.as_bool(request.user):
            disabled = True

        url = reverse(
            "admin:{app}_{model}_edit_redirect".format(
                app=version._meta.app_label, model=version._meta.model_name
            ),
            args=(version.pk,),
        )

        return render_to_string(
            "djangocms_pageadmin/admin/icons/edit.html",
            {"url": url, "disabled": disabled, "get": False},
        )

    def _get_duplicate_link(self, obj, request, disabled=False):
        url = reverse(
            "admin:{app}_{model}_duplicate_content".format(
                app=self.model._meta.app_label, model=self.model._meta.model_name
            ),
            args=(obj.pk,),
        )

        return render_to_string(
            "djangocms_pageadmin/admin/icons/duplicate.html",
            {"url": url, "disabled": disabled},
        )

    def _get_unpublish_link(self, obj, request, disabled=False):
        version = proxy_model(self.get_version(obj))

        if not version.can_be_unpublished():
            # Don't display the link if it can't be unpublished
            return ""

        url = reverse(
            "admin:{app}_{model}_unpublish".format(
                app=version._meta.app_label, model=version._meta.model_name
            ),
            args=(version.pk,),
        )

        if not version.can_be_unpublished() or not version.check_unpublish.as_bool(
            request.user
        ):
            disabled = True

        return render_to_string(
            "djangocms_pageadmin/admin/icons/unpublish.html",
            {"url": url, "disabled": disabled},
        )

    def _get_manage_versions_link(self, obj, request, disabled=False):
        url = version_list_url(obj)
        return render_to_string(
            "djangocms_pageadmin/admin/icons/manage_versions.html",
            {"url": url, "disabled": disabled, "action": False},
        )

    def _get_basic_settings_link(self, obj, request, disabled=False):
        url = reverse("admin:cms_pagecontent_change", args=(obj.pk,))
        return render_to_string(
            "djangocms_pageadmin/admin/icons/basic_settings.html",
            {"url": url, "disabled": disabled, "action": False},
        )

    def _get_advanced_settings_link(self, obj, request, disabled=False):
        url = reverse("admin:cms_page_advanced", args=(obj.page_id,))
        return render_to_string(
            "djangocms_pageadmin/admin/icons/advanced_settings.html",
            {"url": url, "disabled": disabled, "action": False},
        )

    def _list_actions(self, request):
        def list_actions(obj):
            """Display links to state change endpoints
            """
            return format_html_join(
                "",
                "{}",
                ((action(obj, request),) for action in self.get_list_actions()),
            )

        list_actions.short_description = _("actions")
        return list_actions

    def changelist_view(self, request, extra_context=None):
        return admin.ModelAdmin.changelist_view(self, request, extra_context)

    def duplicate_view(self, request, object_id):
        obj = self.get_object(request, unquote(object_id))
        if obj is None:
            return self._get_obj_does_not_exist_redirect(
                request, self.model._meta, object_id
            )

        form = DuplicateForm(
            user=request.user,
            page_content=obj,
            initial={
                "site": obj.page.node.site,
                "slug": obj.page.get_slug(obj.language),
            },
        )
        info = (self.model._meta.app_label, self.model._meta.model_name)
        if request.method == "POST":
            form = DuplicateForm(request.POST, user=request.user, page_content=obj)
            if form.is_valid():
                new_page = obj.page.copy(
                    site=form.cleaned_data["site"],
                    parent_node=obj.page.node.parent,
                    translations=False,
                    permissions=False,
                    extensions=False,
                )

                new_page_content = api.create_title(
                    page=new_page,
                    language=obj.language,
                    slug=form.cleaned_data["slug"],
                    path=form.cleaned_data["path"],
                    title=obj.title,
                    template=obj.template,
                    created_by=request.user,
                )
                new_page.title_cache[obj.language] = new_page_content

                extension_pool.copy_extensions(
                    source_page=obj.page, target_page=new_page, languages=[obj.language]
                )

                placeholders = obj.get_placeholders()
                for source_placeholder in placeholders:
                    target_placeholder = new_page_content.placeholders.get(
                        slot=source_placeholder.slot
                    )
                    source_placeholder.copy_plugins(
                        target_placeholder, language=obj.language
                    )

                self.message_user(request, _("Page has been duplicated"))
                return redirect(reverse("admin:{}_{}_changelist".format(*info)))

        context = dict(
            obj=obj,
            form=form,
            object_id=object_id,
            duplicate_url=reverse(
                "admin:{}_{}_duplicate_content".format(*info), args=(obj.pk,)
            ),
            back_url=reverse("admin:{}_{}_changelist".format(*info)),
        )
        return render(
            request, "djangocms_pageadmin/admin/duplicate_confirmation.html", context
        )

    def get_urls(self):
        info = self.model._meta.app_label, self.model._meta.model_name
        return [
            url(
                r"^(.+)/duplicate-content/$",
                self.admin_site.admin_view(self.duplicate_view),
                name="{}_{}_duplicate_content".format(*info),
            )
        ] + super().get_urls()

    class Media:
        css = {"all": ("djangocms_pageadmin/css/actions.css",)}


admin.site.unregister(PageContent)
admin.site.register(PageContent, PageContentAdmin)

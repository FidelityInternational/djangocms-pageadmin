import csv
import datetime

from django.contrib import admin
from django.contrib.admin.utils import unquote
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import OuterRef, Prefetch, Q, Subquery
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
)
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import re_path, reverse
from django.utils.decorators import method_decorator
from django.utils.html import format_html, format_html_join
from django.utils.translation import get_language, gettext_lazy as _, override
from django.views.decorators.http import require_POST

from cms import api
from cms.admin.pageadmin import PageContentAdmin as DefaultPageContentAdmin
from cms.extensions import extension_pool
from cms.models import PageContent, PageUrl
from cms.signals.apphook import set_restart_trigger
from cms.toolbar.utils import get_object_preview_url

from djangocms_version_locking.helpers import version_is_locked
from djangocms_version_locking.models import VersionLock
from djangocms_versioning.admin import VersioningAdminMixin
from djangocms_versioning.constants import DRAFT, PUBLISHED
from djangocms_versioning.helpers import version_list_url
from djangocms_versioning.models import Version

from .filters import (
    AuthorFilter,
    LanguageFilter,
    TemplateFilter,
    UnpublishedFilter,
)
from .forms import DuplicateForm
from .helpers import is_moderation_enabled, proxy_model


try:
    from django.utils.html import force_str
except ImportError:
    from django.utils.encoding import force_str


require_POST = method_decorator(require_POST)


class PageContentAdmin(VersioningAdminMixin, DefaultPageContentAdmin):
    change_list_template = "admin/djangocms_pageadmin/pagecontent/change_list.html"
    list_display_links = None
    list_filter = (LanguageFilter, UnpublishedFilter, TemplateFilter, AuthorFilter)
    _list_display = [
        "get_title",
        "url",
        "author",
        "state",
        "modified_date",
    ]
    ordering = ['-versions__modified']
    search_fields = ("title",)

    def get_list_display(self, request):
        return self._list_display + [self._list_actions(request)]

    def get_queryset(self, request):
        """Filter PageContent objects by current site of the request.
        """
        url_subquery = PageUrl.objects.filter(
            language=OuterRef("language"), page=OuterRef("page")
        )
        # Collect locked status to handle the requirement that lock
        # on a draft version dictates the unpublish permission
        # on a published version
        draft_version_lock_subquery = VersionLock.objects.filter(
            version__content_type=OuterRef("content_type"),
            version__object_id=OuterRef("object_id"),
            version__state=DRAFT,
        ).order_by("-pk")
        queryset = (
            super()
            .get_queryset(request)
            .filter(page__node__site=get_current_site(request))
            .annotate(_path=Subquery(url_subquery.values("path")[:1]))
        )
        return queryset.select_related("page").prefetch_related(
            Prefetch(
                "versions",
                queryset=Version.objects.annotate(
                    # used by locking
                    _draft_version_user_id=Subquery(
                        draft_version_lock_subquery.values("created_by")[:1]
                    )
                )
                .select_related("created_by", "versionlock")
                .prefetch_related("content"),
            )
        )

    def get_actions(self, request):
        """
        If djangocms-moderation is enabled, adds admin action to allow multiple pages to be added to a moderation
        collection.

        :param request: Request object
        :returns: dict of admin actions
        """
        actions = super().get_actions(request)
        if not is_moderation_enabled():
            return actions

        from djangocms_moderation.admin_actions import \
            add_items_to_collection  # noqa

        actions["add_items_to_collection"] = (
            add_items_to_collection,
            "add_items_to_collection",
            add_items_to_collection.short_description
        )
        return actions

    def get_search_results(self, request, queryset, search_term):
        """
        Override the ModelAdmin method for fetching search results to filter for urls associated with the pagecontent
        :param request: PageContent Admin request
        :param queryset: PageContent queryset
        :param search_term: Term to be searched for
        :return: results
        """
        language = get_language()
        returned_queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        """
        While the returned_queryset contains searches for title, without filtering on the original, we are unable to
        search for symbols within the URL, such as '-'. Therefore, filter the original queryset and combine.
        Language must also be filtered in order to prevent hits on PageContent which have URLS in multiple languages.
        """
        returned_queryset |= queryset.filter(
            Q(page__urls__slug__icontains=search_term) | Q(page__urls__path__icontains=search_term),
            page__urls__language=language
        )

        """
        This is a workaround to avoid replicating the functionality of get_search_results in Django, which checks
        whether a queryset is distinct based on search_fields. We cannot use the standard search_fields configuration,
        because this would not be language aware, and would results in hits on URLs in languages different to the users.
        As we are looking across reverse FK relations, we know that this method should always return use_distinct=True,
        therefore if a search has been made, set it as such.
        https://github.com/django/django/blob/2a62cdcfec85938f40abb2e9e6a9ff497e02afe8/django/contrib/admin/options.py#L980 # NOQA
        """
        if search_term:
            use_distinct = True
        return returned_queryset, use_distinct

    def get_version(self, obj):
        return obj.versions.all()[0]

    def state(self, obj):
        version = self.get_version(obj)
        return version.get_state_display()

    state.short_description = _("state")

    def url(self, obj, csv=False):
        path = obj._path
        url = None
        with override(obj.language):
            if obj.page.is_home:
                url = reverse("pages-root")
            if path:
                url = reverse("pages-details-by-slug", kwargs={"slug": path})
        if url is not None and csv is False:
            return format_html('<a class="js-page-admin-close-sideframe" href="{url}">{url}</a>', url=url)
        return url

    url.short_description = _("url")

    def get_title(self, obj):
        return format_html(
            "{home}{lock}{title}",
            home=self.is_home(obj),
            lock=self.is_locked(obj),
            title=obj.title,
        )

    get_title.short_description = _("title")

    def author(self, obj):
        version = self.get_version(obj)
        return version.created_by

    author.short_description = _("author")
    author.admin_order_field = "versions__created_by"

    def is_locked(self, obj):
        version = self.get_version(obj)
        if version.state == DRAFT and version_is_locked(version):
            return render_to_string("djangocms_version_locking/admin/locked_icon.html")
        return ""

    def is_home(self, obj):
        if obj.page.is_home:
            return render_to_string("djangocms_pageadmin/admin/icons/home.html")
        return ""

    def modified_date(self, obj):
        version = self.get_version(obj)
        return version.modified

    modified_date.short_description = _("modified date")
    modified_date.admin_order_field = "versions__modified"

    def get_list_actions(self):
        return [
            self._set_home_link,
            self._get_preview_link,
            # CAVEAT : get_edit_link Commented out to hide edit link from change list
            # Edit page content can be accessed from preview
            # Below line should be uncommented  change is added to open the edit link new tab
            # self._get_edit_link,
            self._get_duplicate_link,
            self._get_unpublish_link,
            self._get_manage_versions_link,
            self._get_basic_settings_link,
            self._get_advanced_settings_link,
        ]

    def _get_preview_link(self, obj, request, disabled=False):
        return render_to_string(
            "djangocms_pageadmin/admin/icons/preview.html",
            {"url": get_object_preview_url(obj), "disabled": disabled, "keepsideframe": False},
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
            "admin:{app}_{model}_duplicate".format(
                app=self.model._meta.app_label, model=self.model._meta.model_name
            ),
            args=(obj.pk,),
        )

        return render_to_string(
            "djangocms_pageadmin/admin/icons/duplicate.html",
            {"url": url, "disabled": disabled},
        )

    def _set_home_link(self, obj, request, disabled=False):

        if obj.page.is_home:
            return ""

        url = reverse(
            "admin:{app}_{model}_set_home_content".format(
                app=self.model._meta.app_label, model=self.model._meta.model_name
            ),
            args=(obj.pk,),
        )

        return render_to_string(
            "djangocms_pageadmin/admin/icons/set_home.html",
            {"url": url, "disabled": disabled, "action": True, "get": False},
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
        """A closure that makes it possible to pass request object to
        list action button functions.
        """

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
        """Ignore default cms' implementation and use ModelAdmin instead.
        """
        # The standard Pages menu for the PageContent model as provided by the CMS returns a selected item.
        # This works because that view has no filters. PageAdmin has filters, so this causes unwanted filtering.
        # We remove the page_id before calling onto the changelist view. We may in future want to use the parameter
        # so we remove it before initiating the standard Django changelist view.
        if 'page_id' in request.GET:
            request.GET = request.GET.copy()
            del (request.GET['page_id'])

        return admin.ModelAdmin.changelist_view(self, request, extra_context)

    @transaction.atomic
    def duplicate_view(self, request, object_id):
        """Duplicate a specified PageContent.

        Create a new page with content copied from provided PageContent.

        :param request: Http request
        :param object_id: PageContent ID (as a string)
        """
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
                    # Keep all placeholders even if they are not in the template anymore to ensure the data is kept,
                    # keeping only placeholders from rescanning the template would not keep any legacy content
                    # which could in theory be remapped repaired at a later date
                    target_placeholder, created = new_page_content.placeholders.get_or_create(
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
                "admin:{}_{}_duplicate".format(*info), args=(obj.pk,)
            ),
            back_url=reverse("admin:{}_{}_changelist".format(*info)),
        )
        return render(
            request, "djangocms_pageadmin/admin/duplicate_confirmation.html", context
        )

    @require_POST
    @transaction.atomic
    def set_home_view(self, request, object_id):
        page_content = self.get_object(request, object_id=unquote(object_id))

        if page_content is None:
            raise self._get_404_exception(object_id)

        page = page_content.page
        if not page.has_change_permission(request.user):
            raise PermissionDenied("You do not have permission to set 'home'.")

        if not page.is_potential_home():
            return HttpResponseBadRequest(
                force_str(_("The page is not eligible to be home."))
            )

        new_home_tree, old_home_tree = page.set_as_homepage(request.user)

        # Check if one of the affected pages either from the old homepage
        # or the homepage had an apphook attached
        if old_home_tree:
            apphooks_affected = old_home_tree.has_apphooks()
        else:
            apphooks_affected = False

        if not apphooks_affected:
            apphooks_affected = new_home_tree.has_apphooks()

        if apphooks_affected:
            # One or more pages affected by this operation was attached to an apphook.
            # As a result, fire the apphook reload signal to reload the url patterns.
            set_restart_trigger()

        info = (self.model._meta.app_label, self.model._meta.model_name)
        return HttpResponseRedirect(reverse("admin:{}_{}_changelist".format(*info)))

    def get_urls(self):
        info = self.model._meta.app_label, self.model._meta.model_name
        # we replace the duplicate with our function.
        old_urls = [v for v in super().get_urls() if 'duplicate' not in str(v.name)]
        new_urls = [
            re_path(
                r"^(.+)/duplicate-content/$",
                self.admin_site.admin_view(self.duplicate_view),
                name="{}_{}_duplicate".format(*info),
            ),
            re_path(
                r"^(.+)/set-home-content/$",
                self.admin_site.admin_view(self.set_home_view),
                name="{}_{}_set_home_content".format(*info),
            ),
            re_path(
                r'^export_csv/$',
                self.admin_site.admin_view(self.export_to_csv),
                name="{}_{}_export_csv".format(*info),
            ),
        ]
        return new_urls + old_urls

    def _format_export_datetime(self, date):
        """
        date: DateTime object
        date_format: String, date time string format for strftime

        Returns a formatted human readable date time string
        """
        if isinstance(date, datetime.date):
            return date.strftime("%Y/%m/%d %H:%M %z")
        return ""

    def export_to_csv(self, request):
        """
        Retrieves the queryset and exports to csv format
        """
        queryset = self.get_exported_queryset(request)
        meta = self.model._meta
        field_names = ['Title', 'Expiry Date', 'Version State', 'Version Author', 'Url',
                       'Compliance Number']
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename={}.csv'.format(meta)
        writer = csv.writer(response)
        writer.writerow(field_names)
        for obj in queryset:
            title = obj.title
            expiry_date = self._format_export_datetime(self.get_expiry_date(obj))
            version_state = self.state(obj)
            version_author = self.author(obj)
            url = self.url(obj, True)
            compliance_number = self.get_compliance_number(obj)
            writer.writerow([title, expiry_date, version_state, version_author, url, compliance_number])

        return response

    def get_expiry_date(self, obj):
        version = self.get_version(obj)
        if hasattr(version, "contentexpiry"):
            return version.contentexpiry.expires
        return ""

    def get_compliance_number(self, obj):
        version = self.get_version(obj)
        if hasattr(version, "contentexpiry"):
            return version.contentexpiry.compliance_number
        return ""

    def get_exported_queryset(self, request):
        """
        Returns export queryset by respecting applied filters.
        """
        list_display = self.get_list_display(request)
        list_display_links = self.get_list_display_links(request, list_display)
        list_filter = self.get_list_filter(request)
        search_fields = self.get_search_fields(request)
        changelist = self.get_changelist(request)

        changelist_kwargs = {
            'request': request,
            'model': self.model,
            'list_display': list_display,
            'list_display_links': list_display_links,
            'list_filter': list_filter,
            'date_hierarchy': self.date_hierarchy,
            'search_fields': search_fields,
            'list_select_related': self.list_select_related,
            'list_per_page': self.list_per_page,
            'list_max_show_all': self.list_max_show_all,
            'list_editable': self.list_editable,
            'model_admin': self,
            'sortable_by': self.sortable_by
        }
        cl = changelist(**changelist_kwargs)

        return cl.get_queryset(request)

    class Media:
        css = {"all": ("djangocms_pageadmin/css/actions.css",)}


admin.site.unregister(PageContent)
admin.site.register(PageContent, PageContentAdmin)

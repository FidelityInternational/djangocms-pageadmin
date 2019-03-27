from functools import partial
from unittest.mock import patch

from django.contrib import admin
from django.contrib.sites.models import Site
from django.test import RequestFactory, TestCase, TransactionTestCase
from django.test.utils import override_settings
from django.urls import reverse

from cms.api import add_plugin, create_page
from cms.models import PageContent, PageUrl
from cms.test_utils.testcases import CMSTestCase
from cms.toolbar.toolbar import CMSToolbar
from cms.toolbar.utils import get_object_preview_url
from cms.toolbar_pool import toolbar_pool
from cms.utils import conf
from cms.utils.plugins import downcast_plugins
from menus.menu_pool import menu_pool

from bs4 import BeautifulSoup
from djangocms_versioning.constants import ARCHIVED, PUBLISHED, UNPUBLISHED
from djangocms_versioning.helpers import version_list_url

from djangocms_pageadmin.admin import PageContentAdmin
from djangocms_pageadmin.cms_toolbars import PageAdminToolbar
from djangocms_pageadmin.test_utils.factories import (
    PageContentWithVersionFactory,
    PageVersionFactory,
    PlaceholderFactory,
    SiteFactory,
    UserFactory,
)


parse_html = partial(BeautifulSoup, features="lxml")

def get_toolbar(content_obj, user=None, **kwargs):
    """
    Helper method to set up the toolbar
    Copied from djangocms-versioning.test_utils.test_helpers
    """
    # Set the user if none are sent
    if not user:
        user = UserFactory(is_staff=True)

    request = kwargs.get('request', RequestFactory().get('/'))
    request.user = user
    request.session = kwargs.get('session', {})
    request.current_page = getattr(content_obj, 'page', None)
    request.toolbar = CMSToolbar(request)
    # Set the toolbar class
    if kwargs.get('toolbar_class', False):
        toolbar_class = kwargs.get('toolbar_class')
    else:
        toolbar_class = VersioningToolbar
    toolbar = toolbar_class(
        request,
        toolbar=request.toolbar,
        is_current_app=True,
        app_path='/',
    )
    toolbar.toolbar.set_object(content_obj)
    # Set the toolbar mode
    if kwargs.get('edit_mode', False):
        toolbar.toolbar.edit_mode_active = True
        toolbar.toolbar.content_mode_active = False
        toolbar.toolbar.structure_mode_active = False
    elif kwargs.get('preview_mode', False):
        toolbar.toolbar.edit_mode_active = False
        toolbar.toolbar.content_mode_active = True
        toolbar.toolbar.structure_mode_active = False
    elif kwargs.get('structure_mode', False):
        toolbar.toolbar.edit_mode_active = False
        toolbar.toolbar.content_mode_active = False
        toolbar.toolbar.structure_mode_active = True
    toolbar.populate()
    return toolbar

class AdminTestCase(CMSTestCase):
    def test_changelist(self):
        model = PageContent
        with self.login_user_context(self.get_superuser()):
            response = self.client.get(self.get_admin_url(model, "changelist"))
        self.assertEqual(response.status_code, 200)

    def test_changelist_not_accessible_to_regular_users(self):
        model = PageContent
        with self.login_user_context(self.get_standard_user()):
            response = self.client.get(self.get_admin_url(model, "changelist"))
        self.assertRedirects(
            response, "/en/admin/login/?next=/en/admin/cms/pagecontent/"
        )


class FiltersTestCase(CMSTestCase):
    def test_queryset_is_filtered_by_current_site(self):
        site1 = SiteFactory()
        site2 = SiteFactory()
        site1_pagecontents = PageContentWithVersionFactory.create_batch(
            2, page__node__site=site1, language="en"
        )
        site2_pagecontents = [
            PageContentWithVersionFactory(page__node__site=site2, language="en")
        ]
        model = PageContent
        url = self.get_admin_url(model, "changelist")
        with self.login_user_context(self.get_superuser()):
            with self.settings(SITE_ID=site1.pk):
                response1 = self.client.get(url)
            with self.settings(SITE_ID=site2.pk):
                response2 = self.client.get(url)
        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(set(site1_pagecontents), set(response1.context["cl"].queryset))
        self.assertEqual(set(site2_pagecontents), set(response2.context["cl"].queryset))

    def test_language_filter(self):
        expected_en = PageContentWithVersionFactory.create_batch(3, language="en")
        expected_de = PageContentWithVersionFactory.create_batch(3, language="de")
        model = PageContent
        base_url = self.get_admin_url(model, "changelist")
        with self.login_user_context(self.get_superuser()):
            # en is the default language configured for the site
            response_default = self.client.get(base_url)
            qs_default = response_default.context["cl"].queryset
            response_en = self.client.get(base_url + "?language=en")
            qs_en = response_en.context["cl"].queryset
            response_de = self.client.get(base_url + "?language=de")
            qs_de = response_de.context["cl"].queryset

        self.assertEqual(set(qs_default), set(expected_en))
        self.assertEqual(set(qs_en), set(expected_en))
        self.assertEqual(set(qs_de), set(expected_de))

    def test_unpublished_filter(self):
        expected = PageContentWithVersionFactory.create_batch(3, language="en")
        expected_unpublished = PageContentWithVersionFactory.create_batch(
            2, language="en", version__state=UNPUBLISHED
        )
        model = PageContent
        base_url = self.get_admin_url(model, "changelist")
        with self.login_user_context(self.get_superuser()):
            # en is the default language configured for the site
            response_default = self.client.get(base_url)
            qs_default = response_default.context["cl"].queryset
            response_unpublished = self.client.get(base_url + "?unpublished=1")
            qs_unpublished = response_unpublished.context["cl"].queryset

        self.assertEqual(set(qs_default), set(expected))
        self.assertEqual(set(qs_unpublished), set(expected_unpublished))


class ListActionsTestCase(CMSTestCase):
    def setUp(self):
        self.modeladmin = admin.site._registry[PageContent]

    def test_preview_link(self):
        pagecontent = PageContentWithVersionFactory()
        func = self.modeladmin._list_actions(self.get_request("/"))
        response = func(pagecontent)
        soup = parse_html(response)
        element = soup.find("a", {"class": "cms-page-admin-action-preview"})
        self.assertIsNotNone(element, "Missing a.cms-page-admin-action-preview element")
        self.assertEqual(element["title"], "Preview")
        self.assertEqual(element["href"], get_object_preview_url(pagecontent))

    def test_edit_link(self):
        user = UserFactory()
        version = PageVersionFactory(created_by=user)
        pagecontent = version.content
        request = self.get_request("/")
        request.user = user
        func = self.modeladmin._list_actions(request)
        response = func(pagecontent)
        soup = parse_html(response)
        element = soup.find("a", {"class": "cms-page-admin-action-edit"})
        self.assertIsNotNone(element, "Missing a.cms-page-admin-action-edit element")
        self.assertEqual(element["title"], "Edit")
        self.assertEqual(
            element["href"],
            reverse(
                "admin:djangocms_versioning_pagecontentversion_edit_redirect",
                args=(version.pk,),
            ),
        )

    def test_edit_link_inactive(self):
        pagecontent = PageContentWithVersionFactory()
        func = self.modeladmin._list_actions(self.get_request("/"))
        response = func(pagecontent)
        soup = parse_html(response)
        element = soup.find("a", {"class": "cms-page-admin-action-edit"})
        self.assertIsNotNone(element, "Missing a.cms-page-admin-action-edit element")
        self.assertEqual(element["title"], "Edit")
        self.assertIn("inactive", element["class"])
        self.assertNotIn("href", element)

    def test_edit_link_not_shown(self):
        pagecontent = PageContentWithVersionFactory(version__state=ARCHIVED)
        func = self.modeladmin._list_actions(self.get_request("/"))
        response = func(pagecontent)
        soup = parse_html(response)
        element = soup.find("a", {"class": "cms-page-admin-action-edit"})
        self.assertIsNot(
            element, "Element a.cms-page-admin-action-edit is shown when it shouldn't"
        )

    def test_duplicate_link(self):
        version = PageVersionFactory(state=PUBLISHED)
        pagecontent = version.content
        func = self.modeladmin._list_actions(self.get_request("/"))
        response = func(pagecontent)
        soup = parse_html(response)
        element = soup.find("a", {"class": "cms-page-admin-action-duplicate"})
        self.assertIsNotNone(
            element, "Missing a.cms-page-admin-action-duplicate element"
        )
        self.assertEqual(element["title"], "Duplicate")
        self.assertEqual(
            element["href"],
            reverse("admin:cms_pagecontent_duplicate_content", args=(version.pk,)),
        )

    def test_set_home_link(self):
        version = PageVersionFactory(state=PUBLISHED)
        pagecontent = version.content
        func = self.modeladmin._list_actions(self.get_request("/"))
        response = func(pagecontent)
        soup = parse_html(response)
        element = soup.find("a", {"class": "cms-page-admin-action-set-home"})
        self.assertEqual(element["title"], "Set as a home")
        self.assertEqual(
            element["href"],
            reverse("admin:cms_pagecontent_set_home_content", args=(version.pk,)),
        )

    def test_unpublish_link(self):
        version = PageVersionFactory(state=PUBLISHED)
        pagecontent = version.content
        func = self.modeladmin._list_actions(self.get_request("/"))
        response = func(pagecontent)
        soup = parse_html(response)
        element = soup.find("a", {"class": "cms-page-admin-action-unpublish"})
        self.assertIsNotNone(
            element, "Missing a.cms-page-admin-action-unpublish element"
        )
        self.assertEqual(element["title"], "Unpublish")
        self.assertEqual(
            element["href"],
            reverse(
                "admin:djangocms_versioning_pagecontentversion_unpublish",
                args=(version.pk,),
            ),
        )

    def test_unpublish_not_shown(self):
        version = PageVersionFactory()
        pagecontent = version.content
        func = self.modeladmin._list_actions(self.get_request("/"))
        response = func(pagecontent)
        soup = parse_html(response)
        element = soup.find("a", {"class": "cms-page-admin-action-unpublish"})
        self.assertIsNone(
            element,
            "Element a.cms-page-admin-action-unpublish is shown when it shouldn't",
        )

    def test_manage_versions_link(self):
        pagecontent = PageContentWithVersionFactory()
        func = self.modeladmin._list_actions(self.get_request("/"))
        response = func(pagecontent)
        soup = parse_html(response)
        element = soup.find("a", {"class": "cms-page-admin-action-manage-versions"})
        self.assertIsNotNone(
            element, "Missing a.cms-page-admin-action-manage-versions element"
        )
        self.assertEqual(element["title"], "Manage versions")
        self.assertEqual(element["href"], version_list_url(pagecontent))

    def test_basic_settings_link(self):
        pagecontent = PageContentWithVersionFactory()
        func = self.modeladmin._list_actions(self.get_request("/"))
        response = func(pagecontent)
        soup = parse_html(response)
        element = soup.find("a", {"class": "cms-page-admin-action-basic-settings"})
        self.assertIsNotNone(
            element, "Missing a.cms-page-admin-action-basic-settings element"
        )
        self.assertEqual(element["title"], "Basic settings")
        self.assertEqual(
            element["href"],
            reverse("admin:cms_pagecontent_change", args=(pagecontent.pk,)),
        )

    def test_advanced_settings_link(self):
        pagecontent = PageContentWithVersionFactory()
        func = self.modeladmin._list_actions(self.get_request("/"))
        response = func(pagecontent)
        soup = parse_html(response)
        element = soup.find("a", {"class": "cms-page-admin-action-advanced-settings"})
        self.assertIsNotNone(
            element, "Missing a.cms-page-admin-action-advanced-settings element"
        )
        self.assertEqual(element["title"], "Advanced settings")
        self.assertEqual(
            element["href"],
            reverse("admin:cms_page_advanced", args=(pagecontent.page_id,)),
        )


class SetHomeViewTestCase(CMSTestCase):
    def test_get_method_is_not_allowed(self):
        pagecontent = PageContentWithVersionFactory()
        with self.login_user_context(self.get_superuser()):
            response = self.client.get(
                self.get_admin_url(PageContent, "set_home_content", pagecontent.pk)
            )
        pagecontent.page.refresh_from_db()
        self.assertEqual(response.status_code, 405)
        self.assertFalse(pagecontent.page.is_home)

    def test_root_page_is_allowed_to_set_home(self):
        version = PageVersionFactory(content__page__node__depth=1, state=PUBLISHED)
        pagecontent = version.content
        with self.login_user_context(self.get_superuser()):
            response = self.client.post(
                self.get_admin_url(PageContent, "set_home_content", pagecontent.pk)
            )
        url = reverse("admin:cms_pagecontent_changelist")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, url)

        pagecontent.page.refresh_from_db()
        self.assertTrue(pagecontent.page.is_home)

    def test_non_root_page_should_not_allowed_to_set_home(self):
        version = PageVersionFactory(content__page__node__depth=2, state=PUBLISHED)
        pagecontent = version.content
        with self.login_user_context(self.get_superuser()):
            response = self.client.post(
                self.get_admin_url(PageContent, "set_home_content", pagecontent.pk)
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.content.decode("utf-8"), "The page is not eligible to be home."
        )
        self.assertFalse(pagecontent.page.is_home)

    def test_non_existing_page_should_result_404(self):
        with self.login_user_context(self.get_superuser()):
            response = self.client.post(
                self.get_admin_url(PageContent, "set_home_content", 99)
            )
        self.assertEqual(response.status_code, 404)

    def test_permission_to_set_home_page(self):
        version = PageVersionFactory(content__page__node__depth=1, state=PUBLISHED)
        pagecontent = version.content
        with self.login_user_context(self.get_superuser()), patch(
            "cms.models.pagemodel.Page.has_change_permission", return_value=False
        ) as mock:
            response = self.client.post(
                self.get_admin_url(PageContent, "set_home_content", pagecontent.pk)
            )

        self.assertEqual(mock.call_count, 1)
        self.assertEqual(response.status_code, 403)

        pagecontent.page.refresh_from_db()
        self.assertFalse(pagecontent.page.is_home)

    def test_when_new_homepage_tree_has_apphooks_should_trigger_signal(self):
        PageVersionFactory(
            content__page__node__depth=1, content__page__is_home=1, state=PUBLISHED
        )
        version = PageVersionFactory(content__page__node__depth=1, state=PUBLISHED)
        to_be_homepage = version.content
        with self.login_user_context(self.get_superuser()), patch(
            "cms.models.query.PageQuerySet.has_apphooks", return_value=True
        ), patch("djangocms_pageadmin.admin.set_restart_trigger") as mock_handler:
            self.client.post(
                self.get_admin_url(PageContent, "set_home_content", to_be_homepage.pk)
            )
            mock_handler.assert_called_once_with()

    def test_when_old_homepage_tree_has_no_apphooks_shouldnt_trigger_signal(self):
        PageVersionFactory(
            content__page__node__depth=1, content__page__is_home=1, state=PUBLISHED
        )
        version = PageVersionFactory(content__page__node__depth=1, state=PUBLISHED)
        to_be_homepage = version.content
        with self.login_user_context(self.get_superuser()), patch(
            "djangocms_pageadmin.admin.set_restart_trigger"
        ) as mock_handler, patch(
            "cms.models.query.PageQuerySet.has_apphooks", return_value=False
        ):
            self.client.post(
                self.get_admin_url(PageContent, "set_home_content", to_be_homepage.pk)
            )

            mock_handler.assert_not_called()

    def test_when_old_home_tree_is_none_should_not_trigger_signal(self):
        version = PageVersionFactory(content__page__node__depth=1, state=PUBLISHED)
        pagecontent = version.content

        with self.login_user_context(self.get_superuser()), patch(
            "djangocms_pageadmin.admin.set_restart_trigger"
        ) as mock_handler:
            self.client.post(
                self.get_admin_url(PageContent, "set_home_content", pagecontent.pk)
            )

            mock_handler.assert_not_called()


class SetHomeViewTransactionTestCase(TransactionTestCase):
    def setUp(self):
        self.user = UserFactory(is_staff=True, is_superuser=True)
        # Login
        self.client.force_login(self.user)

    def test_set_home_is_wrapped_in_db_transaction(self):
        class FakeError(Exception):
            pass

        version = PageVersionFactory(content__page__node__depth=1, state=PUBLISHED)
        page_content = version.content

        # Asserting to make sure page is not set as homepage
        self.assertFalse(page_content.page.is_home)

        # Patching has_apphooks which is get called after setting home on view so transaction
        # should roll back in event of error
        with patch("cms.models.query.PageQuerySet.has_apphooks", side_effect=FakeError):
            try:
                self.client.post(
                    reverse(
                        "admin:cms_pagecontent_set_home_content", args=[page_content.pk]
                    )
                )
            except FakeError:
                pass

        # Refresh object from db
        page_content.page.refresh_from_db()
        self.assertFalse(page_content.page.is_home)


class DuplicateViewTestCase(CMSTestCase):
    def test_obj_does_not_exist(self):
        with self.login_user_context(self.get_superuser()), patch(
            "django.contrib.messages.add_message"
        ) as mock:
            response = self.client.get(
                self.get_admin_url(PageContent, "duplicate_content", "foo")
            )
        self.assertRedirects(response, "/en/admin/", target_status_code=302)
        self.assertEqual(mock.call_count, 1)
        self.assertEqual(mock.call_args[0][1], 30)  # warning level
        self.assertEqual(
            mock.call_args[0][2],
            'page content with ID "foo" doesn\'t exist. Perhaps it was deleted?',
        )

    def test_get(self):
        pagecontent = PageContentWithVersionFactory()
        with self.login_user_context(self.get_superuser()):
            response = self.client.get(
                self.get_admin_url(PageContent, "duplicate_content", pagecontent.pk)
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PageContent._base_manager.count(), 1)

    def test_post_empty_slug(self):
        pagecontent = PageContentWithVersionFactory()
        with self.login_user_context(self.get_superuser()):
            response = self.client.post(
                self.get_admin_url(PageContent, "duplicate_content", pagecontent.pk),
                data={"slug": ""},
            )
            form = response.context["form"]
        self.assertEqual(response.status_code, 200)
        self.assertFalse(form.is_valid())
        self.assertIn("slug", form.errors)
        self.assertEqual(form.errors["slug"], ["This field is required."])

    def test_post_empty_slug_after_slugify(self):
        pagecontent = PageContentWithVersionFactory()
        with self.login_user_context(self.get_superuser()):
            response = self.client.post(
                self.get_admin_url(PageContent, "duplicate_content", pagecontent.pk),
                data={"site": Site.objects.first().pk, "slug": "£"},
            )
            form = response.context["form"]
        self.assertEqual(response.status_code, 200)
        self.assertFalse(form.is_valid())
        self.assertIn("slug", form.errors)
        self.assertEqual(form.errors["slug"], ["Slug must not be empty."])

    def test_post(self):
        pagecontent = PageContentWithVersionFactory(template="page.html")
        placeholder = PlaceholderFactory(slot="content", source=pagecontent)
        add_plugin(placeholder, "TextPlugin", pagecontent.language, body="Test text")
        with self.login_user_context(self.get_superuser()):
            response = self.client.post(
                self.get_admin_url(PageContent, "duplicate_content", pagecontent.pk),
                data={"site": Site.objects.first().pk, "slug": "foo bar"},
                follow=True,
            )
        self.assertRedirects(response, self.get_admin_url(PageContent, "changelist"))
        new_pagecontent = PageContent._base_manager.latest("pk")
        new_placeholder = new_pagecontent.placeholders.get(slot="content")
        self.assertEqual(PageContent._base_manager.count(), 2)
        self.assertNotEqual(pagecontent, new_pagecontent)
        self.assertNotEqual(pagecontent.page, new_pagecontent.page)
        self.assertEqual(pagecontent.language, new_pagecontent.language)
        self.assertEqual(
            new_pagecontent.page.get_slug(new_pagecontent.language), "foo-bar"
        )
        new_plugins = list(downcast_plugins(new_placeholder.get_plugins_list()))
        self.assertEqual(len(new_plugins), 1)
        self.assertEqual(new_plugins[0].plugin_type, "TextPlugin")
        self.assertEqual(new_plugins[0].body, "Test text")

    def test_post_with_parent(self):
        pagecontent1 = PageContentWithVersionFactory(
            template="page.html",
            page__node__depth=0,
            page__node__path="0001",
            page__node__numchild=1,
        )
        PageUrl.objects.create(
            slug="foo",
            path="foo",
            language=pagecontent1.language,
            page=pagecontent1.page,
        )
        pagecontent2 = PageContentWithVersionFactory(
            template="page.html",
            language=pagecontent1.language,
            page__node__parent_id=pagecontent1.page.node_id,
            page__node__depth=1,
            page__node__path="00010001",
        )
        placeholder = PlaceholderFactory(slot="content", source=pagecontent2)
        add_plugin(placeholder, "TextPlugin", pagecontent2.language, body="Test text")
        with self.login_user_context(self.get_superuser()):
            response = self.client.post(
                self.get_admin_url(PageContent, "duplicate_content", pagecontent2.pk),
                data={"site": Site.objects.first().pk, "slug": "bar"},
                follow=True,
            )
        self.assertRedirects(response, self.get_admin_url(PageContent, "changelist"))
        new_pagecontent = PageContent._base_manager.latest("pk")
        new_placeholder = new_pagecontent.placeholders.get(slot="content")
        self.assertEqual(PageContent._base_manager.count(), 3)
        self.assertNotEqual(pagecontent2, new_pagecontent)
        self.assertNotEqual(pagecontent2.page, new_pagecontent.page)
        self.assertEqual(pagecontent2.language, new_pagecontent.language)
        self.assertEqual(
            new_pagecontent.page.get_path(new_pagecontent.language), "foo/bar"
        )
        new_plugins = list(downcast_plugins(new_placeholder.get_plugins_list()))
        self.assertEqual(len(new_plugins), 1)
        self.assertEqual(new_plugins[0].plugin_type, "TextPlugin")
        self.assertEqual(new_plugins[0].body, "Test text")


class RegistrationTestCase(TestCase):
    def test_admin_is_registered(self):
        self.assertIn(PageContent, admin.site._registry)
        self.assertTrue(isinstance(admin.site._registry[PageContent], PageContentAdmin))


@override_settings(CMS_PERMISSION=True)
class CMSToolbarTestCase(CMSTestCase): 
    def test_pages_menu_item_url_has_no_params(self):
        """
        Create a page and get the toolbar for that page's preview
        Then check that the page menu item does not have a query string, 
        so as not to trigger filters
        """
        user = self.get_superuser()
        pagecontent = PageVersionFactory(content__template="")
        toolbar = get_toolbar(
            pagecontent.content,
            user=user,
            toolbar_class=PageAdminToolbar,
            preview_mode=True,
        )
        toolbar.post_template_populate()
        menu = toolbar.toolbar.get_menu('admin-menu')
        pagemenu = menu.get_items()[0]
        self.assertTrue('/en/admin/cms/pagecontent/?language=en', pagemenu.url)

    def test_cmstoolbar_is_replaced(self):
        """
        Create a page and check that the PageToolbar has been replaced by the PageAdminToolbar
        """
        user = self.get_superuser()
        page = create_page(title='Test', template='page.html', language='en', created_by=user)
        self.request = self.get_page_request(page, user, '/')
        self.assertIn('djangocms_pageadmin.cms_toolbars.PageAdminToolbar', toolbar_pool.toolbars)


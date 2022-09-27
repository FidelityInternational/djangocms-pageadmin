import datetime
from functools import partial
from unittest import skip
from unittest.mock import MagicMock, patch

from django.contrib import admin
from django.contrib.sites.models import Site
from django.test import TestCase, TransactionTestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils.text import slugify

from cms.api import add_plugin
from cms.models import PageContent, PageUrl
from cms.test_utils.testcases import CMSTestCase
from cms.toolbar.utils import get_object_preview_url
from cms.utils.conf import get_cms_setting
from cms.utils.plugins import downcast_plugins

from bs4 import BeautifulSoup
from djangocms_moderation.admin_actions import add_items_to_collection
from djangocms_versioning.constants import ARCHIVED, PUBLISHED
from djangocms_versioning.helpers import version_list_url
from djangocms_versioning.models import Version

from djangocms_pageadmin.admin import PageContentAdmin
from djangocms_pageadmin.compat import DJANGO_GTE_30
from djangocms_pageadmin.test_utils.factories import (
    PageContentWithVersionFactory,
    PageUrlFactory,
    PageVersionFactory,
    PlaceholderFactory,
    UserFactory,
)


parse_html = partial(BeautifulSoup, features="lxml")


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

    def test_ordering_author(self):
        model = PageContent
        order = 2
        author = PageContentAdmin._list_display[order]
        self.assertEqual(author, 'author', 'Make sure we are checking the correct ordering')

        with self.login_user_context(self.get_superuser()):
            url = self.get_admin_url(model, "changelist")
            url = '{url}?o={order}'.format(url=url, order=(order + 1))
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class ListActionsTestCase(CMSTestCase):
    def setUp(self):
        self.modeladmin = admin.site._registry[PageContent]

    def test_duplicate_url_is_replaced(self):
        """
        The old url /duplicate/ has been removed. But cms_pagecontent_duplicate
        still exists.
        """

        urls = self.modeladmin.get_urls()
        duplicate_url = [u for u in urls if '/duplicate/' in u.pattern.regex.pattern]
        name_url = [u for u in urls if 'cms_pagecontent_duplicate' == u.name]

        self.assertEqual(len(duplicate_url), 0)
        self.assertEqual(len(name_url), 1)

    def test_preview_link(self):
        pagecontent = PageContentWithVersionFactory()
        func = self.modeladmin._list_actions(self.get_request("/"))
        response = func(pagecontent)
        soup = parse_html(response)
        element = soup.find("a", {"class": "cms-page-admin-action-preview"})
        self.assertIsNotNone(element, "Missing a.cms-page-admin-action-preview element")
        self.assertEqual(element["title"], "Preview")
        self.assertEqual(element["href"], get_object_preview_url(pagecontent))

    @skip("Skip Test as Edit link is commented in list_actions")
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

    @skip("Skip Test as Edit link is commented in list_actions")
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
            reverse("admin:cms_pagecontent_duplicate", args=(version.pk,)),
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
                self.get_admin_url(PageContent, "duplicate", "foo")
            )
        self.assertRedirects(response, "/en/admin/", target_status_code=302)
        self.assertEqual(mock.call_count, 1)
        self.assertEqual(mock.call_args[0][1], 30)  # warning level

        # Django < 3 support
        # django 3 contains text formatting changes
        if not DJANGO_GTE_30:
            self.assertEqual(
                mock.call_args[0][2],
                'page content with ID "foo" doesn\'t exist. Perhaps it was deleted?',
            )
        # django >= 3 support
        else:
            self.assertEqual(
                mock.call_args[0][2],
                'page content with ID “foo” doesn’t exist. Perhaps it was deleted?',
            )

    def test_get(self):
        pagecontent = PageContentWithVersionFactory()
        with self.login_user_context(self.get_superuser()):
            response = self.client.get(
                self.get_admin_url(PageContent, "duplicate", pagecontent.pk)
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PageContent._base_manager.count(), 1)

    def test_post_empty_slug(self):
        pagecontent = PageContentWithVersionFactory()
        with self.login_user_context(self.get_superuser()):
            response = self.client.post(
                self.get_admin_url(PageContent, "duplicate", pagecontent.pk),
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
                self.get_admin_url(PageContent, "duplicate", pagecontent.pk),
                data={"site": Site.objects.first().pk, "slug": "£"},
            )
            form = response.context["form"]
        self.assertEqual(response.status_code, 200)
        self.assertFalse(form.is_valid())
        self.assertIn("slug", form.errors)
        self.assertEqual(form.errors["slug"], ["Slug must not be empty."])

    def test_post(self):
        """the slot for content is always there, the slot for navigation needs
        to be created"""
        pagecontent = PageContentWithVersionFactory(template="page.html")
        placeholder = PlaceholderFactory(slot="content", source=pagecontent)
        PlaceholderFactory(slot="navigation", source=pagecontent)
        add_plugin(placeholder, "TextPlugin", pagecontent.language, body="Test text")
        with self.login_user_context(self.get_superuser()):
            response = self.client.post(
                self.get_admin_url(PageContent, "duplicate", pagecontent.pk),
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
                self.get_admin_url(PageContent, "duplicate", pagecontent2.pk),
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


class ChangelistSideframeControlsTestCase(CMSTestCase):
    def setUp(self):
        self.modeladmin = admin.site._registry[PageContent]

    def test_changelist_url_link_doesnt_open_in_sideframe(self):
        """
        When clicking on the pages url link the sideframe is closed
        and the page link is followed
        """
        pagecontent = PageContentWithVersionFactory()
        pagecontent._path = "/some-url"
        url_markup = self.modeladmin.url(pagecontent)

        # The url link should close the sideframe when selected
        self.assertIn("js-page-admin-close-sideframe", url_markup)
        self.assertNotIn("js-page-admin-keep-sideframe", url_markup)

    def test_preview_link_doesnt_open_in_sideframe(self):
        """
        When clicking on the pages preview link the sideframe is closed
        and the page link is followed
        """
        pagecontent = PageContentWithVersionFactory()
        func = self.modeladmin._list_actions(self.get_request("/"))
        response = func(pagecontent)
        soup = parse_html(response)
        element = soup.find("a", {"class": "cms-page-admin-action-preview"})

        # The preview link should close the sideframe when selected
        self.assertIn("js-page-admin-close-sideframe", element.attrs["class"])
        self.assertNotIn("js-page-admin-keep-sideframe", element.attrs["class"])


class RegistrationTestCase(TestCase):
    def test_admin_is_registered(self):
        self.assertIn(PageContent, admin.site._registry)
        self.assertTrue(isinstance(admin.site._registry[PageContent], PageContentAdmin))


@override_settings(CMS_PERMISSION=True)
class CMSPageToolbarTestCase(CMSTestCase):
    def test_cms_page_toolbar_pages_link_doesnt_filter_the_page_list_by_page_id(self):
        """
        The PageToolbar "Pages" link sends a parameter "page_id=X" which filters the page admin changelist.
        This is not desired behaviour for this package, the page_id for the standard cms is designed to allow the page
        tree to show a tree from a page i.e. expand any children below it. The page admin for this package does not use
        a page tree so this functionality breaks the admin changelist by only showing the page with the matching id.

        The PageAdmin page list should not be affected by the page_id parameter.
        """
        template_1 = get_cms_setting('TEMPLATES')[0][0]
        pages = PageContentWithVersionFactory.create_batch(6, template=template_1, language="en")
        base_url = self.get_admin_url(PageContent, "changelist")
        simulated_toolbar_pages_link = "/en/admin/cms/pagecontent/?language=en&page_id=1"

        with self.login_user_context(self.get_superuser()):
            # Default changelist link
            response = self.client.get(base_url)
            # Toolbar pages link simulation
            response_with_page_id = self.client.get(simulated_toolbar_pages_link)

        self.assertSetEqual(set(response.context["cl"].queryset), set(pages))
        self.assertSetEqual(set(response_with_page_id.context["cl"].queryset), set(pages))


class AdminSearchTestCase(CMSTestCase):
    """
    Test case covers custom search functionality.
    """
    def setUp(self):
        template_1 = get_cms_setting('TEMPLATES')[0][0]
        self.language = "en"
        self.pagecontent = PageContentWithVersionFactory(
            template=template_1, language=self.language,
            title="This is a test"
        )
        PageContentWithVersionFactory.create_batch(
            template=template_1, language=self.language,
            size=5,
        )
        self.page_admin = PageContentAdmin(PageContent, admin)
        # Use _base_manager so that non-published contents are available
        self.page_queryset = PageContent._base_manager.all()
        self.page_urls = []

    def _get_page_admin_request(self, search_term):
        return f"/admin/cms/pagecontent/?q={search_term}"

    def test_page_url_search_partial_match_from_slug_and_path(self):
        """
        Partial URL matches to the slug and path return the PageContent associated with it.
        """
        PageUrlFactory(
            page=self.pagecontent.page,
            language=self.language,
            path=slugify("example-url"),
            slug=slugify("example-url"),
        )
        request = self._get_page_admin_request("example-url")
        url_instance = self.pagecontent.page.urls.filter(language="en").first()
        url = url_instance.path

        with self.login_user_context(self.get_superuser()):
            response = self.client.get(request, follow=True)

        soup = BeautifulSoup(response.content, "html.parser")
        results = soup.find_all("td", "field-url")

        self.assertEqual(len(results), 1)
        self.assertIn(url, results[0].text)

    def test_page_url_search_partial_match_from_slug(self):
        """
        Partial URL matches to the slug return the pagecontent associated with it.
        """
        PageUrlFactory(
            page=self.pagecontent.page,
            language=self.language,
            slug=slugify("example-slug"),
        )
        request = self._get_page_admin_request("example-slug")

        with self.login_user_context(self.get_superuser()):
            response = self.client.get(request, follow=True)

        soup = BeautifulSoup(response.content, "html.parser")
        results_title = soup.find_all("td", "field-get_title")

        self.assertEqual(len(results_title), 1)
        # As only slug is populated, the admin will render the url as blank, therefore check the title.
        self.assertIn(self.pagecontent.title, results_title[0].text)

    def test_page_url_search_partial_match_from_path(self):
        """
        Partial URL matches to the path return the pagecontent associated with it.
        """
        page_url = PageUrlFactory(
            page=self.pagecontent.page,
            language=self.language,
            path=slugify("example-path"),
        )
        request = self._get_page_admin_request("example-path")
        url = page_url.path

        with self.login_user_context(self.get_superuser()):
            response = self.client.get(request, follow=True)

        soup = BeautifulSoup(response.content, "html.parser")
        results = soup.find_all("td", "field-url")

        self.assertEqual(len(results), 1)
        self.assertIn(url, results[0].text)

    def test_page_url_search_invalid_search_criteria(self):
        """
        Invalid search criteria are handled gracefully.
        """
        PageUrlFactory(
            page=self.pagecontent.page,
            language=self.language,
            path=slugify("example-slug"),
            slug=slugify("example-slug"),
        )

        request = self._get_page_admin_request("not-a-valid-path")

        with self.login_user_context(self.get_superuser()):
            response = self.client.get(request, follow=True)

        soup = BeautifulSoup(response.content, "html.parser")
        results = soup.find_all("td", "field-url")

        self.assertEqual(results, [])

    def test_page_url_search_url_in_other_language(self):
        """
        With a match in a different language, but not in the current one, the pagecontent should not be returned.
        """
        # Create URLs in more than one language
        PageUrlFactory(
            page=self.pagecontent.page,
            language="en",
            path=slugify("example-path"),
            slug=slugify("example-slug"),
        )
        PageUrlFactory(
            page=self.pagecontent.page,
            language="de",
            path=slugify("test-path"),
            slug=slugify("test-slug"),
        )

        request = self._get_page_admin_request("test-path")

        with self.login_user_context(self.get_superuser()):
            response = self.client.get(request, follow=True)

        soup = BeautifulSoup(response.content, "html.parser")
        results = soup.find_all("td", "field-url")

        self.assertEqual(results, [])

    def test_page_url_search_term_symbol(self):
        """
        When searching by symbol, appropriate results should be returned
        """
        page_url = PageUrlFactory(
            page=self.pagecontent.page,
            language="en",
            path=slugify("test-path"),
            slug=slugify("test-slug"),
        )
        request = self._get_page_admin_request("-")
        url = page_url.path

        with self.login_user_context(self.get_superuser()):
            response = self.client.get(request, follow=True)

        soup = BeautifulSoup(response.content, "html.parser")
        results = soup.find_all("td", "field-url")

        self.assertEqual(len(results), 1)
        self.assertIn(url, results[0].text)


class PageAdminCsvExportFileTestCase(CMSTestCase):
    def setUp(self):
        self.headings_map = {
            "title": 0,
            "expiry_date": 1,
            "version_state": 2,
            "version_author": 3,
            "url": 4,
            "compliance_number": 5,
        }
        self.export_admin_endpoint = self.get_admin_url(PageContent, "export_csv")
        self.template_1 = get_cms_setting('TEMPLATES')[0][0]

    def test_export_button_endpoint_response_is_a_csv(self):
        """
        Valid csv file is returned from the admin export endpoint
        """
        PageContentWithVersionFactory.create_batch(6, template=self.template_1, language="en")
        with self.login_user_context(self.get_superuser()):
            response = self.client.get(self.export_admin_endpoint)

        # Endpoint is returning 200 status code
        self.assertEqual(response.status_code, 200)
        # Response contains a csv file
        self.assertEquals(
            response.get('Content-Disposition'),
            "attachment; filename={}.csv".format("cms.pagecontent")
        )

    def test_export_content_headers(self):
        """
        Export should contain all the headings in the current page content list display
        """
        PageContentWithVersionFactory()

        with self.login_user_context(self.get_superuser()):
            response = self.client.get(self.export_admin_endpoint)

        csv_headings = response.content.decode().splitlines()[0].split(",")

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            csv_headings[self.headings_map["title"]],
            "Title"
        )
        self.assertEqual(
            csv_headings[self.headings_map["expiry_date"]],
            "Expiry Date"
        )
        self.assertEqual(
            csv_headings[self.headings_map["version_state"]],
            "Version State"
        )
        self.assertEqual(
            csv_headings[self.headings_map["version_author"]],
            "Version Author"
        )
        self.assertEqual(
            csv_headings[self.headings_map["url"]],
            "Url"
        )
        self.assertEqual(
            csv_headings[self.headings_map["compliance_number"]],
            "Compliance Number"
        )

    def test_file_content_contains_values(self):
        """
        CSV response should contain expected values.
        """
        version = PageVersionFactory(state=PUBLISHED, content__language="en")
        preview_url = get_object_preview_url(version)

        with self.login_user_context(self.get_superuser()):
            response = self.client.get(self.export_admin_endpoint)

        self.assertEqual(response.status_code, 200)

        csv_lines = response.content.decode().splitlines()

        content_row_1 = csv_lines[1].split(",")

        self.assertIn(
            content_row_1[self.headings_map["title"]],
            version.content.title
        )
        self.assertEqual(
            content_row_1[self.headings_map["expiry_date"]],
            ""
        )
        self.assertEqual(
            content_row_1[self.headings_map["compliance_number"]],
            ""
        )
        self.assertEqual(
            content_row_1[self.headings_map["version_state"]].lower(),
            version.state
        )
        self.assertEqual(
            content_row_1[self.headings_map["version_author"]],
            version.created_by.username
        )
        self.assertNotEqual(
            content_row_1[self.headings_map["url"]],
            preview_url
        )

    def test_export_button_is_visible(self):
        """
        Export button should be visible on the frontend changelist
        """
        admin_endpoint = self.get_admin_url(PageContent, "changelist")

        with self.login_user_context(self.get_superuser()):
            response = self.client.get(admin_endpoint)

        self.assertContains(
            response,
            '<a class="historylink" href="/en/admin/cms/pagecontent/export_csv/?">Export</a>',
            html=True
        )

    def test_get_compliance_number(self):
        """
        Compliance number should be returned by the get_compliance_number method
        """
        mock_with_content_expiry = MagicMock(spec=Version)
        mock_with_content_expiry.contentexpiry = MagicMock(compliance_number="123456789123456")

        page_content = PageContent()
        model_admin = PageContentAdmin(PageContent, admin.AdminSite())

        with patch.object(model_admin, "get_version") as mock_get_version:
            mock_get_version.return_value = mock_with_content_expiry
            result = model_admin.get_compliance_number(page_content)

            self.assertEqual(result, "123456789123456")
            mock_get_version.assert_called_once_with(page_content)

    def test_get_expiry_date(self):
        """
        The expiry date should be returned by the get_expiry_date method
        """
        from_date = datetime.datetime.now()
        expire_at = from_date + datetime.timedelta(days=10)
        mock_with_content_expiry = MagicMock(spec=Version)
        mock_with_content_expiry.contentexpiry = MagicMock(expires=expire_at)

        page_content = PageContent()
        model_admin = PageContentAdmin(PageContent, admin.AdminSite())

        with patch.object(model_admin, "get_version") as mock_get_version:
            mock_get_version.return_value = mock_with_content_expiry
            result = model_admin.get_expiry_date(page_content)

            self.assertEqual(result, expire_at)
            mock_get_version.assert_called_once_with(page_content)


class TestPageContentAdminActions(CMSTestCase):

    def test_get_actions_when_moderation_is_installed(self):
        """
        With djangocms_moderation installed, the PageContentAdmin actions should include the action to add multiple
        items to a collection.
        """
        pagecontent_admin = PageContentAdmin(PageContent, admin.AdminSite())
        request = self.get_request('/')

        actions = pagecontent_admin.get_actions(request)
        self.assertIn("add_items_to_collection", actions)
        self.assertEqual(actions, {
            "add_items_to_collection": (
                add_items_to_collection,
                "add_items_to_collection",
                add_items_to_collection.short_description
            )
        })

    @patch("django.apps.apps.is_installed")
    def test_get_actions_when_moderation_not_installed(self, is_installed):
        """
        With djangocms_moderation not installed, the PageContentAdmin actions should include the action to add multiple
        items to a collection. As djangocms_moderation is installed in the test environment, a mock is used to simulate
        it not being installed.
        """
        is_installed.return_value = False
        pagecontent_admin = PageContentAdmin(PageContent, admin.AdminSite())
        request = self.get_request('/')

        actions = pagecontent_admin.get_actions(request)
        self.assertNotIn("add_items_to_collection", actions)
        self.assertEqual(actions, {})
        is_installed.assert_called_once_with("djangocms_moderation")

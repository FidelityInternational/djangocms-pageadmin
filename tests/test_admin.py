from unittest.mock import patch

from cms.api import add_plugin
from cms.models import PageContent
from cms.test_utils.testcases import CMSTestCase
from cms.utils.plugins import downcast_plugins
from django.contrib import admin
from django.contrib.sites.models import Site
from django.http import HttpResponse

from djangocms_pageadmin.admin import PageContentAdmin
from djangocms_pageadmin.test_utils.factories import (
    PageContentWithVersionFactory,
    PlaceholderFactory,
    SiteFactory,
)
from djangocms_versioning.constants import UNPUBLISHED


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
        site2_pagecontents = PageContentWithVersionFactory.create_batch(
            1, page__node__site=site2, language="en"
        )
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


class DuplicateViewTestCase(CMSTestCase):
    def test_obj_does_not_exist(self):
        with self.login_user_context(self.get_superuser()), patch(
            "djangocms_pageadmin.admin.PageContentAdmin._get_obj_does_not_exist_redirect",
            return_value=HttpResponse(),
        ) as mock:
            response = self.client.get(
                self.get_admin_url(PageContent, "duplicate_content", "foo")
            )
        mock.assert_called_once()
        self.assertEqual(response, mock.return_value)

    def test_get(self):
        pagecontent = PageContentWithVersionFactory()
        with self.login_user_context(self.get_superuser()):
            response = self.client.get(
                self.get_admin_url(PageContent, "duplicate_content", pagecontent.pk)
            )
        self.assertEqual(response.status_code, 200)

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
                data={"site": Site.objects.first().pk, "slug": "foo"},
                follow=True,
            )
        self.assertRedirects(response, self.get_admin_url(PageContent, "changelist"))
        new_pagecontent = PageContent._base_manager.latest("pk")
        new_placeholder = new_pagecontent.placeholders.get(slot="content")
        self.assertEqual(PageContent._base_manager.count(), 2)
        self.assertNotEqual(pagecontent, new_pagecontent)
        self.assertNotEqual(pagecontent.page, new_pagecontent.page)
        self.assertEqual(pagecontent.language, new_pagecontent.language)
        self.assertEqual(new_pagecontent.page.get_slug(new_pagecontent.language), "foo")
        new_plugins = list(downcast_plugins(new_placeholder.get_plugins_list()))
        self.assertEqual(len(new_plugins), 1)
        self.assertEqual(new_plugins[0].plugin_type, "TextPlugin")
        self.assertEqual(new_plugins[0].body, "Test text")


class RegistrationTestCase(CMSTestCase):
    def test_admin_is_registered(self):
        self.assertIn(PageContent, admin.site._registry)
        self.assertTrue(isinstance(admin.site._registry[PageContent], PageContentAdmin))

from django.conf import settings
from django.contrib.sites.models import Site
from django.test import override_settings

from cms.models import PageContent
from cms.test_utils.testcases import CMSTestCase
from cms.utils import get_current_site
from cms.utils.conf import get_cms_setting

from djangocms_versioning.constants import UNPUBLISHED

from djangocms_pageadmin.test_utils.factories import (
    PageContentWithVersionFactory,
    PageVersionFactory,
    SiteFactory,
    UserFactory,
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


class LanguageFilterTestCase(CMSTestCase):
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


class UnpublishedTestCase(CMSTestCase):
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


class TemplateFilterTestCase(CMSTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.site_1 = Site(id=1, domain='domain.com', name='Domain site')
        cls.site_1.save()
        cls.site_2 = Site(id=2, domain='example.com', name='Example site')
        cls.site_2.save()

    def test_template_filter(self):
        template_1 = get_cms_setting('TEMPLATES')[0][0]
        template_2 = get_cms_setting('TEMPLATES')[1][0]
        template_1_pages = PageContentWithVersionFactory.create_batch(3, template=template_1, language="en")
        template_2_pages = PageContentWithVersionFactory.create_batch(3, template=template_2, language="en")
        base_url = self.get_admin_url(PageContent, "changelist")

        with self.login_user_context(self.get_superuser()):
            # All / No templates filtered is the default
            response_default = self.client.get(base_url)
            # fullwidth template set
            response_template_1 = self.client.get(base_url + "?template={}".format(template_1))
            # page template set
            response_template_2 = self.client.get(base_url + "?template={}".format(template_2))

        self.assertSetEqual(set(response_default.context["cl"].queryset), set(template_1_pages) | set(template_2_pages))
        self.assertSetEqual(set(response_template_1.context["cl"].queryset), set(template_1_pages))
        self.assertSetEqual(set(response_template_2.context["cl"].queryset), set(template_2_pages))

    @override_settings(SITE_ID=1)
    def test_templates_filtered_by_site(self):
        """
        Templates filter lookup choices should be filtered by site
        """
        current_site = get_current_site()
        base_url = self.get_admin_url(PageContent, "changelist")
        site_templates = getattr(settings, "SITE_TEMPLATES", {})

        with self.login_user_context(self.get_superuser()):
            response_default = self.client.get(base_url)

        actual_lookup_choices = response_default.context_data["cl"].filter_specs[2].lookup_choices
        expected_lookup_choices = site_templates.get(current_site.domain, None)

        self.assertEqual(actual_lookup_choices[0], expected_lookup_choices[0])

    @override_settings(SITE_ID=2)
    def test_templates_filtered_by_site_without_templates(self):
        """
        Sites which are not configured in templates, should return a default template list
        """
        base_url = self.get_admin_url(PageContent, "changelist")

        with self.login_user_context(self.get_superuser()):
            response_default = self.client.get(base_url)

        actual_lookup_choices = response_default.context_data["cl"].filter_specs[2].lookup_choices
        expected_lookup_choices = get_cms_setting('TEMPLATES')

        self.assertEqual(actual_lookup_choices[0], expected_lookup_choices[0])


class AuthorFilterTestCase(CMSTestCase):
    def test_author_filter(self):
        """
        Author filter should only show selected author's results
        """
        author1 = UserFactory()
        author2 = UserFactory()
        page_author_1 = PageVersionFactory(content__template="page.html", content__language="en", created_by=author1)
        page_author_2 = PageVersionFactory(content__template="page.html", content__language="en", created_by=author2)

        author_param = f"?created_by={author1.pk}"
        base_url = self.get_admin_url(PageContent, "changelist")

        with self.login_user_context(self.get_superuser()):
            response = self.client.get(base_url)

        queryset_result = response.context_data['cl'].result_list

        # The results should not be filtered
        self.assertTrue(len(queryset_result), 2)
        self.assertQuerysetEqual(
            response.context["cl"].queryset,
            [page_author_1.pk, page_author_2.pk],
            transform=lambda x: x.pk,
            ordered=False,
        )

        with self.login_user_context(self.get_superuser()):
            response = self.client.get(base_url + author_param)

        queryset_result = response.context_data['cl'].result_list

        # When an author is selected in the filter only the author selected pages are shown
        self.assertTrue(len(queryset_result), 1)
        self.assertQuerysetEqual(
            response.context["cl"].queryset,
            [page_author_1.pk],
            transform=lambda x: x.pk,
            ordered=False,
        )

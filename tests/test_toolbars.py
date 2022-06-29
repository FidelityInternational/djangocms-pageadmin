from django.apps import apps
from django.urls import reverse
from django.utils.text import slugify

from cms.models.titlemodels import PageContent
from cms.test_utils.testcases import CMSTestCase
from cms.toolbar.utils import get_object_edit_url, get_object_preview_url

from djangocms_versioning.test_utils.factories import PageUrlFactory

from djangocms_pageadmin.test_utils import factories


class PageAdminToolbarTestCase(CMSTestCase):
    def _get_versionable(self):
        """Helper method to get the versionable for PageContent
        """
        versioning_extension = apps.get_app_config("djangocms_versioning").cms_extension
        return versioning_extension.versionables_by_content[PageContent]

    def test_edit_mode_toolbar_button_preview_live_url_appended(self):
        """
        The PageAdminToolbar alters the preview url to add the live url as a querystring parameter
        """
        draft_version = factories.PageVersionFactory(content__template="page.html", content__language="en")
        language = draft_version.content.language
        PageUrlFactory(
            page=draft_version.content.page,
            language=language,
            path=slugify("test_page"),
            slug=slugify("test_page"),
        )
        edit_endpoint = get_object_edit_url(draft_version.content)
        expected_url = "{}?live-URL={}".format(
            get_object_preview_url(draft_version.content),
            "/en/test_page/"
        )

        with self.login_user_context(self.get_superuser()):
            response = self.client.get(edit_endpoint)

        self.assertContains(
            response,  '<a href="{}" class="cms-btn cms-btn cms-btn-switch-save">Preview</a>'.format(expected_url)
        )

    def test_preview_mode_toolbar_button_edit_live_url_appended(self):
        """
        The PageAdminToolbar alters the edit url to add the live url as a querystring parameter
        """
        draft_version = factories.PageVersionFactory(content__template="page.html", content__language="en")
        language = draft_version.content.language
        PageUrlFactory(
            page=draft_version.content.page,
            language=language,
            path=slugify("test_page"),
            slug=slugify("test_page"),
        )
        preview_endpoint = get_object_preview_url(draft_version.content)
        proxy_model = self._get_versionable().version_model_proxy
        edit_url = reverse(
            "admin:{app}_{model}_edit_redirect".format(
                app=proxy_model._meta.app_label, model=proxy_model.__name__.lower()
            ),
            args=(draft_version.pk,),
        )
        expected_url = "{}?live-URL={}".format(
            edit_url,
            "/en/test_page/"
        )

        with self.login_user_context(self.get_superuser()):
            response = self.client.get(preview_endpoint)

        self.assertContains(
            response,
            '<a href="{}" class="cms-btn cms-btn-action cms-versioning-js-edit-btn">Edit</a>'.format(expected_url)
        )

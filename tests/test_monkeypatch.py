from django.utils.text import slugify

from cms.test_utils.testcases import CMSTestCase
from cms.toolbar.utils import get_object_preview_url

from djangocms_versioning.test_utils.factories import PageUrlFactory

from djangocms_pageadmin.test_utils import factories


class ToolbarMonkeyPatchTestCase(CMSTestCase):

    def test_view_published_in_toolbar_in_preview_mode_button_url(self):
        """
        The monkeypatch adds the target attribute to the view published button
        """
        published_version = factories.PageVersionFactory(content__template="page.html", content__language="en")
        language = published_version.content.language
        PageUrlFactory(
            page=published_version.content.page,
            language=language,
            path=slugify("test_page"),
            slug=slugify("test_page"),
        )
        published_version.publish(user=self.get_superuser())
        draft_version = published_version.copy(self.get_superuser())
        preview_endpoint = get_object_preview_url(draft_version.content)

        with self.login_user_context(self.get_superuser()):
            response = self.client.get(preview_endpoint)

        self.assertContains(response, '<a href="/en/test_page/"')
        self.assertContains(
            response,  'class="cms-btn cms-btn cms-btn-switch-save" target="_blank" >View Published</a>'
        )

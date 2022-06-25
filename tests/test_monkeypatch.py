from cms.test_utils.testcases import CMSTestCase
from cms.toolbar.utils import get_object_edit_url, get_object_preview_url

from djangocms_pageadmin.test_utils import factories


class ToolbarMonkeyPatchTestCase(CMSTestCase):
    def test_preview_button_contains_target(self):
        """
        The monkeypatch adds the target attribute to the preview button only
        """
        user = self.get_superuser()
        version = factories.PageVersionFactory(created_by=user, content__template="page.html")
        url = get_object_edit_url(version.content)

        with self.login_user_context(user):
            response = self.client.get(url)

        self.assertContains(response, 'class="cms-btn cms-btn cms-btn-switch-save" target="_blank"')
        self.assertContains(response, get_object_preview_url(version.content))

from cms.test_utils.testcases import CMSTestCase
from cms.toolbar.utils import get_object_preview_url, get_object_edit_url

from djangocms_versioning.constants import PUBLISHED
from djangocms_versioning.test_utils.test_helpers import find_toolbar_buttons, get_toolbar

from djangocms_pageadmin.test_utils import factories


class ToolbarMonkeyPatchTestCase(CMSTestCase):
    def test_preview_button_contains_target(self):
        """
        The monkeypatch adds the target attribute to the view published button
        """
        version = factories.PageVersionFactory(content__template="page.html", state=PUBLISHED)
        toolbar = get_toolbar(version.content, preview_mode=True)
        toolbar.post_template_populate()

        button = toolbar.toolbar.get_right_items()[1].buttons[0]
        rendered_button = button.render()

        self.assertIn(
            'class="cms-btn cms-btn cms-btn-switch-save" target="_blank" >View Published</a>', rendered_button
        )
        self.assertIn(version.content.get_absolute_url(), rendered_button)

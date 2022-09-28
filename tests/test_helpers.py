from unittest.mock import MagicMock, patch

from cms.test_utils.testcases import CMSTestCase

from djangocms_pageadmin.helpers import is_moderation_enabled


class TestIsModerationEnabled(CMSTestCase):

    @patch("django.apps.apps.get_app_config")
    def test_when_config_not_found(self, mock_get_app_config):
        """
        As djangocms_moderation is installed in the test environment, patches get_app_config to raise a LookupError to
        simulate djangocms_moderation not being installed
        """
        mock_get_app_config.side_effect = LookupError

        result = is_moderation_enabled()

        self.assertFalse(result)
        mock_get_app_config.assert_called_once_with("djangocms_moderation")

    @patch("django.apps.apps.get_app_config")
    def test_config_does_not_include_page_content_model(self, mock_get_app_config):
        """
        As djangocms_moderation is installed in the test environment, patches get_app_config to return a mock config
        object where we set the moderation models to an empty list, to check that the helper returns False
        """
        mock_config = MagicMock()
        mock_config.cms_extension.moderated_models = []
        mock_get_app_config.return_value = mock_config

        result = is_moderation_enabled()

        self.assertFalse(result)
        mock_get_app_config.assert_called_once_with("djangocms_moderation")

    def test_config_does_include_page_content_model(self):
        """
        The test environment has djangocms_moderation installed and enabled so this should return True
        """
        self.assertTrue(is_moderation_enabled())

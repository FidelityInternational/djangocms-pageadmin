from django.utils.translation import ugettext_lazy as _

from cms.toolbar.items import ButtonList

from djangocms_version_locking.monkeypatch.cms_toolbars import (
    ButtonWithAttributes,
)
from djangocms_versioning.cms_toolbars import VersioningToolbar


def new_view_published_button(func):
    """
    The cms core does not allow for custom attributes to be specified for toolbar buttons, therefore,
    monkeypatch the method which adds view published to use the ButtonWithAttributes item from djangocms-version-locking
    """
    def inner(self, **kwargs):
        """Helper method to add a publish button to the toolbar
        """
        # Check if object is registered with versioning otherwise don't add
        if not self._is_versioned():
            return

        # Add the View published button if in edit or preview mode
        published_version = self._get_published_page_version()
        if not published_version:
            return

        if self.toolbar.edit_mode_active or self.toolbar.preview_mode_active:
            item = ButtonList(side=self.toolbar.RIGHT)
            view_published_button = ButtonWithAttributes(
                _("View Published"),
                url=published_version.get_absolute_url(),
                disabled=False,
                extra_classes=['cms-btn', 'cms-btn-switch-save'],
                html_attributes={"target": "_blank"},
            )
            item.buttons.append(view_published_button)
            self.toolbar.add_item(item)
    return inner


VersioningToolbar._add_view_published_button = new_view_published_button(VersioningToolbar._add_view_published_button)

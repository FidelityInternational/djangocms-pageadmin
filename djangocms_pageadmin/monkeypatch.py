from django.utils.translation import ugettext_lazy as _

from cms.cms_toolbars import PlaceholderToolbar
from cms.toolbar.items import ButtonList
from cms.toolbar.utils import get_object_preview_url

from djangocms_version_locking.monkeypatch.cms_toolbars import (
    ButtonWithAttributes
)


def new_preview_button(func):
    """
    The cms core does not allow for custom attributes to be specified for toolbar buttons, therefore,
    monkeypatch the method which adds preview to use the ButtonWithAttributes item from djangocms-version-locking
    """
    def inner(self, **kwargs):
        url = get_object_preview_url(self.toolbar.obj, language=self.toolbar.request_language)
        item = ButtonList(side=self.toolbar.RIGHT)
        preview_button = ButtonWithAttributes(
            _("Preview"),
            url=url,
            disabled=False,
            extra_classes=["cms-btn", "cms-btn-switch-save"],
            html_attributes={"target": "_blank"},
        )
        item.buttons.append(preview_button)
        self.toolbar.add_item(item)
    return inner


PlaceholderToolbar.add_preview_button = new_preview_button(PlaceholderToolbar.add_preview_button)

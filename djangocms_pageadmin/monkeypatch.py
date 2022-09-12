from django.utils.translation import ugettext_lazy as _

from cms.toolbar.items import ButtonList

from djangocms_version_locking.monkeypatch.cms_toolbars import (
    ButtonWithAttributes,
)
from djangocms_versioning import admin
from djangocms_versioning.cms_toolbars import VersioningToolbar
from djangocms_versioning.models import StateTracking


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


def published_date(self, obj):
    version = StateTracking.objects.filter(version_id=obj.pk)
    if hasattr(version.first(), "new_state") and version.first().new_state == "published":
        return version.first().date
    return ""


published_date.short_description = "Published Date"
admin.VersionAdmin.published_date = published_date


def get_list_display(func):
    """
    Register the published date field with the Versioning Admin
    """
    def inner(self, request):
        original_list_display = func(self, request)
        list_display_list = list(original_list_display)
        # Removing created date from versioning changelist
        del list_display_list[1]
        new_list_display = tuple(list_display_list)
        modified_date = new_list_display.index('modified')
        return new_list_display[:modified_date] + ('published_date',) + new_list_display[modified_date:]
    return inner


admin.VersionAdmin.get_list_display = get_list_display(admin.VersionAdmin.get_list_display)

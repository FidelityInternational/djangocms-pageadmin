from django.urls import reverse
from django.utils.translation import ugettext_lazy as _

from cms.toolbar.items import ButtonList
from cms.toolbar.utils import get_object_preview_url

from djangocms_versioning.cms_toolbars import replace_toolbar, VersioningToolbar
from djangocms_versioning.models import Version

from .conf import PAGEADMIN_LIVE_URL_QUERY_PARAM_NAME
from .helpers import _get_url

try:
    from djangocms_moderation import helpers
    from djangocms_moderation.cms_toolbars import ModerationToolbar

    moderation_installed = True
    toolbar_to_replace = ModerationToolbar
except ImportError:
    moderation_installed = False
    toolbar_to_replace = VersioningToolbar


class PageAdminToolBar(toolbar_to_replace):
    """
    Toolbar inheriting from ModerationToolbar, to replace it with altered edit and preview endpoints
    """

    def _add_pageadmin_edit_button(self, disabled=False):
        item = ButtonList(side=self.toolbar.RIGHT)
        proxy_model = self._get_proxy_model()
        version = Version.objects.get_for_content(self.toolbar.obj)
        url = reverse(
            "admin:{app}_{model}_edit_redirect".format(
                app=proxy_model._meta.app_label, model=proxy_model.__name__.lower()
            ),
            args=(version.pk,),
        )
        url = f"{url}?{PAGEADMIN_LIVE_URL_QUERY_PARAM_NAME}={_get_url(self.toolbar.obj)}"
        item.add_button(
            _("Edit"),
            url=url,
            disabled=disabled,
            extra_classes=["cms-btn-action", "cms-versioning-js-edit-btn"],
        )
        self.toolbar.add_item(item)

    def _add_edit_button(self, disabled=False):
        """Helper method to add the modified edit button, including slug appended.
        """
        # can we moderate content object?
        # return early to avoid further DB calls below
        if moderation_installed:
            if not helpers.is_registered_for_moderation(self.toolbar.obj):
                return self._add_pageadmin_edit_button(disabled=disabled)
            # yes we can! but is it locked?
            if helpers.is_obj_review_locked(self.toolbar.obj, self.request.user):
                disabled = True

        return self._add_pageadmin_edit_button(disabled)

    def add_preview_button(self):
        """Helper method to add the modified preview button, including slug appended.
        """
        language = self.toolbar.request_language
        url = get_object_preview_url(self.toolbar.obj, language=language)
        url = f"{url}?{PAGEADMIN_LIVE_URL_QUERY_PARAM_NAME}={_get_url(self.toolbar.obj)}"
        item = ButtonList(side=self.toolbar.RIGHT)
        item.add_button(
            _('Preview'),
            url=url,
            disabled=False,
            extra_classes=['cms-btn', 'cms-btn-switch-save'],
        )
        self.toolbar.add_item(item)


replace_toolbar(toolbar_to_replace, PageAdminToolBar)

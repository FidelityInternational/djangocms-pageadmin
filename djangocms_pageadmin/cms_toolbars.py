from collections import OrderedDict

from django.urls import reverse
from django.utils.translation import ugettext_lazy as _

from cms.toolbar.items import ButtonList
from cms.toolbar.utils import get_object_preview_url
from cms.toolbar_pool import toolbar_pool

from djangocms_moderation import helpers
from djangocms_moderation.cms_toolbars import ModerationToolbar
from djangocms_versioning.models import Version

from .helpers import _get_url


class PageAdminToolBar(ModerationToolbar):
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
        url = "{url}?live-URL={live_url}".format(url=url, live_url=_get_url(self.toolbar.obj))
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
        url = "{url}?live-URL={live_url}".format(url=url, live_url=_get_url(self.toolbar.obj))
        item = ButtonList(side=self.toolbar.RIGHT)
        item.add_button(
            _('Preview'),
            url=url,
            disabled=False,
            extra_classes=['cms-btn', 'cms-btn-switch-save'],
        )
        self.toolbar.add_item(item)


def replace_toolbar(old, new):
    """Replace `old` toolbar class with `new` class,
    while keeping its position in toolbar_pool.
    """
    new_name = ".".join((new.__module__, new.__name__))
    old_name = ".".join((old.__module__, old.__name__))
    toolbar_pool.toolbars = OrderedDict(
        [
            (new_name, new) if name == old_name else (name, toolbar)
            for name, toolbar in toolbar_pool.toolbars.items()
        ]
    )


replace_toolbar(ModerationToolbar, PageAdminToolBar)

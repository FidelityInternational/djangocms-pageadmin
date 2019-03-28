from django.test import RequestFactory

from cms.toolbar.toolbar import CMSToolbar

from djangocms_versioning.cms_toolbars import VersioningToolbar

from djangocms_pageadmin.test_utils.factories import UserFactory


def get_toolbar(content_obj, user=None, **kwargs):
    """
    Helper method to set up the toolbar
    Copied from djangocms-versioning.test_utils.test_helpers
    """
    # Set the user if none are sent
    if not user:
        user = UserFactory(is_staff=True)

    request = kwargs.get("request", RequestFactory().get("/"))
    request.user = user
    request.session = kwargs.get("session", {})
    request.current_page = getattr(content_obj, "page", None)
    request.toolbar = CMSToolbar(request)
    # Set the toolbar class
    if kwargs.get("toolbar_class", False):
        toolbar_class = kwargs.get("toolbar_class")
    else:
        toolbar_class = VersioningToolbar
    toolbar = toolbar_class(
        request, toolbar=request.toolbar, is_current_app=True, app_path="/"
    )
    toolbar.toolbar.set_object(content_obj)
    # Set the toolbar mode
    if kwargs.get("edit_mode", False):
        toolbar.toolbar.edit_mode_active = True
        toolbar.toolbar.content_mode_active = False
        toolbar.toolbar.structure_mode_active = False
    elif kwargs.get("preview_mode", False):
        toolbar.toolbar.edit_mode_active = False
        toolbar.toolbar.content_mode_active = True
        toolbar.toolbar.structure_mode_active = False
    elif kwargs.get("structure_mode", False):
        toolbar.toolbar.edit_mode_active = False
        toolbar.toolbar.content_mode_active = False
        toolbar.toolbar.structure_mode_active = True
    toolbar.populate()
    return toolbar

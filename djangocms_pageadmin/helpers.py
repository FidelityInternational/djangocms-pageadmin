from copy import deepcopy

from django.apps import apps

from cms.models import PageContent

from djangocms_versioning import versionables


def proxy_model(obj):
    versionable = versionables.for_content(PageContent)
    obj_ = deepcopy(obj)
    obj_.__class__ = versionable.version_model_proxy
    return obj_


def is_moderation_enabled():
    """
    Returns True if the PageContent model is enabled for moderation.
    If it is not, or djangocms_moderation is not installed, returns False.

    :returns: True or False
    """
    try:
        moderation_config = apps.get_app_config("djangocms_moderation")
    except LookupError:
        return False

    return PageContent in moderation_config.cms_extension.moderated_models

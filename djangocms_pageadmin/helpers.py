from copy import deepcopy

from cms.models import PageContent
from cms.utils.conf import get_cms_setting

from djangocms_versioning import versionables


def proxy_model(obj):
    versionable = versionables.for_content(PageContent)
    obj_ = deepcopy(obj)
    obj_.__class__ = versionable.version_model_proxy
    return obj_


def get_settings_templates(templates):
    """
    Returns lookup choices from the configured templates
    :param templates:
    :return: Lookup choices
    """
    return [template for template in templates]


def get_default_templates():
    """
    Returns lookup choices from the default templates
    :return: Default lookup choices
    """
    for value, name in get_cms_setting('TEMPLATES'):
        yield (value, name)
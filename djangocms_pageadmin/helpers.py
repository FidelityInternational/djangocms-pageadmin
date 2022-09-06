from copy import deepcopy

from cms.models import PageContent

from djangocms_versioning import versionables


def proxy_model(obj):
    versionable = versionables.for_content(PageContent)
    obj_ = deepcopy(obj)
    obj_.__class__ = versionable.version_model_proxy
    return obj_

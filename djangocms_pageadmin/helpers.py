from copy import deepcopy

from cms.models import PageContent

from djangocms_versioning import versionables


def original_model(obj):
    obj_ = deepcopy(obj)
    obj_.__class__ = PageContent
    return obj_


def proxy_model(obj):
    content_model = obj.content_type.model_class()
    versionable = versionables.for_content(content_model)
    obj_ = deepcopy(obj)
    obj_.__class__ = versionable.version_model_proxy
    return obj_

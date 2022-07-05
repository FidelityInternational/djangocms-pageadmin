from copy import deepcopy

from django.urls import reverse
from django.utils.translation import override

from cms.models import PageContent

from djangocms_versioning import versionables


def proxy_model(obj):
    versionable = versionables.for_content(PageContent)
    obj_ = deepcopy(obj)
    obj_.__class__ = versionable.version_model_proxy
    return obj_


def _get_url(obj):
    """
    Get the relative path of a live URL for a given page,
    this helper is required as slug doesn't necessarily provide the correct path if a page is updated.
    """
    path = obj.page.get_path(obj.language)
    with override(obj.language):
        if obj.page.is_home:
            return reverse("pages-root")
        if path:
            return reverse("pages-details-by-slug", kwargs={"slug": path})

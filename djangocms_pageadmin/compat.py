from cms import __version__ as cms_version

from packaging.version import Version


DJANGO_CMS_4_1 = Version(cms_version) >= Version('4.1')
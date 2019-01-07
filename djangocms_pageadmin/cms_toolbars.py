from django.urls import reverse

from cms.cms_toolbars import ADMIN_MENU_IDENTIFIER
from cms.toolbar_base import CMSToolbar
from cms.toolbar_pool import toolbar_pool
from cms.utils.urlutils import add_url_parameters

from .models import PageContent


@toolbar_pool.register
class PageAdminToolbar(CMSToolbar):
    def populate(self):
        admin_menu = self.toolbar.get_or_create_menu(ADMIN_MENU_IDENTIFIER)
        url = reverse(
            "admin:{}_{}_changelist".format(
                PageContent._meta.app_label, PageContent._meta.model_name
            )
        )
        params = {"language": self.toolbar.request_language}
        url = add_url_parameters(url, params)
        admin_menu.items[0].url = url

from collections import OrderedDict

from cms.cms_toolbars import PageToolbar
from cms.toolbar_pool import toolbar_pool
from cms.utils.urlutils import admin_reverse


# Identifiers for search
ADMIN_MENU_IDENTIFIER = "admin-menu"
VERSIONING_MENU_IDENTIFIER = "version"


class PageAdminToolbar(PageToolbar):
    def change_admin_menu(self):
        """
        The standard Pages menu for the PageContent model as provided by the CMS returns a selected item.
        This works because that view has no filters. PageAdmin has filters, so this causes unwanted filtering.
        Thus replace the PageToolbar with to remove the filter parameters from the URL
        """
        super().change_admin_menu()
        menu = self.toolbar.get_menu(ADMIN_MENU_IDENTIFIER)
        item = menu.items[0]
        # Menu items like SubMenu that have no url attribute:
        if item and getattr(item, 'url', None) and "admin/cms/pagecontent/" in item.url:
            url = admin_reverse("cms_pagecontent_changelist")  # cms page admin
            item.url = url


def replace_toolbar(old, new):
    """
    Replace `old` toolbar class with `new` class,
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


replace_toolbar(PageToolbar, PageAdminToolbar)

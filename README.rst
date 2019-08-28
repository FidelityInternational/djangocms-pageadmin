====================
djangocms-pageadmin
====================

Installation
============

Requirements
============

django CMS Page Admin requires that you have a django CMS 4.0 (or higher)
project already running and set up.

To install
==========

Run::

    pip install djangocms-pageadmin

Add ``djangocms_pageadmin`` to your project's ``INSTALLED_APPS``.
It should appear **after** ``cms`` app in order to override the
default PageContent admin class.


Development
===========

Extending PageAdmin
-------------------

If you need to extend the pageadmin further you can do that in the following way.

    # admin.py
    from django.contrib import admin
    from djangocms_pageadmin.admin import PageContentAdmin

    class CustomPageContentAdmin(PageContentAdmin):
        # your changes here
        pass

    admin.site.unregister(PageContent)
    admin.site.register(PageContent, CustomPageContentAdmin)


Running Tests
-------------

You can run the tests by executing:

    python -m venv venv
    source venv/bin/activate
    python setup.py test

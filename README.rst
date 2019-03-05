====================
djangocms-pageadmin
====================

Installation
============

Requirements
============

django CMS Page Admin requires that you have a django CMS 4.0 (or higher) project already running and set up.


To install
==========

Run::

    pip install djangocms-pageadmin

Add ``djangocms_pageadmin`` to your project's ``INSTALLED_APPS``.
It should appear **after** ``cms`` app in order to override the
default PageContent admin class.

Run::

    python manage.py migrate djangocms_pageadmin

to perform the application's database migrations.


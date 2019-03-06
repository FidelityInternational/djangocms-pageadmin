.. djangocms-pageadmin documentation master file, created by
   sphinx-quickstart on Thu Feb 14 11:45:02 2019.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to djangocms-pageadmin's documentation!
===============================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

Overview
--------

Django CMS Page Admin provides a new PageContent admin which doesn't
include tree functionality. It also displays data from Django CMS Versioning
and Django CMS Version Locking.

Installation
------------

Run::

    pip install djangocms-pageadmin

Add ``djangocms_pageadmin`` to your project's ``INSTALLED_APPS``.
It should appear **after** ``cms`` app in order to override the
default PageContent admin class.

.. code-block:: python

    INSTALLED_APPS = [
        # ...
        'cms',
        # ...
        'djangocms_pageadmin',
        # ...
    ]

Usage
-----

Django CMS Page Admin replaces the default PageContent admin
provided by the CMS.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

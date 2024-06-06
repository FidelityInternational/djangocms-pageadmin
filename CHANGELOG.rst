=========
Changelog
=========

Unreleased
=================
* Fixed edit link in pageadmin to close sideframe

1.7.0 (2024-05-16)
==================
* Introduced Django 4.2 support.
* Dropped support for Django<3.1
* Added support for Python 3.10
* Dropped support for Python<3.8

1.6.0 (2022-11-04)
==================
* feat: Enabled edit button in Page Admin

1.5.0 (2022-09-28)
==================
* feat: Adds admin action to add multiple items to a collection when moderation is installed

1.4.0 (2022-09-21)
==================
* feat: Replacing created with published date in versioning changelist

1.3.0 (2022-09-06)
==================
* feat: Author filter added to admin
* feat: Template filter choices filtered by site. Moved filter test cases to own file

1.2.2 (2022-08-22)
==================
* feat: PageContent search checks PageUrls
* feat: CSV export functionality added to the change list
* fix: Added CMS_CONFIRM_VERSION4 in test_settings to show intend of using v4

1.1.2 (2022-07-20)
==================
* fix: Admin burger menu excluding Preview and Edit buttons in all languages
* feat: Migrate CI to use Github Actions

1.1.1 (2022-06-25)
==================
* fix: Update monkeypatch to target View Published instead of Preview button

1.1.0 (2022-06-23)
==================
* feat: Added monkeypatch to inject target="_blank" attribute into the toolbar preview button

1.0.0 (2022-02-10)
==================
* feat: Close the sideframe when following links to the page endpoints
* Python 3.8, 3.9 support added
* Django 3.0, 3.1 and 3.2 support added
* Python 3.5 and 3.6 support removed
* Django 1.11 support removed

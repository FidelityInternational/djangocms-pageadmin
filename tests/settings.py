import os


class DisableMigrations(object):
    """
    Django-cms disables all migrations when they run their tests.
    It would be better to not do it. Right now we are forced to disable our
    migrations because we inherit one of our models from django-cms.

    The error in question is due to an incompability of sqlite3 and
    with atomic transactions.
    """
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


HELPER_SETTINGS = {
    "SECRET_KEY": "djangocmspageadmintestsuitekey",
    "INSTALLED_APPS": [
        "djangocms_pageadmin",
        "djangocms_text_ckeditor",
        "djangocms_versioning",
        "djangocms_version_locking",
        "djangocms_alias",
        "djangocms_moderation",
    ],
    "LANGUAGES": (
        ("en", "English"),
        ("de", "German"),
        ("fr", "French"),
        ("it", "Italiano"),
    ),
    'MIGRATION_MODULES': DisableMigrations(),
    "CMS_LANGUAGES": {
        1: [
            {"code": "en", "name": "English", "fallbacks": ["de", "fr"]},
            {
                "code": "de",
                "name": "Deutsche",
                "fallbacks": ["en"],  # FOR TESTING DO NOT ADD 'fr' HERE
            },
            {
                "code": "fr",
                "name": "Française",
                "fallbacks": ["en"],  # FOR TESTING DO NOT ADD 'de' HERE
            },
            {
                "code": "it",
                "name": "Italiano",
                "fallbacks": ["fr"],  # FOR TESTING, LEAVE AS ONLY 'fr'
            },
        ]
    },
    "TEMPLATE_DIRS": (
        os.path.join(
            os.path.dirname(__file__),
            'djangocms_pageadmin', 'test_utils', 'templates', 'integration'),
    ),
    "PARLER_ENABLE_CACHING": False,
    "LANGUAGE_CODE": "en",
    # Due to a recent temporary change in develop-4, we now need to confirm that we intend to use v4
    "CMS_CONFIRM_VERSION4": True,
    "SITE_TEMPLATES": {
        "domain.com": (
            ("default_uk.html", "UK Default",),
            ("uktools.html", "UK Tools With Tool Base",),
        ),
    }
}


def run():
    from djangocms_helper import runner
    runner.cms("djangocms_pageadmin", extra_args=[])


if __name__ == "__main__":
    run()

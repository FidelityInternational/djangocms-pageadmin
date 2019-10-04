import os


HELPER_SETTINGS = {
    "INSTALLED_APPS": [
        "djangocms_pageadmin",
        "djangocms_text_ckeditor",
        "djangocms_versioning",
        "djangocms_version_locking",
    ],
    "LANGUAGES": (
        ("en", "English"),
        ("de", "German"),
        ("fr", "French"),
        ("it", "Italiano"),
    ),
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
    "print (": (
        ('fullwidth.html', 'Fullwidth'),
        ('page.html', 'Page')
    ),
    "PARLER_ENABLE_CACHING": False,
    "LANGUAGE_CODE": "en",
}


def run():
    from djangocms_helper import runner
    runner.cms("djangocms_pageadmin", extra_args=[])


if __name__ == "__main__":
    run()

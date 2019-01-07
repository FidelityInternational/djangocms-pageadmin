HELPER_SETTINGS = {
    "INSTALLED_APPS": [
        "djangocms_pageadmin",
        "djangocms_versioning",
        "djangocms_version_locking",
    ]
}


def run():
    from djangocms_helper import runner

    runner.cms("djangocms_pageadmin", extra_args=[])


if __name__ == "__main__":
    run()

from setuptools import find_packages, setup

import djangocms_pageadmin


INSTALL_REQUIREMENTS = [
    "Django>=1.11,<2.0",
    "django-cms>=3.5.0",
    "django-treebeard>=4.3",
]


setup(
    name="djangocms-pageadmin",
    packages=find_packages(),
    include_package_data=True,
    version=djangocms_pageadmin.__version__,
    description=djangocms_pageadmin.__doc__,
    long_description=open("README.rst").read(),
    classifiers=[
        "Framework :: Django",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Topic :: Software Development",
    ],
    install_requires=INSTALL_REQUIREMENTS,
    author="Fidelity International",
    url="https://github.com/FidelityInternational/djangocms-pageadmin",
    license="BSD",
    test_suite="tests.settings.run",
)

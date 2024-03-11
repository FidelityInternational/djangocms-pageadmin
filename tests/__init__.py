from djangocms_pageadmin.compat import DJANGO_4_2


if not DJANGO_4_2:  # TODO: remove when dropping support for Django < 4.2
    from django.test.testcases import TransactionTestCase

    TransactionTestCase.assertQuerySetEqual = TransactionTestCase.assertQuerysetEqual

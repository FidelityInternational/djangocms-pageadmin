from cms.models import PageContent as CmsPageContent


class PageContent(CmsPageContent):
    class Meta:
        proxy = True

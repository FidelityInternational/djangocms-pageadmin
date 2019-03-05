from django import forms
from django.contrib.sites.models import Site
from django.template.defaultfilters import slugify
from django.utils.translation import ugettext_lazy as _

from cms.forms.validators import validate_url_uniqueness


class DuplicateForm(forms.Form):
    site = forms.ModelChoiceField(
        label=_("Site"),
        queryset=Site.objects.all(),
        help_text=_("Site in which the new page will be created"),
    )
    slug = forms.CharField(
        label=_("Slug"),
        max_length=255,
        widget=forms.TextInput(),
        help_text=_("The part of the title that is used in the URL"),
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        self.page_content = kwargs.pop("page_content")
        super().__init__(*args, **kwargs)

    def clean_slug(self):
        slug = slugify(self.cleaned_data["slug"])
        if not slug:
            raise forms.ValidationError(_("Slug must not be empty."))
        return slug

    def clean(self):
        cleaned_data = super().clean()

        if self.errors:
            return cleaned_data

        language = self.page_content.language

        slug = cleaned_data["slug"]
        if self.page_content.page.node.parent:
            parent_path = self.page_content.page.node.parent.item.get_path(language)
            path = u"%s/%s" % (parent_path, slug) if parent_path else slug
        else:
            path = cleaned_data["slug"]

        try:
            validate_url_uniqueness(
                cleaned_data["site"],
                path=path,
                language=language,
                user_language=language,
            )
        except forms.ValidationError as e:
            self.add_error("slug", e)
        else:
            cleaned_data["path"] = path

        return cleaned_data

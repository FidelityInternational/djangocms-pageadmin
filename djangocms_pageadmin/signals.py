import django.dispatch

page_copied = django.dispatch.Signal(
    providing_args=["original_page", "copied_page", "language"]
)

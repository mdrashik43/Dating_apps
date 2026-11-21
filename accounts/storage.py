from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateStorage(FileSystemStorage):
    """Storage outside MEDIA_ROOT that can never produce a public URL.
    Files are only reachable through the permission-checked view."""

    def __init__(self, *args, **kwargs):
        super().__init__(location=settings.PRIVATE_MEDIA_ROOT)

    def url(self, name):
        raise ValueError("Private files have no public URL.")


def private_storage():
    return PrivateStorage()

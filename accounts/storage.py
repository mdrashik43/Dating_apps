import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateStorage(FileSystemStorage):
    """Storage outside MEDIA_ROOT that can never produce a public URL.
    Files are only reachable through permission-checked views. The location is
    read from settings on every use, so tests can point it at a temp folder."""

    @property
    def base_location(self):
        return settings.PRIVATE_MEDIA_ROOT

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    def url(self, name):
        raise ValueError("Private files have no public URL.")


def private_storage():
    return PrivateStorage()

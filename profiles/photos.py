from io import BytesIO
from uuid import uuid4

from django.core.files.base import ContentFile
from PIL import Image, ImageOps
from rest_framework import serializers

MAX_BYTES = 5 * 1024 * 1024
MAX_PHOTOS = 6


def clean_image(upload) -> ContentFile:
    """Validate by decoding, then re-encode as plain JPEG. Re-encoding drops EXIF
    (GPS location, camera, timestamps) and anything hidden inside the file."""
    if upload.size > MAX_BYTES:
        raise serializers.ValidationError("Image too large (max 5 MB).")
    try:
        probe = Image.open(upload)
        probe.verify()
        upload.seek(0)
        img = Image.open(upload)
        if img.format not in {"JPEG", "PNG", "WEBP"}:
            raise ValueError
        img = ImageOps.exif_transpose(img).convert("RGB")
    except Exception:
        raise serializers.ValidationError("Upload a real JPG, PNG or WEBP image.")
    img.thumbnail((1600, 1600))
    buf = BytesIO()
    img.save(buf, "JPEG", quality=85)
    return ContentFile(buf.getvalue(), name=f"{uuid4().hex}.jpg")

import shutil
import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image

from accounts.testing import APITestCase, make_user
from mystery_game.tests_helpers import mutual_match
from profiles.models import ProfilePhoto

ME = "/api/profiles/me/photos/"
S = "/api/game/sessions/"


def image_bytes(fmt="JPEG", size=(80, 60), exif=False):
    img = Image.new("RGB", size, "red")
    buf = BytesIO()
    kwargs = {}
    if exif:
        ex = Image.Exif()
        ex[0x010F] = "SecretCameraMaker"
        kwargs["exif"] = ex
    img.save(buf, fmt, **kwargs)
    return buf.getvalue()


def upload(client, data, name="p.jpg", url=ME):
    return client.post(url, {"image": SimpleUploadedFile(name, data)}, format="multipart")


class PhotoTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp()
        ov = override_settings(PRIVATE_MEDIA_ROOT=self.tmp)
        ov.enable()
        self.addCleanup(ov.disable)
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.a, self.b = self.player("a@uiu.ac.bd", name="Alice"), self.player("b@uiu.ac.bd", name="Bob")
        self.ca, self.cb = self.client_for(self.a), self.client_for(self.b)

    def test_upload_requires_login_and_profile(self):
        self.assertEqual(self.client_for().post(ME).status_code, 401)
        self.assertEqual(upload(self.client_for(make_user("n@uiu.ac.bd")), image_bytes()).status_code, 400)

    def test_upload_list_delete(self):
        r = upload(self.ca, image_bytes())
        self.assertEqual(r.status_code, 201)
        self.assertEqual(len(self.ca.get(ME).json()), 1)
        self.assertEqual(self.ca.delete(f"{ME}{r.json()['id']}/").status_code, 204)
        self.assertEqual(self.ca.get(ME).json(), [])

    def test_png_and_webp_are_accepted_and_stored_as_jpeg(self):
        for fmt in ("PNG", "WEBP"):
            self.assertEqual(upload(self.ca, image_bytes(fmt)).status_code, 201)
        photo = ProfilePhoto.objects.first()
        self.assertEqual(Image.open(photo.image.path).format, "JPEG")

    def test_non_images_are_rejected(self):
        for data in (b"<script>alert(1)</script>", b"GIF89a" + b"0" * 50, b""):
            self.assertEqual(upload(self.ca, data, name="x.jpg").status_code, 400)
        self.assertEqual(self.ca.post(ME).status_code, 400)
        self.assertFalse(ProfilePhoto.objects.exists())

    def test_oversized_image_rejected(self):
        self.assertEqual(upload(self.ca, image_bytes() + b"0" * (5 * 1024 * 1024)).status_code, 400)

    def test_maximum_six_photos(self):
        for _ in range(6):
            self.assertEqual(upload(self.ca, image_bytes()).status_code, 201)
        self.assertEqual(upload(self.ca, image_bytes()).status_code, 400)

    def test_metadata_is_stripped_and_big_images_shrink(self):
        upload(self.ca, image_bytes(exif=True, size=(3000, 2000)))
        img = Image.open(ProfilePhoto.objects.get().image.path)
        self.assertEqual(len(img.getexif()), 0)
        self.assertLessEqual(max(img.size), 1600)

    def test_files_live_in_private_storage_not_media(self):
        upload(self.ca, image_bytes())
        self.assertTrue(ProfilePhoto.objects.get().image.path.startswith(self.tmp))

    def test_cannot_delete_someone_elses_photo(self):
        pid = upload(self.ca, image_bytes()).json()["id"]
        self.assertEqual(self.cb.delete(f"{ME}{pid}/").status_code, 404)
        self.assertTrue(ProfilePhoto.objects.filter(pk=pid).exists())

    def test_access_rules(self):
        pid = upload(self.ca, image_bytes()).json()["id"]
        url = f"/api/profiles/photos/{pid}/"
        self.assertEqual(self.client_for().get(url).status_code, 401)
        self.assertEqual(self.ca.get(url).status_code, 200)  # owner
        self.assertEqual(self.client_for(make_user("x@uiu.ac.bd")).get(url).status_code, 404)  # stranger (not in the pool)
        self.assertEqual(self.cb.get(url).status_code, 404)  # has not revealed Alice
        sid = self.cb.post(S).json()["id"]
        self.assertEqual(self.cb.get(url).status_code, 404)  # active, still hidden
        self.cb.post(f"{S}{sid}/reveal/")
        r = self.cb.get(url)
        self.assertEqual(r.status_code, 200)  # viewing the revealed profile
        self.assertIn("no-store", r["Cache-Control"])
        self.cb.post(f"{S}{sid}/decision/", {"action": "pass"}, format="json")
        self.assertEqual(self.cb.get(url).status_code, 404)  # passed: access ends

    def test_revealed_profile_lists_photo_urls_but_hides_them_before(self):
        pid = upload(self.ca, image_bytes()).json()["id"]
        sid = self.cb.post(S).json()["id"]
        self.assertNotIn("/api/profiles/photos/", self.cb.get(f"{S}{sid}/").content.decode())
        body = self.cb.post(f"{S}{sid}/reveal/").json()
        self.assertEqual(body["profile"]["photos"][0]["url"], f"/api/profiles/photos/{pid}/")

    def test_matches_can_see_each_others_photos_until_unmatch(self):
        pid = upload(self.ca, image_bytes()).json()["id"]
        match = mutual_match(self, self.a, self.b)
        url = f"/api/profiles/photos/{pid}/"
        self.assertEqual(self.cb.get(url).status_code, 200)
        self.ca.post(f"/api/matches/{match.pk}/unmatch/")
        self.assertEqual(self.cb.get(url).status_code, 404)

    def test_admin_profile_page_works_with_private_photos(self):
        upload(self.ca, image_bytes())
        su = make_user("root@uiu.ac.bd", is_staff=True, is_superuser=True)
        self.client.force_login(su)
        self.assertEqual(self.client.get(f"/admin/profiles/profile/{self.a.profile.pk}/change/").status_code, 200)

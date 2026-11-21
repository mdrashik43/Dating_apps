import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from accounts.models import VerificationRequest
from accounts.testing import PNG, APITestCase, make_user
from notifications.models import Notification

URL = "/api/auth/verification/"


class VerificationApiTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp()
        ov = override_settings(PRIVATE_MEDIA_ROOT=self.tmp)
        ov.enable()
        self.addCleanup(ov.disable)
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.student = make_user("s@uiu.ac.bd", university=self.uni)
        self.staff = make_user("staff@uiu.ac.bd", is_staff=True)

    def upload(self, user=None, name="id.png", data=PNG, sid="011221234"):
        user = user or self.student
        f = SimpleUploadedFile(name, data)
        return self.client_for(user).post(URL, {"student_id_number": sid, "document": f}, format="multipart")

    def test_anonymous_cannot_upload_or_list(self):
        self.assertEqual(self.client_for().post(URL, {}).status_code, 401)
        self.assertEqual(self.client_for().get(URL).status_code, 401)

    def test_upload_creates_pending_request_without_storage_url(self):
        r = self.upload()
        self.assertEqual(r.status_code, 201)
        body = r.json()
        self.assertEqual(body["status"], "pending")
        self.assertTrue(body["document_path"].endswith("/document/"))
        self.assertNotIn("/private_media/", str(body))
        self.assertNotIn("media/", body["document_path"])

    def test_fake_image_rejected_by_content_check(self):
        self.assertEqual(self.upload(data=b"<script>alert(1)</script>").status_code, 400)

    def test_bad_extension_rejected(self):
        self.assertEqual(self.upload(name="id.exe", data=PNG).status_code, 400)

    def test_oversized_file_rejected(self):
        self.assertEqual(self.upload(data=PNG + b"0" * (5 * 1024 * 1024)).status_code, 400)

    def test_bad_student_id_rejected(self):
        self.assertEqual(self.upload(sid="<b>x</b>").status_code, 400)

    def test_second_pending_request_rejected(self):
        self.assertEqual(self.upload().status_code, 201)
        self.assertEqual(self.upload().status_code, 400)

    def test_user_without_university_rejected(self):
        self.assertEqual(self.upload(user=make_user("n@gmail.com")).status_code, 400)

    def test_already_verified_rejected(self):
        self.assertEqual(self.upload(user=self.verified_user()).status_code, 400)

    def test_list_shows_only_own_requests(self):
        self.upload()
        other = make_user("o@uiu.ac.bd", university=self.uni)
        self.assertEqual(len(self.client_for(self.student).get(URL).json()), 1)
        self.assertEqual(self.client_for(other).get(URL).json(), [])


class StaffReviewTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp()
        ov = override_settings(PRIVATE_MEDIA_ROOT=self.tmp)
        ov.enable()
        self.addCleanup(ov.disable)
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.student = make_user("s@uiu.ac.bd", university=self.uni)
        self.staff = make_user("staff@uiu.ac.bd", is_staff=True)
        self.vr = VerificationRequest.objects.create(
            user=self.student, university=self.uni, student_id_number="011",
            document=SimpleUploadedFile("id.png", PNG))
        self.review = f"/api/auth/verification/{self.vr.pk}/review/"

    def test_students_cannot_see_pending_list_or_review(self):
        c = self.client_for(self.student)
        self.assertEqual(c.get(URL + "pending/").status_code, 403)
        self.assertEqual(c.post(self.review, {"decision": "approve"}, format="json").status_code, 403)
        self.vr.refresh_from_db()
        self.assertEqual(self.vr.status, "pending")

    def test_anonymous_cannot_review(self):
        self.assertEqual(self.client_for().post(self.review, {"decision": "approve"}, format="json").status_code, 401)

    def test_staff_sees_pending_list(self):
        r = self.client_for(self.staff).get(URL + "pending/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()[0]["email"], "s@uiu.ac.bd")

    def test_approve_verifies_user_and_notifies(self):
        r = self.client_for(self.staff).post(self.review, {"decision": "approve"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.student.refresh_from_db()
        self.assertTrue(self.student.is_university_verified)
        self.assertTrue(Notification.objects.filter(user=self.student, kind="verification").exists())

    def test_reject_requires_reason_and_does_not_verify(self):
        c = self.client_for(self.staff)
        self.assertEqual(c.post(self.review, {"decision": "reject"}, format="json").status_code, 400)
        r = c.post(self.review, {"decision": "reject", "reason": "Blurry photo"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_university_verified)
        self.assertEqual(r.json()["rejection_reason"], "Blurry photo")

    def test_cannot_review_twice(self):
        c = self.client_for(self.staff)
        c.post(self.review, {"decision": "approve"}, format="json")
        self.assertEqual(c.post(self.review, {"decision": "reject", "reason": "x"}, format="json").status_code, 400)

    def test_rejected_student_can_resubmit(self):
        self.client_for(self.staff).post(self.review, {"decision": "reject", "reason": "Blurry"}, format="json")
        f = SimpleUploadedFile("id2.png", PNG)
        r = self.client_for(self.student).post(URL, {"student_id_number": "011", "document": f}, format="multipart")
        self.assertEqual(r.status_code, 201)

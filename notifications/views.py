from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification


class NotificationListView(APIView):
    def get(self, request):
        qs = Notification.objects.filter(user=request.user)
        items = [
            {"id": n.pk, "kind": n.kind, "title": n.title, "body": n.body, "is_read": n.is_read, "created_at": n.created_at}
            for n in qs[:50]
        ]
        return Response({"unread": qs.filter(is_read=False).count(), "items": items})


class MarkReadView(APIView):
    def post(self, request):
        qs = Notification.objects.filter(user=request.user, is_read=False)
        ids = request.data.get("ids")
        if isinstance(ids, list):
            qs = qs.filter(pk__in=[i for i in ids if isinstance(i, int)])
        return Response({"marked": qs.update(is_read=True)})

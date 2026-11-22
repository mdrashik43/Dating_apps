from django.urls import path

from . import views

urlpatterns = [
    path("block/", views.BlockView.as_view(), name="block"),
    path("report/", views.ReportView.as_view(), name="report"),
    path("blocks/", views.MyBlocksView.as_view(), name="blocks"),
    path("blocks/<int:pk>/", views.UnblockView.as_view(), name="unblock"),
]

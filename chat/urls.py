from django.urls import path

from . import views

urlpatterns = [
    path("conversations/", views.ConversationListView.as_view(), name="conversations"),
    path("conversations/<int:pk>/messages/", views.MessagesView.as_view(), name="messages"),
]

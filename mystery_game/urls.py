from rest_framework.routers import DefaultRouter

from .views import MyClueViewSet

router = DefaultRouter()
router.register("clues", MyClueViewSet, basename="clue")
urlpatterns = router.urls

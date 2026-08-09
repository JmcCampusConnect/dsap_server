from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import StudentViewSet


router = DefaultRouter()
router.register(r'', StudentViewSet, basename='students')


urlpatterns = [
    path('', include(router.urls)),
]

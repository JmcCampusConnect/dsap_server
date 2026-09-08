from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import MyRequestViewSet

router = DefaultRouter()
router.register(r'my', MyRequestViewSet, basename='my-requests')

urlpatterns = [
    path('', include(router.urls)),
]

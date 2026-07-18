from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.departments.views.academic_department import AcademicDepartmentViewSet

router = DefaultRouter()
router.register(r'academic-departments', AcademicDepartmentViewSet, basename='academic-department')

urlpatterns = [
    path('', include(router.urls)),
]

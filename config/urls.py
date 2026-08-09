from django.contrib import admin
from django.urls import include, path


urlpatterns = [

    # Admin
    path('admin/', admin.site.urls),

    # Accounts 
    path("api/auth/", include("apps.accounts.urls.auth")),
    path("api/users/", include("apps.accounts.urls.user")),

    # Departments
    path("api/service-departments/",include("apps.departments.urls.service_department"),),
    path("api/academic-departments/",include("apps.departments.urls.academic_department")),

    # Students
    path("api/students/", include("apps.students.urls")),

    # Services
    path("api/services/", include("apps.services.urls")),
]

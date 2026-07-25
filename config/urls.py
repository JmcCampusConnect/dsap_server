from django.contrib import admin
from django.urls import include, path


urlpatterns = [

    # Accounts API
    path('api/', include('apps.accounts.urls')),
    path('admin/', admin.site.urls),
    path("api/v1/", include("apps.departments.urls")),
    path('api/accounts/', include('apps.accounts.urls')),
    path('api/', include('apps.departments.urls')),
    path('api/users/', include('common.urls')),
]

from django.contrib import admin
from django.urls import path, include

from apps.core.views import health_check

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health/', health_check, name='health-check'),
    path('api-auth/', include('rest_framework.urls')),
    path('api/auth/', include('apps.accounts.urls')),
    path('api/occupants/', include('apps.occupants.urls')),
    path('api/occupancy/', include('apps.occupancy.urls')),
    path('api/properties/', include('apps.properties.urls')),
    path('api/sections/', include('apps.sections.urls')),
    path('api/units/', include('apps.units.urls')),
    path('api/payments/', include('apps.payments.urls')),
    path('api/dashboard/', include('apps.dashboard.urls')),
    path('api/reports/', include('apps.reports.urls')),
    path('api/admin/', include('apps.administration.urls')),
    path('api/audit/', include('apps.audit.urls')),
    path('api/', include('apps.backup.urls')),
]

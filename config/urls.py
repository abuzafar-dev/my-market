"""Root URL configuration for the My Market project.

The backend is a JSON-only API (see TZ v2 section 8.1) — the frontend
is a separate Vue SPA that is not served from here. The Django admin
at /admin/ is the one exception and keeps rendering its own HTML.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.common.views import healthz
from apps.shops.views import SettingsView

urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("api/auth/", include("apps.shops.urls")),
    path("api/settings/", SettingsView.as_view(), name="settings"),
    path("api/", include("apps.catalog.urls")),
    path("api/", include("apps.sales.urls")),
    path("api/", include("apps.debt.urls")),
    path("api/", include("apps.reports.urls")),
]

if settings.ADMIN_ENABLED:
    urlpatterns.append(path("admin/", admin.site.urls))

if settings.DEBUG:
    # API docs describe every endpoint — handy while developing, not something to
    # publish on a live server.
    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path(
            "api/schema/swagger-ui/",
            SpectacularSwaggerView.as_view(url_name="schema"),
            name="swagger-ui",
        ),
    ]

if settings.DEBUG:
    # Product photos: served by nginx/whitenoise-equivalent in production,
    # but Django needs to do it itself in dev.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

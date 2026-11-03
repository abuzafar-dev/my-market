"""Notification routes, mounted at /api/ (see config/urls.py)."""

from django.urls import path

from . import views

urlpatterns = [
    path("whatsapp/webhook/", views.webhook, name="whatsapp-webhook"),
    path(
        "customers/whatsapp-statuses/",
        views.CustomerStatusesView.as_view(),
        name="customer-whatsapp-statuses",
    ),
    path(
        "customers/<uuid:pk>/whatsapp/",
        views.CustomerWhatsAppView.as_view(),
        name="customer-whatsapp",
    ),
    path(
        "customers/<uuid:pk>/whatsapp-consent/",
        views.CustomerConsentView.as_view(),
        name="customer-whatsapp-consent",
    ),
    path(
        "customers/<uuid:pk>/send-reminder/",
        views.SendReminderView.as_view(),
        name="customer-send-reminder",
    ),
    path(
        "shops/<uuid:shop_id>/notification-settings/",
        views.NotificationSettingsView.as_view(),
        name="shop-notification-settings",
    ),
]

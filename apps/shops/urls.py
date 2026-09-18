"""Authentication API routes, mounted at /api/auth/ (see config/urls.py)."""
from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="auth-login"),
    path("refresh/", views.RefreshView.as_view(), name="auth-refresh"),
    path("logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("password/", views.PasswordChangeView.as_view(), name="auth-password"),
]

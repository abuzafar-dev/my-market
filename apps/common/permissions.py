from rest_framework.permissions import BasePermission

from apps.shops.models import User


class IsOwner(BasePermission):
    """Restricts a view/action to shop owners; sellers get 403.

    Combine with IsAuthenticated (DRF ANDs permission_classes together) —
    on its own this would raise AttributeError for an anonymous request.
    """

    message = "Bu amal faqat do'kon egasi uchun."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == User.Role.OWNER)

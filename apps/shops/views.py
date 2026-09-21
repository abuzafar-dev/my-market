"""JWT authentication API.

The refresh token lives in an httpOnly cookie (never touched by JS, so an
XSS can't exfiltrate it); the access token is returned in the response
body and is expected to be kept in memory by the frontend. See TZ v2
section 9.4 for the rationale.
"""

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.permissions import IsOwner

from .models import User
from .serializers import (
    LoginSerializer,
    ShopSettingsSerializer,
    UserSerializer,
)

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/auth/"


def _set_refresh_cookie(response: Response, refresh: RefreshToken) -> None:
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        str(refresh),
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite="Strict",
    )


def _error(code: str, message: str, http_status: int) -> Response:
    return Response({"data": None, "error": {"code": code, "message": message}}, status=http_status)


class LoginView(APIView):
    """POST /api/auth/login/ — {phone, password} -> access token + user."""

    permission_classes = [AllowAny]
    # 10 attempts/min per address on top of the per-account lockout (security.py).
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        refresh = RefreshToken.for_user(user)
        response = Response(
            {"access": str(refresh.access_token), "user": UserSerializer(user).data}
        )
        _set_refresh_cookie(response, refresh)
        return response


class RefreshView(APIView):
    """POST /api/auth/refresh/ — cookie -> new access token."""

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        raw_token = request.COOKIES.get(REFRESH_COOKIE_NAME)
        if not raw_token:
            return _error("no_refresh_token", "Sessiya topilmadi.", status.HTTP_401_UNAUTHORIZED)

        try:
            refresh = RefreshToken(raw_token)
        except TokenError:
            return _error(
                "invalid_refresh_token", "Sessiya muddati tugagan.", status.HTTP_401_UNAUTHORIZED
            )

        # A hard page reload only has this cookie to go on — the frontend's
        # in-memory `auth.user` (role, shop) is gone, so it has to come back
        # here too, or the router's role guard treats every owner as a
        # stranger and bounces them off every owner-only screen.
        try:
            user = User.objects.get(pk=refresh.payload["user_id"])
        except User.DoesNotExist:
            return _error(
                "invalid_refresh_token", "Sessiya muddati tugagan.", status.HTTP_401_UNAUTHORIZED
            )

        # A deactivated account must not be able to keep minting tokens for
        # the remaining life of its refresh cookie (30 days).
        if not user.is_active:
            return _error(
                "invalid_refresh_token", "Sessiya muddati tugagan.", status.HTTP_401_UNAUTHORIZED
            )

        response = Response(
            {"access": str(refresh.access_token), "user": UserSerializer(user).data}
        )

        if settings.SIMPLE_JWT["ROTATE_REFRESH_TOKENS"]:
            if settings.SIMPLE_JWT["BLACKLIST_AFTER_ROTATION"]:
                try:
                    refresh.blacklist()
                except AttributeError:
                    pass
            refresh.set_jti()
            refresh.set_exp()
            refresh.set_iat()
            _set_refresh_cookie(response, refresh)

        return response


class LogoutView(APIView):
    """POST /api/auth/logout/ — revokes the refresh cookie."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        raw_token = request.COOKIES.get(REFRESH_COOKIE_NAME)
        if raw_token:
            try:
                RefreshToken(raw_token).blacklist()
            except TokenError:
                pass

        response = Response(status=status.HTTP_205_RESET_CONTENT)
        response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
        return response


class SettingsView(APIView):
    """GET/PATCH /api/settings/ — expiry warning window and currency (TZ v2 8.2)."""

    permission_classes = [IsAuthenticated, IsOwner]

    def get(self, request: Request) -> Response:
        return Response(ShopSettingsSerializer(request.user.shop.get_settings()).data)

    def patch(self, request: Request) -> Response:
        serializer = ShopSettingsSerializer(
            request.user.shop.get_settings(), data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

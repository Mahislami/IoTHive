import json
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST


def home_view(request):
    """
    Public landing page with quick access to login and product highlights.
    Logged-in users get a dashboard CTA while still seeing product context.
    """
    is_authenticated = request.user.is_authenticated
    primary_cta_url = reverse("dashboard") if is_authenticated else reverse("login")
    primary_cta_label = _("Enter Dashboard") if is_authenticated else _("Log In")

    context = {
        "primary_cta_url": primary_cta_url,
        "primary_cta_label": primary_cta_label,
        "secondary_cta_url": reverse("devices:kitchen_list") if is_authenticated else reverse("login"),
        "is_authenticated": is_authenticated,
    }
    return render(request, "home.html", context)


@login_required
@require_POST
def keep_session_alive(request):
    """AJAX endpoint to extend the authenticated session window."""
    request.session.modified = True
    return JsonResponse({
        "status": "ok",
        "expires_in": request.session.get_expiry_age(),
    })


@login_required
def logout_view(request):
    """Explicit logout endpoint that always redirects home."""
    logout(request)
    return redirect("home")


@login_required
@require_POST
def grafana_login_proxy(request):
    """Exchange operator-provided credentials for Grafana session cookies."""
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": _("Invalid payload.")}, status=400)

    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""

    if not username or not password:
        return JsonResponse({"error": _("Username and password are required.")}, status=400)

    base_url = getattr(settings, "GRAFANA_INTERNAL_URL", "http://grafana:3000/grafana/")
    if not base_url.endswith("/"):
        base_url = f"{base_url}/"
    login_url = urljoin(base_url, "login")

    try:
        grafana_response = requests.post(
            login_url,
            json={"user": username, "password": password},
            timeout=10,
        )
    except requests.RequestException:
        return JsonResponse({"error": _("Unable to reach Grafana.")}, status=502)

    if grafana_response.status_code != 200:
        return JsonResponse({"error": _("Invalid Grafana credentials.")}, status=401)

    response = JsonResponse({"ok": True})
    for cookie in grafana_response.cookies:
        cookie_path = cookie.path or "/grafana/"
        response.set_cookie(
            cookie.name,
            cookie.value,
            path=cookie_path,
            secure=request.is_secure(),
            httponly=True,
            samesite="Lax",
        )
    return response

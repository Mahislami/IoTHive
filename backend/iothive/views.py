from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_POST


def home_view(request):
    """
    Public landing page with quick access to login and product highlights.
    Logged-in users get a dashboard CTA while still seeing product context.
    """
    is_authenticated = request.user.is_authenticated
    primary_cta_url = reverse("dashboard") if is_authenticated else reverse("login")
    primary_cta_label = "Enter Dashboard" if is_authenticated else "Log In"

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

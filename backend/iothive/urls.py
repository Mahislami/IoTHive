"""
URL configuration for iothive project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from devices.views import signup_view, dashboard_view
from devices.forms import StyledAuthenticationForm
from iothive.views import home_view, keep_session_alive, logout_view, grafana_login_proxy

urlpatterns = [
    path('', home_view, name='home'),
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(template_name='login.html', authentication_form=StyledAuthenticationForm), name='login'),
    path('logout/', logout_view, name='logout'),
    path('signup/', signup_view, name='signup'),
    path('session/keepalive/', keep_session_alive, name='session_keepalive'),
    path('grafana/login/', grafana_login_proxy, name='grafana_login'),
    path("devices/", include(("devices.urls", "devices"), namespace="devices")),
    path("users/", include(("users.urls", "users"), namespace="users")),
    path("dashboard/", dashboard_view, name="dashboard"),
    path("i18n/", include("django.conf.urls.i18n")),
]

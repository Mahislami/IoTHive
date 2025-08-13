# backend/devices/urls.py

from django.urls import path
from .views import DeviceCreateView, DeviceListView, register_device_view, signup_view, dashboard_view
from .views import (
    DeviceListView, DeviceDetailView,
    UserListView, UserDetailView,
)

app_name = "devices"

urlpatterns = [
    path('create/', DeviceCreateView.as_view(), name='device-create'),
    path('', DeviceListView.as_view(), name='device-list'),
    path('register/', register_device_view, name='register_device'),  # new web form route
    path('signup/', signup_view, name='signup'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path("devices/", DeviceListView.as_view(), name="list"),
    path("devices/<int:pk>/", DeviceDetailView.as_view(), name="devices_detail"),
]

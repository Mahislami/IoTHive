# backend/devices/urls.py

from django.urls import path
from .views import DeviceListView, DeviceDetailView, DeviceCreateView, DeviceUpdateView, \
    device_delete, signup_view, dashboard_view
from .views import (
    DeviceListView, DeviceDetailView,
    UserListView, UserDetailView,
)

app_name = "devices"

urlpatterns = [
    path('create/', DeviceCreateView.as_view(), name='device-create'),
    path('signup/', signup_view, name='signup'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path("devices/", DeviceListView.as_view(), name="list"),
    path("devices/<int:pk>/", DeviceDetailView.as_view(), name="devices_detail"),
    path("", DeviceListView.as_view(), name="list"),
    path("create/", DeviceCreateView.as_view(), name="create"),
    path("<int:pk>/", DeviceDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", DeviceUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", device_delete, name="delete"),
]

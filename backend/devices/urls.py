# backend/devices/urls.py

from django.urls import path
from .views import DeviceCreateView, DeviceListView, register_device_view, signup_view

urlpatterns = [
    path('create/', DeviceCreateView.as_view(), name='device-create'),
    path('', DeviceListView.as_view(), name='device-list'),
    path('register/', register_device_view, name='register_device'),  # new web form route
    path('signup/', signup_view, name='signup'),
]

# backend/devices/urls.py

from django.urls import path
from .views import DeviceCreateView, DeviceListView

urlpatterns = [
    path('create/', DeviceCreateView.as_view(), name='device-create'),
    path('', DeviceListView.as_view(), name='device-list'),
]

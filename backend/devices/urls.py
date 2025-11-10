# backend/devices/urls.py
from . import views

from django.urls import path
from .views import DeviceListView, DeviceDetailView, DeviceCreateView, DeviceUpdateView, \
    device_delete, device_control, dashboard_view, alarm_rules, save_alarm_rule, active_alarms, ack_alarm, clear_alarm, \
    KitchenApplianceListView, KitchenApplianceCreateView, KitchenApplianceUpdateView
from .views import (
    DeviceListView, DeviceDetailView,
    UserListView, UserDetailView,
)

app_name = "devices"

urlpatterns = [
    path('create/', DeviceCreateView.as_view(), name='device-create'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('kitchen/', KitchenApplianceListView.as_view(), name='kitchen_list'),
    path('kitchen/new/', KitchenApplianceCreateView.as_view(), name='kitchen_create'),
    path('kitchen/<int:pk>/edit/', KitchenApplianceUpdateView.as_view(), name='kitchen_edit'),
    path("devices/", DeviceListView.as_view(), name="list"),
    path("devices/<int:pk>/", DeviceDetailView.as_view(), name="devices_detail"),
    path("", DeviceListView.as_view(), name="list"),
    path("create/", DeviceCreateView.as_view(), name="create"),
    path("<int:pk>/", DeviceDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", DeviceUpdateView.as_view(), name="edit"),
    path("<int:pk>/control/", device_control, name="control"),
    path("<int:pk>/delete/", device_delete, name="delete"),
    path('alarms/rules/', alarm_rules, name='alarm_rules'),
    path('alarms/rules/save/', save_alarm_rule, name='save_alarm_rule'),
    path('alarms/', active_alarms, name='active_alarms'),
    path('alarms/<int:event_id>/ack/', ack_alarm, name='ack_alarm'),
    path('alarms/<int:event_id>/clear/', clear_alarm, name='clear_alarm'),
    
]

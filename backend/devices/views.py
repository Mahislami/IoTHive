from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework import generics
from .models import Device
from .serializers import DeviceSerializer

class DeviceCreateView(generics.CreateAPIView):
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer

class DeviceListView(generics.ListAPIView):
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer

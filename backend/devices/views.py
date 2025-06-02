from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from rest_framework import generics
from .models import Device
from .serializers import DeviceSerializer
from .forms import DeviceForm  # New
from django.contrib.auth import login
from .forms import SignUpForm


# Existing API views
class DeviceCreateView(generics.CreateAPIView):
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer

class DeviceListView(generics.ListAPIView):
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer

# New form-based device registration view
@login_required
def register_device_view(request):
    if request.method == 'POST':
        form = DeviceForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('register_device')
    else:
        form = DeviceForm()
    return render(request, 'register_device.html', {'form': form})

def signup_view(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()

            # Set role in profile
            role = form.cleaned_data['role']
            user.userprofile.role = role
            user.userprofile.save()

            login(request, user)
            return redirect('register_device' if role == 'operator' else 'device-list')
    else:
        form = SignUpForm()
    return render(request, 'signup.html', {'form': form})
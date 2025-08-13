from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from rest_framework import generics
from .models import Device
from .serializers import DeviceSerializer
from .forms import DeviceForm  # New
from django.contrib.auth import login
from .forms import SignUpForm
from .forms import StyledAuthenticationForm
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.contrib.auth.models import User
from django.views.generic import ListView, DetailView
import json
from .models import Device, UserProfile
from .permissions import role_required
from django.urls import reverse

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
            print("DDddlllllllaallalMMMNN")
            user.save()

            # set role on profile (create or update)
            role = form.cleaned_data['role']
            print(role)
            UserProfile.objects.update_or_create(
                user=user,
                defaults={'role': role}
            )

            login(request, user)
            next_url = request.POST.get('next') or request.GET.get('next')
            return redirect(next_url or 'dashboard')  # named URL or use reverse('dashboard')
    else:
        form = SignUpForm()
    return render(request, 'signup.html', {'form': form})


@login_required
def dashboard_view(request):
    user = request.user
    role = getattr(getattr(user, 'userprofile', None), 'role', 'visitor')

    # Common item
    menu = [
        {
            "key": "grafana",
            "label": "Grafana Dashboard",
            "href": "https://grafana.example.com",  # TODO: replace
            "desc": "View metrics and charts",
            "icon": "activity",
        }
    ]

    if role in ("admin", "operator"):
        menu.insert(0, {
            "key": "devices",
            "label": "Manage Devices",
            "href": reverse("devices:list"),  # e.g. /devices/
            "desc": "Add, remove, or edit devices",
            "icon": "cpu",
        })

    if role == "admin":
        menu.append({
            "key": "users",
            "label": "Manage Users",
            "href": reverse("users:list"),
            "desc": "Create, disable, or edit users",
        })

    context = {
        "role": role,
        "menu": menu,
        "user_display": user.get_username(),
    }
    return render(request, "dashboard.html", {"menu": menu, "role": role, "user_display": request.user.username})

def login_view(request):
    if request.method == 'POST':
        form = StyledAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')  # Change 'home' to your desired redirect
    else:
        form = StyledAuthenticationForm()

    return render(request, 'login.html', {'form': form})




@method_decorator(login_required, name="dispatch")
class DeviceListView(ListView):
    model = Device
    template_name = "devices/list.html"
    context_object_name = "devices"
    paginate_by = 20
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(
                Q(name__icontains=q) |
                Q(topic__icontains=q) |
                Q(device_type__icontains=q)
            )
        return qs


@method_decorator(login_required, name="dispatch")
class DeviceDetailView(DetailView):
    model = Device
    template_name = "devices/detail.html"
    context_object_name = "device"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        meta = self.object.metadata or {}
        ctx["metadata_pretty"] = json.dumps(meta, indent=2, ensure_ascii=False)
        return ctx


@method_decorator(login_required, name="dispatch")
@method_decorator(role_required("admin"), name="dispatch")
class UserListView(ListView):
    model = User
    template_name = "users/list.html"
    context_object_name = "users"
    paginate_by = 20

    def get_queryset(self):
        # join to UserProfile to avoid N+1
        return User.objects.select_related("userprofile").order_by("username")


@method_decorator(login_required, name="dispatch")
@method_decorator(role_required("admin"), name="dispatch")
class UserDetailView(DetailView):
    model = User
    template_name = "users/detail.html"
    context_object_name = "u"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # convenient alias to avoid template errors if no profile exists yet
        ctx["profile"] = getattr(self.object, "userprofile", None)
        return ctx
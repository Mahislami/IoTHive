from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .utils import publish_device_update_like_simulator
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
from users.permissions import role_required
from django.urls import reverse
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.db.models import Q
from django.urls import reverse_lazy
from django.contrib import messages


from .models import Device
from .forms import DeviceForm
from .permissions import role_required  # or from users.permissions import role_required


# Existing API views
class DeviceCreateView(generics.CreateAPIView):
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer

class DeviceListView(generics.ListAPIView):
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer

# New form-based device registration view
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


@method_decorator([login_required, role_required("admin", "operator")], name="dispatch")
class DeviceCreateView(CreateView):
    model = Device
    form_class = DeviceForm
    template_name = "devices/edit.html"
    success_url = reverse_lazy("devices:list")


@method_decorator([login_required, role_required("admin", "operator")], name="dispatch")
class DeviceUpdateView(UpdateView):
    model = Device
    form_class = DeviceForm
    template_name = "devices/edit.html"
    success_url = reverse_lazy("devices:list")

    def form_valid(self, form):
        # Determine if status changed so we don’t spam MQTT on unrelated edits
        status_changed = "status" in form.changed_data
        response = super().form_valid(form)  # saves self.object

        if status_changed:
            device = self.object
            try:
                publish_device_update_like_simulator(device)
                messages.success(self.request, "Device updated and MQTT message published.")
            except Exception as e:
                messages.error(self.request, f"Device saved, but MQTT publish failed: {e}")
        return response


@login_required
@role_required("admin", "operator")
def device_delete(request, pk):
    device = get_object_or_404(Device, pk=pk)
    if request.method == "POST":
        device.delete()
        messages.success(request, "Device deleted.")
        return redirect("devices:list")
    # Fallback confirm if someone GETs the URL
    return render(request, "devices/confirm_delete.html", {"device": device})

def signup_view(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
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
            "href": "http://localhost:3000/login",  # TODO: replace
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
        menu.insert(1, {  # 👈 NEW: New Device card
            "key": "device_new",
            "label": "New Device",
            "href": reverse("devices:create"),
            "desc": "Create a new device",
        })

    if role == "admin":
        menu.append({
            "key": "users",
            "label": "Manage Users",
            "href": reverse("users:list"),
            "desc": "Create, disable, or edit users",
        })
        menu.append({     # 👈 NEW: New User card
            "key": "user_new",
            "label": "New User",
            "href": reverse("users:create"),
            "desc": "Create a new user",
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
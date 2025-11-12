import json
from urllib.parse import urljoin

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST, require_GET
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from rest_framework import generics

from users.permissions import role_required

from .appliances import (
    APPLIANCE_SPECS,
    APPLIANCE_DEVICE_TYPES,
    get_appliance_illustration,
    get_device_illustration,
)
from .forms import DeviceForm, KitchenApplianceForm, SignUpForm, StyledAuthenticationForm
from .models import Device, UserProfile, AlarmRule, AlarmEvent
from .serializers import DeviceSerializer
from .timers import supports_timer, start_timer, update_timer_runtime
from .utils import (
    publish_device_update_like_simulator,
    load_device_metadata,
    save_device_metadata,
)


def _resolve_device_type_for_form(form):
    if not form:
        return Device.DEVICE_TYPES[0][0]
    selected = getattr(form, "selected_type", None)
    if selected:
        return selected
    if hasattr(form, "data") and form.data.get("device_type"):
        return form.data["device_type"]
    if form.initial.get("device_type"):
        return form.initial["device_type"]
    instance = getattr(form, "instance", None)
    if instance and getattr(instance, "device_type", None):
        return instance.device_type
    return Device.DEVICE_TYPES[0][0]


def _grafana_base_url(request):
    configured = getattr(settings, "GRAFANA_PUBLIC_URL", "").strip()
    if configured:
        return configured if configured.endswith("/") else f"{configured}/"
    derived = request.build_absolute_uri("/grafana/")
    return derived if derived.endswith("/") else f"{derived}/"


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

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["appliance_types"] = APPLIANCE_SPECS.keys()
        return ctx


@method_decorator(login_required, name="dispatch")
class DeviceDetailView(DetailView):
    model = Device
    template_name = "devices/detail.html"
    context_object_name = "device"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        meta = load_device_metadata(self.object)
        ctx["metadata_pretty"] = json.dumps(meta, indent=2, ensure_ascii=False)
        ctx["current_power"] = round(self.object.current_power_watts or 0, 2)
        ctx["power_capacity"] = self.object.power_rating_watts
        ctx["appliance_spec"] = APPLIANCE_SPECS.get(self.object.device_type)
        ctx["cycle_progress"] = meta.get("cycle_progress")
        ctx["can_control"] = (
            self.request.user.is_authenticated
            and hasattr(self.request.user, "userprofile")
            and self.request.user.userprofile.role in ("admin", "operator")
            and self.object.device_type in APPLIANCE_SPECS
        )
        return ctx


@method_decorator([login_required, role_required("admin", "operator")], name="dispatch")
class DeviceCreateView(CreateView):
    model = Device
    form_class = DeviceForm
    template_name = "devices/edit.html"
    success_url = reverse_lazy("devices:list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        form = ctx.get("form")
        device_type = _resolve_device_type_for_form(form)
        ctx["device_schematic_svg"] = get_device_illustration(device_type)
        ctx["device_schematic_label"] = device_type.replace("_", " ").title()
        ctx["device_schematics_map"] = {
            value: get_device_illustration(value)
            for value, _ in Device.DEVICE_TYPES
            if value not in APPLIANCE_DEVICE_TYPES
        }
        ctx["current_device_type"] = device_type
        return ctx


@method_decorator([login_required, role_required("admin", "operator")], name="dispatch")
class DeviceUpdateView(UpdateView):
    model = Device
    form_class = DeviceForm
    template_name = "devices/edit.html"
    success_url = reverse_lazy("devices:list")

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.device_type in APPLIANCE_DEVICE_TYPES:
            return redirect("devices:kitchen_edit", pk=obj.pk)
        self.object = obj
        return super().dispatch(request, *args, **kwargs)

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

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["device_type"].disabled = True
        return form


@method_decorator([login_required, role_required("admin", "operator")], name="dispatch")
class KitchenApplianceListView(ListView):
    model = Device
    template_name = "devices/kitchen/list.html"
    context_object_name = "devices"
    paginate_by = 20

    def get_queryset(self):
        return (Device.objects
                .filter(device_type__in=APPLIANCE_SPECS.keys())
                .order_by("-created_at"))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["available_types"] = APPLIANCE_DEVICE_TYPES
        ctx["illustrations"] = {dt: get_appliance_illustration(dt) for dt in APPLIANCE_DEVICE_TYPES}
        return ctx


class KitchenApplianceFormViewMixin:
    form_class = KitchenApplianceForm
    template_name = "devices/kitchen/form.html"
    success_url = reverse_lazy("devices:kitchen_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        initial = kwargs.get("initial", {}).copy()
        selected_type = initial.get("device_type") or None
        current_object = getattr(self, "object", None)
        if current_object and not selected_type:
            selected_type = current_object.device_type
        if not selected_type:
            selected_type = self.request.GET.get("device_type") or APPLIANCE_DEVICE_TYPES[0]
        initial["device_type"] = selected_type
        kwargs["initial"] = initial
        kwargs["request"] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["available_types"] = APPLIANCE_DEVICE_TYPES
        form = ctx.get("form")
        if form:
            ctx["illustration"] = form.illustration_svg
            ctx["appliance_field_configs"] = form.appliance_field_configs
            ctx["selected_type"] = getattr(form, "selected_type", None)
        return ctx


@method_decorator([login_required, role_required("admin", "operator")], name="dispatch")
class KitchenApplianceCreateView(KitchenApplianceFormViewMixin, CreateView):
    model = Device

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["is_edit"] = False
        return ctx


@method_decorator([login_required, role_required("admin", "operator")], name="dispatch")
class KitchenApplianceUpdateView(KitchenApplianceFormViewMixin, UpdateView):
    model = Device

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field_name in ("device_type", "status", "target_temperature", "mode"):
            if field_name in form.fields:
                form.fields[field_name].disabled = True
        return form

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["is_edit"] = True
        form = ctx.get("form")
        device_type = _resolve_device_type_for_form(form)
        ctx["device_schematic_svg"] = get_device_illustration(device_type)
        ctx["device_schematic_label"] = device_type.replace("_", " ").title()
        ctx["device_schematics_map"] = {
            value: get_device_illustration(value)
            for value, _ in Device.DEVICE_TYPES
            if value not in APPLIANCE_DEVICE_TYPES
        }
        ctx["current_device_type"] = device_type
        return ctx


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


@login_required
@role_required("admin", "operator")
def device_control(request, pk):
    device = get_object_or_404(Device, pk=pk)
    if device.device_type not in APPLIANCE_SPECS:
        messages.error(request, "Controls are only available for managed appliances.")
        return redirect("devices:detail", pk=pk)

    meta = load_device_metadata(device)
    spec = APPLIANCE_SPECS.get(device.device_type)
    timer_supported = supports_timer(device.device_type)

    if request.method == "POST":
        update_fields = []
        meta_changed = False

        desired_status = request.POST.get("status")
        if desired_status in ("on", "off"):
            desired_bool = desired_status == "on"
            if desired_bool != device.status:
                device.status = desired_bool
                update_fields.append("status")

        target_temp = request.POST.get("target_temperature")
        if target_temp:
            try:
                temp_val = float(target_temp)
                if device.target_temperature != temp_val:
                    device.target_temperature = temp_val
                    update_fields.append("target_temperature")
            except ValueError:
                messages.error(request, "Temperature must be a number.")
                return redirect("devices:control", pk=pk)

        mode = request.POST.get("mode")
        if mode and mode != device.mode:
            device.mode = mode
            update_fields.append("mode")

        cycle = request.POST.get("cycle")
        if cycle and spec.get("cycles"):
            meta["cycle"] = cycle
            meta_changed = True
        if request.POST.get("reset_cycle") == "on":
            meta["cycle_progress"] = 0
            meta_changed = True

        timer_action = request.POST.get("timer_action")
        if timer_supported:
            if timer_action == "start":
                minutes_raw = request.POST.get("timer_minutes")
                try:
                    minutes = int(minutes_raw)
                except (TypeError, ValueError):
                    messages.error(request, "Timer duration must be a whole number of minutes.")
                    return redirect("devices:control", pk=pk)
                if minutes < 1 or minutes > 240:
                    messages.error(request, "Timer duration must be between 1 and 240 minutes.")
                    return redirect("devices:control", pk=pk)
                meta["timer"] = start_timer(minutes)
                if spec.get("cycles"):
                    meta["cycle_progress"] = 0
                meta_changed = True
                if not device.status:
                    device.status = True
                    update_fields.append("status")
            elif timer_action == "cancel":
                if meta.pop("timer", None):
                    meta_changed = True
                    if device.status:
                        device.status = False
                        update_fields.append("status")

        if meta_changed and update_fields:
            save_device_metadata(
                device,
                meta,
                update_fields=tuple(set(update_fields + ["metadata"])),
            )
            update_fields = []
        elif meta_changed:
            save_device_metadata(device, meta)

        if update_fields:
            device.save(update_fields=update_fields)

        publish_device_update_like_simulator(device)
        messages.success(request, "Device control update published to MQTT.")
        return redirect("devices:detail", pk=pk)

    timer_context = None
    if timer_supported:
        timer_data = meta.get("timer")
        if timer_data:
            timer_context, _ = update_timer_runtime(dict(timer_data))
            remaining = timer_context.get("remaining_seconds")
            if remaining is not None:
                mins, secs = divmod(int(remaining), 60)
                timer_context["remaining_label"] = f"{mins:02d}:{secs:02d}"
    timer_initial_minutes = (timer_context or {}).get("duration_minutes") or 10

    context = {
        "device": device,
        "spec": spec,
        "meta": meta,
        "status_on": device.status,
        "timer_supported": timer_supported,
        "timer": timer_context,
        "timer_initial_minutes": timer_initial_minutes,
    }
    return render(request, "devices/control.html", context)

@login_required
@role_required("admin")
def signup_view(request):
    """Restricted sign-up flow for administrators to provision new users."""
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(
                request,
                _("Created account %(username)s with role %(role)s.") % {
                    "username": user.username,
                    "role": user.userprofile.role,
                },
            )
            return redirect('users:list')
    else:
        form = SignUpForm()
    return render(request, 'signup.html', {'form': form})


@login_required
def dashboard_view(request):
    user = request.user
    role = getattr(getattr(user, 'userprofile', None), 'role', 'visitor')
    grafana_base = _grafana_base_url(request)
    grafana_login_url = urljoin(grafana_base, "login")
    grafana_dashboards_url = urljoin(grafana_base, "dashboards")
    grafana_power_url = urljoin(
        grafana_base,
        "d/e2e3ebfb-6d61-491c-8880-ff9d4a2cdaf5/energy-command-center?orgId=1",
    )

    # Common item
    menu = [
        {
            "key": "grafana",
            "label": _("Grafana Dashboard"),
            "href": grafana_dashboards_url,
            "desc": _("View metrics and charts"),
            "icon": "activity",
            "requires_grafana_login": True,
        },
        {
            "key": "power_grafana",
            "label": _("Power Usage"),
            "href": grafana_power_url,
            "desc": _("Track appliance energy consumption"),
            "icon": "zap",
            "requires_grafana_login": True,
        },
    ]

    if role in ("admin", "operator"):
        menu.insert(0, {
            "key": "devices",
            "label": _("Manage Devices"),
            "href": reverse("devices:list"),
            "desc": _("Add, remove, or edit devices"),
            "icon": "cpu",
        })
        menu.insert(1, {
            "key": "device_new",
            "label": _("New Device"),
            "href": reverse("devices:create"),
            "desc": _("Create a new device"),
        })
        menu.insert(2, {
            "key": "kitchen",
            "label": _("Kitchen Appliances"),
            "href": reverse("devices:kitchen_list"),
            "desc": _("Dedicated controls for ovens, kettles, etc."),
            "icon": "chef-hat",
        })
        menu.append({
            "key": "alarm_rules",
            "label": _("Alarm Rules"),
            "href": reverse("devices:alarm_rules"),
            "desc": _("Set thresholds / states per device"),
        })
        menu.append({
            "key": "active_alarms",
            "label": _("Active Alarms"),
            "href": reverse("devices:active_alarms"),
            "desc": _("See and manage raised alarms"),
        })

    if role == "admin":
        menu.append({
            "key": "users",
            "label": _("Manage Users"),
            "href": reverse("users:list"),
            "desc": _("Create, disable, or edit users"),
        })
        menu.append({
            "key": "user_new",
            "label": _("New User"),
            "href": reverse("users:create"),
            "desc": _("Create a new user"),
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
        meta = load_device_metadata(self.object)
        ctx["metadata_pretty"] = json.dumps(meta, indent=2, ensure_ascii=False)
        ctx["current_power"] = round(self.object.current_power_watts or 0, 2)
        ctx["power_capacity"] = self.object.power_rating_watts
        ctx["appliance_spec"] = APPLIANCE_SPECS.get(self.object.device_type)
        ctx["cycle_progress"] = meta.get("cycle_progress")
        ctx["can_control"] = (
            self.request.user.is_authenticated
            and hasattr(self.request.user, "userprofile")
            and self.request.user.userprofile.role in ("admin", "operator")
            and self.object.device_type in APPLIANCE_SPECS
        )
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


@login_required
@role_required("admin", "operator")
@require_GET
def alarm_rules(request):
    # Devices + a map of active rule per device (single rule per device UX)
    devices = Device.objects.all().order_by("name")
    rules_map = {r.device_id: r for r in AlarmRule.objects.filter(active=True)}
    return render(
        request,
        "devices/monitoring/alarm_rules.html",
        {
            "devices": devices,
            "kitchen_devices": [d for d in devices if d.device_type in APPLIANCE_SPECS],
            "rules_map": rules_map,
            "user_display": request.user.username,  # for header (same as dashboard)
            "role": getattr(getattr(request.user, "userprofile", None), "role", "visitor"),
        },
    )


@login_required
@role_required("admin", "operator")
@require_POST
def save_alarm_rule(request):
    device = get_object_or_404(Device, id=request.POST.get("device_id"))
    rule, _ = AlarmRule.objects.get_or_create(device=device, defaults={"created_by": request.user})

    # numeric (sensor/thermostat) vs boolean (switch/light/actuator)
    if device.device_type in ("sensor", "thermostat"):
        mn = request.POST.get("min_value") or None
        mx = request.POST.get("max_value") or None
        rule.min_value = float(mn) if mn is not None else None
        rule.max_value = float(mx) if mx is not None else None
        rule.expected_state = None
    else:
        es = request.POST.get("expected_state")
        rule.expected_state = (es == "on") if es in ("on", "off") else None
        rule.min_value = None
        rule.max_value = None

    rule.severity = request.POST.get("severity", rule.severity)
    rule.note = request.POST.get("note", "")
    rule.active = (request.POST.get("active") == "on")
    rule.save()

    return redirect("devices:alarm_rules")


@login_required
@role_required("admin", "operator")
@require_GET
def active_alarms(request):
    events = (
        AlarmEvent.objects.filter(is_active=True)
        .select_related("device", "rule")
        .order_by("-created_at")
    )
    return render(
        request,
        "devices/monitoring/active_alarms.html",
        {
            "events": events,
            "user_display": request.user.username,  # for header (same as dashboard)
            "role": getattr(getattr(request.user, "userprofile", None), "role", "visitor"),
        },
    )


@login_required
@role_required("admin", "operator")
@require_POST
def ack_alarm(request, event_id):
    ev = get_object_or_404(AlarmEvent, id=event_id)
    ev.acknowledged = True
    ev.save(update_fields=["acknowledged"])
    return redirect("devices:active_alarms")


@login_required
@role_required("admin", "operator")
@require_POST
def clear_alarm(request, event_id):
    ev = get_object_or_404(AlarmEvent, id=event_id)
    ev.clear()
    return redirect("devices:active_alarms")

@login_required
@role_required("admin", "operator")
@require_POST
def clear_alarm(request, event_id):
    ev = get_object_or_404(AlarmEvent, id=event_id)
    ev.clear()
    return redirect("devices:active_alarms")

import json
from urllib.parse import urljoin

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
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
from .models import Device, UserProfile, AlarmRule, AlarmEvent, Recommendation, MetricChoices
from .alarms import evaluate_device_alarms
from .serializers import DeviceSerializer
from .timers import supports_timer, start_timer, update_timer_runtime, timer_optional
from .utils import (
    publish_device_update_like_simulator,
    load_device_metadata,
    save_device_metadata,
)


def _remove_duplicate_rules(device: Device, metric: str, keep_rule: AlarmRule):
    """Delete other rules for this device/metric, clearing their active alarms first."""
    dupes = AlarmRule.objects.filter(device=device, metric=metric).exclude(id=keep_rule.id)
    if not dupes.exists():
        return
    AlarmEvent.objects.filter(rule__in=dupes, is_active=True).update(
        is_active=False,
        cleared_at=timezone.now(),
    )
    dupes.delete()


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

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            _('Device "%(name)s" created successfully.') % {"name": self.object.name},
        )
        return response


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
        messages.success(
            self.request,
            _('Device "%(name)s" updated successfully.') % {"name": self.object.name},
        )

        if status_changed:
            device = self.object
            try:
                publish_device_update_like_simulator(device)
            except Exception as e:
                messages.error(
                    self.request,
                    _('Device saved, but MQTT publish failed: %(error)s') % {"error": e},
                )
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

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            _('Device "%(name)s" created successfully.') % {"name": self.object.name},
        )
        return response


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

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            _('Device "%(name)s" updated successfully.') % {"name": self.object.name},
        )
        return response


@login_required
@role_required("admin", "operator")
def device_delete(request, pk):
    device = get_object_or_404(Device, pk=pk)
    if request.method == "POST":
        device.delete()
        messages.success(request, _('Device "%(name)s" removed successfully.') % {"name": device.name})
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
    timer_is_optional = timer_optional(device.device_type) if timer_supported else False

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
        "timer_optional": timer_is_optional,
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

    # Common item
    menu = [
        {
            "key": "grafana",
            "label": _("Grafana Dashboard"),
            "href": grafana_dashboards_url,
            "desc": _("View metrics and charts"),
            "icon": "activity",
            "requires_grafana_login": False,
            "new_tab": True,
        },
        {
            "key": "recommendations",
            "label": _("Recommendations"),
            "href": reverse("devices:recommendations"),
            "desc": _("AI-assisted alarm and control suggestions"),
            "icon": "sparkles",
            "requires_grafana_login": False,
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
    # Show any existing rules per device/metric so saved thresholds are visible for editing
    rules_map = {}
    for r in (AlarmRule.objects
              .order_by("device_id", "metric", "-updated_at", "-id")):
        rules_map.setdefault(r.device_id, {})
        # keep the most recently updated rule per metric
        if r.metric not in rules_map[r.device_id]:
            rules_map[r.device_id][r.metric] = r
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
    metric = request.POST.get("metric")
    field = request.POST.get("field")
    if not metric:
        if device.device_type in ("sensor", "thermostat") or device.device_type in APPLIANCE_SPECS:
            metric = "temperature"
        elif device.device_type in ("switch", "light", "actuator"):
            metric = "state"
        else:
            metric = "reading"
    if not field:
        field = metric

    rule, created = AlarmRule.objects.get_or_create(
        device=device,
        metric=metric,
        field=field,
        defaults={"created_by": request.user}
    )

    # numeric (sensor/thermostat/appliances) vs boolean (switch/light/actuator)
    if metric in ("temperature", "power_w", "reading"):
        mn = request.POST.get("min_value") or None
        mx = request.POST.get("max_value") or None
        rule.min_value = float(mn) if mn is not None else None
        rule.max_value = float(mx) if mx is not None else None
        rule.expected_state = None
        rule.field = field or metric
    else:  # state expected for binary
        es = request.POST.get("expected_state")
        rule.expected_state = (es == "on") if es in ("on", "off") else None
        rule.min_value = None
        rule.max_value = None

    rule.severity = request.POST.get("severity", rule.severity)
    rule.note = request.POST.get("note", "")
    rule.active = (request.POST.get("active") == "on")
    rule.save()
    # Clear any active events tied to this rule so they re-evaluate with the new thresholds/settings.
    AlarmEvent.objects.filter(rule=rule, is_active=True).update(
        is_active=False,
        cleared_at=timezone.now(),
    )
    # Clear any other inactive-rule alarms on this device (covers previously disabled rules).
    inactive_rules = AlarmRule.objects.filter(device=device, active=False)
    if inactive_rules.exists():
        AlarmEvent.objects.filter(rule__in=inactive_rules, is_active=True).update(
            is_active=False,
            cleared_at=timezone.now(),
        )
    # Enforce a single rule per metric/device and clear alarms appropriately.
    if rule.active:
        siblings = AlarmRule.objects.filter(device=device, metric=metric).exclude(id=rule.id)
        if siblings.exists():
            siblings.update(active=False)
            AlarmEvent.objects.filter(rule__in=siblings, is_active=True).update(
                is_active=False,
                cleared_at=timezone.now(),
            )
    else:
        # If the rule was deactivated, clear any active alarms for this device/metric.
        AlarmEvent.objects.filter(
            device=device,
            is_active=True,
            rule__metric=metric,
        ).update(is_active=False, cleared_at=timezone.now())
    _remove_duplicate_rules(device, metric, rule)
    # Re-evaluate immediately so updated rules (including boolean state rules) raise/clear alarms without waiting for the next cycle.
    evaluate_device_alarms(device)

    return redirect("devices:alarm_rules")


@login_required
@role_required("admin", "operator")
@require_GET
def active_alarms(request):
    active_qs = AlarmEvent.objects.filter(is_active=True).select_related("device", "rule").order_by("-created_at")
    alerts = list(active_qs.exclude(severity="info"))
    notifications = list(active_qs.filter(severity="info"))
    history = list(
        AlarmEvent.objects.filter(is_active=False)
        .select_related("device", "rule")
        .order_by("-cleared_at", "-created_at")[:200]
    )
    requested_tab = request.GET.get("tab")
    if requested_tab not in {"alerts", "notifications", "history"}:
        requested_tab = "alerts" if alerts else ("notifications" if notifications else "history")
    return render(
        request,
        "devices/monitoring/active_alarms.html",
        {
            "alerts": alerts,
            "notifications": notifications,
            "history": history,
            "active_tab": requested_tab,
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
def recommendations_view(request):
    recs = (Recommendation.objects
            .filter(dismissed=False)
            .select_related("device")
            .order_by("-created_at"))

    def _localize(rec: Recommendation):
        # Apply translated labels for common recommendation templates
        title = rec.title or ""
        note = rec.target_note or ""
        if title.startswith("Set ") and title.endswith(" thresholds"):
            rec.title = _("Set %(device_type)s thresholds") % {"device_type": rec.device.get_device_type_display()}
            rec.message = _("Based on current readings, apply tighter min/max bounds.")
            rec.target_note = rec.target_note or ""
            rec.target_metric = rec.target_metric or MetricChoices.TEMPERATURE
        elif title.startswith("Expected state for "):
            rec.title = _("Expected state for %(device_type)s") % {"device_type": rec.device.get_device_type_display()}
            rec.message = _("Lock the expected state to reduce noise.")
            rec.target_note = rec.target_note or _("Alert when state changes unexpectedly.")
            rec.target_metric = rec.target_metric or MetricChoices.STATE
        elif title.startswith("Off-hours alert for "):
            rec.title = _("Off-hours alert for %(device)s") % {"device": rec.device.name}
            rec.message = _("Notify if this device toggles outside scheduled hours.")
            rec.target_note = note or _("Unexpected toggle outside schedule.")
            rec.target_metric = rec.target_metric or MetricChoices.STATE
        elif title.endswith(" safety band"):
            rec.title = _("%(device_type)s safety band") % {"device_type": rec.device.get_device_type_display()}
            rec.message = _("Apply bounds to catch overheating or abnormal power draw.")
            rec.target_note = rec.target_note or _("Use appliance spec temperature range.")
            rec.target_metric = rec.target_metric or MetricChoices.TEMPERATURE
        elif title.startswith("Data-driven thresholds for "):
            rec.title = _("Data-driven thresholds for %(device)s") % {"device": rec.device.name}
            rec.message = _("Derived from recent telemetry (IsolationForest inliers p5–p95).")
            rec.target_metric = rec.target_metric or MetricChoices.TEMPERATURE
        elif title.startswith("Maintenance reminder for "):
            rec.title = _("Maintenance reminder for %(device)s") % {"device": rec.device.name}
            rec.message = _("Add a note about filter cleaning or descale intervals.")
            rec.target_note = note or _("Track maintenance actions alongside alarms.")
            rec.target_metric = rec.target_metric or MetricChoices.READING
        elif title.startswith("Baseline rule for "):
            rec.title = _("Baseline rule for %(device)s") % {"device": rec.device.name}
            rec.message = _("Add a default rule so alarms can be tuned later.")
            rec.target_metric = rec.target_metric or MetricChoices.TEMPERATURE
        # else leave as-is; any target_note present gets translated by the template engine if wrapped elsewhere

    for rec in recs:
        _localize(rec)

    def _resolve_metric(rec: Recommendation):
        if rec.target_metric:
            return rec.target_metric
        if rec.target_expected_state is not None:
            return MetricChoices.STATE
        if rec.target_min_value is not None or rec.target_max_value is not None:
            dtype = getattr(rec.device, "device_type", "")
            if dtype == "thermostat":
                return MetricChoices.TEMPERATURE
            if dtype == "sensor":
                return MetricChoices.READING
            if dtype in APPLIANCE_SPECS:
                return MetricChoices.POWER_W
        return MetricChoices.TEMPERATURE

    def _group(recommendations):
        groups = {"numeric": [], "binary": [], "appliance": [], "other": []}
        for rec in recommendations:
            dtype = getattr(rec.device, "device_type", "")
            resolved_metric = _resolve_metric(rec)
            payload = {
                "id": rec.id,
                "severity": rec.severity,
                "title": rec.title,
                "message": rec.message,
                "device_name": rec.device.name,
                "created_at": rec.created_at,
                "acknowledged": rec.acknowledged,
                "implemented": rec.implemented,
                "target_min_value": rec.target_min_value,
                "target_max_value": rec.target_max_value,
                "target_expected_state": rec.target_expected_state,
                "target_note": rec.target_note,
                "metric": resolved_metric,
            }
            if dtype in ("sensor", "thermostat"):
                groups["numeric"].append(payload)
            elif dtype in ("switch", "light", "actuator"):
                groups["binary"].append(payload)
            elif dtype in APPLIANCE_SPECS:
                groups["appliance"].append(payload)
            else:
                groups["other"].append(payload)
        return groups

    def _default_cat(groups):
        for key in ("numeric", "binary", "appliance", "other"):
            if groups.get(key):
                return key
        return "numeric"

    actionable = [
        r for r in recs
        if (r.target_min_value is not None
            or r.target_max_value is not None
            or r.target_expected_state is not None
            or (r.target_note or "").strip())
    ]

    alerts = [r for r in actionable if r.severity in ("warn", "crit")]
    rec_notifications = [r for r in actionable if r.severity == "info"]
    history_recs = list(
        Recommendation.objects.filter(Q(dismissed=True) | Q(implemented=True))
        .select_related("device")
        .order_by("-updated_at")[:200]
    )
    requested_tab = request.GET.get("tab")
    if requested_tab not in {"alerts", "notifications", "history"}:
        requested_tab = "alerts" if alerts else ("notifications" if rec_notifications else "history")
    return render(
        request,
        "devices/monitoring/recommendations.html",
        {
            "alerts": alerts,
            "notifications": rec_notifications,
            "history_recs": history_recs,
            "alerts_grouped": _group(alerts),
            "notifications_grouped": _group(rec_notifications),
            "alerts_default_cat": _default_cat(_group(alerts)),
            "notifications_default_cat": _default_cat(_group(rec_notifications)),
            "active_tab": requested_tab,
            "user_display": request.user.username,
            "role": getattr(getattr(request.user, "userprofile", None), "role", "visitor"),
        },
    )


@login_required
@role_required("admin", "operator")
@require_POST
def acknowledge_recommendation(request, rec_id):
    rec = get_object_or_404(Recommendation, id=rec_id, dismissed=False)
    if not rec.acknowledged:
        rec.acknowledged = True
        rec.save(update_fields=["acknowledged", "updated_at"])
    tab = request.POST.get("tab") or "alerts"
    return redirect(f"{reverse('devices:recommendations')}?tab={tab}")


@login_required
@role_required("admin", "operator")
@require_POST
def implement_recommendation(request, rec_id):
    rec = get_object_or_404(Recommendation, id=rec_id, dismissed=False)
    # Resolve a sensible metric if target_metric is missing
    if rec.target_metric:
        metric = rec.target_metric
    elif rec.target_expected_state is not None:
        metric = MetricChoices.STATE
    elif rec.target_min_value is not None or rec.target_max_value is not None:
        dtype = getattr(rec.device, "device_type", "")
        if dtype == "thermostat":
            metric = MetricChoices.TEMPERATURE
        elif dtype == "sensor":
            metric = MetricChoices.READING
        elif dtype in APPLIANCE_SPECS:
            metric = MetricChoices.POWER_W
        else:
            metric = MetricChoices.TEMPERATURE
    else:
        metric = MetricChoices.TEMPERATURE
    # Avoid MultipleObjectsReturned by selecting or creating a single rule for this device/metric
    rule = (AlarmRule.objects
            .filter(device=rec.device, metric=metric)
            .order_by("-updated_at", "-id")
            .first())
    if not rule:
        rule = AlarmRule.objects.create(
            device=rec.device,
            metric=metric,
            field=metric,
            created_by=request.user,
        )
    if not rule.field:
        rule.field = metric
    rule.min_value = rec.target_min_value
    rule.max_value = rec.target_max_value
    rule.expected_state = rec.target_expected_state
    rule.severity = rec.target_severity or rec.severity or rule.severity
    rule.note = rec.target_note or rec.title
    rule.active = True
    rule.save()

    # Clear alarms tied to this rule and any inactive rules; enforce single active rule per device
    AlarmEvent.objects.filter(rule=rule, is_active=True).update(
        is_active=False,
        cleared_at=timezone.now(),
    )
    inactive_rules = AlarmRule.objects.filter(device=rec.device, active=False)
    if inactive_rules.exists():
        AlarmEvent.objects.filter(rule__in=inactive_rules, is_active=True).update(
            is_active=False,
            cleared_at=timezone.now(),
        )
    siblings = AlarmRule.objects.filter(device=rec.device, metric=metric).exclude(id=rule.id)
    if siblings.exists():
        siblings.update(active=False)
        AlarmEvent.objects.filter(rule__in=siblings, is_active=True).update(
            is_active=False,
            cleared_at=timezone.now(),
        )
    _remove_duplicate_rules(rec.device, metric, rule)
    evaluate_device_alarms(rec.device)

    rec.implemented = True
    rec.acknowledged = True
    rec.save(update_fields=["implemented", "acknowledged", "updated_at"])

    messages.success(
        request,
        _('Recommendation "%(title)s" applied to %(device)s.') % {
            "title": rec.title,
            "device": rec.device.name,
        },
    )
    tab = request.POST.get("tab") or "alerts"
    return redirect(f"{reverse('devices:recommendations')}?tab={tab}")


@login_required
@role_required("admin", "operator")
@require_POST
def dismiss_recommendation(request, rec_id):
    rec = get_object_or_404(Recommendation, id=rec_id, dismissed=False)
    rec.dismissed = True
    rec.save(update_fields=["dismissed", "updated_at"])
    tab = request.POST.get("tab") or "alerts"
    return redirect(f"{reverse('devices:recommendations')}?tab={tab}")
@login_required
@role_required("admin", "operator")
@require_POST
def clear_alarm(request, event_id):
    ev = get_object_or_404(AlarmEvent, id=event_id)
    ev.clear()
    return redirect("devices:active_alarms")

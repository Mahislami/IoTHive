from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView
from django.contrib.auth.models import User
from django.db.models import Q
from django.views.generic import UpdateView
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse_lazy
from django.contrib import messages
from django.views.generic import CreateView
from .forms import UserCreateForm

from .forms import UserAdminForm
from .permissions import role_required

from .permissions import role_required
# ↓ change 'yourapp' to the app where UserProfile is defined
from devices.models import UserProfile


@method_decorator([login_required, role_required("admin")], name="dispatch")
class UserListView(ListView):
    model = User
    template_name = "users/list.html"
    context_object_name = "users"
    paginate_by = 20

    def get_queryset(self):
        qs = User.objects.select_related("userprofile").order_by("username")
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(
                Q(username__icontains=q) |
                Q(email__icontains=q) |
                Q(userprofile__role__icontains=q)
            )
        return qs


@method_decorator([login_required, role_required("admin")], name="dispatch")
class UserDetailView(DetailView):
    model = User
    template_name = "users/detail.html"
    context_object_name = "u"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["profile"] = getattr(self.object, "userprofile", None)  # may be None
        return ctx

@method_decorator([login_required, role_required("admin")], name="dispatch")
class UserUpdateView(UpdateView):
    model = User
    form_class = UserAdminForm
    template_name = "users/edit.html"
    context_object_name = "u"
    success_url = reverse_lazy("users:list")

@login_required
@role_required("admin")
def user_delete(request, pk):
    u = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        if u == request.user:
            messages.error(request, "You can’t delete your own account.")
            return redirect("users:edit", pk=pk)
        u.delete()
        messages.success(request, "User deleted.")
        return redirect("users:list")
    # fallback confirm page if someone GETs this URL
    return render(request, "users/confirm_delete.html", {"u": u})

@method_decorator([login_required, role_required("admin")], name="dispatch")
class UserCreateView(CreateView):
    form_class = UserCreateForm
    template_name = "users/create.html"
    success_url = reverse_lazy("users:list")
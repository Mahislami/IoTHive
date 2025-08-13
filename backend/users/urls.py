from django.urls import path
from .views import UserListView, UserDetailView, UserUpdateView, user_delete, UserCreateView

app_name = "users"

urlpatterns = [
    path("", UserListView.as_view(), name="list"),
    path("<int:pk>/", UserDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", UserUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", user_delete, name="delete"),
    path("create/", UserCreateView.as_view(), name="create"),
]

from django.core.exceptions import PermissionDenied

def role_required(*allowed_roles):
    def decorator(view_func):
        def _wrapped(request, *args, **kwargs):
            role = getattr(getattr(request.user, 'userprofile', None), 'role', 'visitor')
            if role in allowed_roles:
                return view_func(request, *args, **kwargs)
            raise PermissionDenied
        return _wrapped
    return decorator
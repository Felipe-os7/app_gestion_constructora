from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


def get_role(user):
    return getattr(getattr(user, "perfil", None), "rol", None)


def is_jefe_obra(user):
    return user.is_authenticated and (user.is_staff or get_role(user) == "jefe_obra")


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if get_role(request.user) not in roles and not request.user.is_staff:
                messages.error(request, "No tienes permisos para realizar esta acción.")
                return redirect("index")
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator


jefe_obra_required = role_required("jefe_obra")

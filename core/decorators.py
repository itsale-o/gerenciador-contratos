from django.contrib import messages
from django.shortcuts import redirect
from functools import wraps

def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        
        if not request.user.groups.filter(name="Admin").exists():
            messages.error(request, "Você não tem permissão para acessar essa página.")
            return redirect("core:home")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view
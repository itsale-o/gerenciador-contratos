from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required


@login_required
def dashboard_redirect(request):
    user = request.user

    if user.groups.filter(name="Admin").exists():
        return redirect("contratos:dashboard_admin")
    
    if user.groups.filter(name="Vendedor").exists():
        return redirect("contratos:dashboard_vendedor")
    
    return redirect("login")
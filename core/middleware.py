import time

from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils import timezone


class SessionTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.timeout = 1200  

    def __call__(self, request):
        if request.user.is_authenticated:
            current_time = time.time()
            last_activity = request.session.get("last_activity")

            if last_activity and (current_time - last_activity) > self.timeout:
                vendedor = getattr(request.user, "perfil_vendedor", None)
                if vendedor:
                    vendedor.ramal = None
                    vendedor.ultimo_acesso = timezone.now()
                    vendedor.save(update_fields=["ramal", "ultimo_acesso"])

                logout(request)
                messages.warning(request, "Sua sessão expirou por inatividade.")
                return redirect("login")

            request.session["last_activity"] = current_time

            vendedor = getattr(request.user, "perfil_vendedor", None)
            if vendedor:
                vendedor.ultimo_acesso = timezone.now()
                vendedor.save(update_fields=["ultimo_acesso"])

        return self.get_response(request)
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse


class GroupRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    groups_required = []
    allow_superuser = True
    return_json = False

    def test_func(self):
        user = self.request.user

        if not user.is_authenticated:
            return False

        if self.allow_superuser and user.is_superuser:
            return True

        if not self.groups_required:
            return False

        return user.groups.filter(name__in=self.groups_required).exists()

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()

        if self.return_json:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "Acesso negado."
                },
                status=403,
            )

        raise PermissionDenied



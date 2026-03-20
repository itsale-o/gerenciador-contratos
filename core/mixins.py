from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied


class GroupRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    group_required = None

    def test_func(self):
        return (
            self.request.user.is_authenticated
            and self.group_required
            and self.request.user.groups.filter(name=self.group_required).exists()
        )
    
    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied
    

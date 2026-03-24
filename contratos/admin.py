from django.contrib import admin

from .models import *

class ReadOnlyAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        fields = [f.name for f in self.model._meta.fields]
        fields += [m2m.name for m2m in self.model._meta.many_to_many]

        return fields
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Contrato)
class ContratoAdmin(ReadOnlyAdmin):
    pass

@admin.register(ClaroEndereco)
class ClaroEnderecoAdmin(ReadOnlyAdmin):
    pass

# @admin.register(Cdr)
# class CdrAdmin(ReadOnlyAdmin):
#     pass

@admin.register(AuditoriaCdr)
class AuditoriaCdrAdmin(ReadOnlyAdmin):
    pass


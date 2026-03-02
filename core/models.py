from django.conf import settings
from django.db import models


class Lead(models.Model):
    vendedor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="leads")
    contrato_id = models.IntegerField()
    data_atribuicao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.vendedor.username} - {self.contrato_id}"

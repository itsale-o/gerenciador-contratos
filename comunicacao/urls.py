from django.urls import path
from .views import contatar_cliente

app_name = "comms" 

urlpatterns = [
    path("contatar-cliente/<int:contrato_id>/", contatar_cliente, name="contatar_cliente"),
]
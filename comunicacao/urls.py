from django.urls import path
from .views import *

app_name = "comms" 

urlpatterns = [
    path("contatar-cliente/<int:contrato_id>/", contatar_cliente, name="contatar_cliente"),
    path("acompanhar-chamada/", acompanhar_chamada, name="acompanhar_chamada"),
    path("cancelar-ligacao/", cancelar_ligacao, name="cancelar_ligacao"),
]
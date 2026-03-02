from django.urls import path
from .views import *

app_name = "contratos"

urlpatterns = [
    path("admin-dashboard/", DashboardAdmin.as_view(), name="dashboard_admin"),
    path("enderecos", ListaArruamento.as_view(), name="lista_arruamento"),
    path("contratos", ListaContratos.as_view(), name="lista_contratos"),
    path("leads/<int:pk>", LeadsEndereco.as_view(), name="leads_endereco"),

    path("carregar-bairros", carregar_bairros, name="carregar_bairros"),
    path("carregar-ruas", carregar_ruas, name="carregar_ruas"),
]
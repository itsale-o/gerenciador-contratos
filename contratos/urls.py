from django.urls import path
from .views import *

app_name = "contratos"

urlpatterns = [
    path("admin-dashboard/", DashboardAdmin.as_view(), name="dashboard_admin"),
    path("vendedor-dashboard", DashboardVendedor.as_view(), name="dashboard_vendedor"),
    path("enderecos", ListaArruamento.as_view(), name="lista_arruamento"),
    path("contratos", ListaContratos.as_view(), name="lista_contratos"),
    path("leads/<int:pk>", LeadsEndereco.as_view(), name="leads_endereco"),
    path("bairro/leads", ListaLeadsBairro.as_view(), name="leads_bairro"),
    path("bairro/leads/contrato/<int:pk>", DetalhesContrato.as_view(), name="detalhes_contrato"),
    path("atribuir-lead", AtribuirLead.as_view(), name="atribuir_lead"),

    path("carregar-bairros", carregar_bairros, name="carregar_bairros"),
]
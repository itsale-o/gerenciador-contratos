from django.urls import path

from .views import *


app_name = "core"

urlpatterns = [
    path("", dashboard_redirect, name="home"),
    path("dashboard-administrativo/", DashboardAdmin.as_view(), name="dashboard_admin"),
    path("dashboard-vendedor", DashboardVendedor.as_view(), name="dashboard_vendedor"),
    path("contratos", ListaContratos.as_view(), name="lista_contratos"),
    path("enderecos", ListaArruamento.as_view(), name="lista_arruamento"),
    path("vendedores", ListaVendedores.as_view(), name="lista_vendedores"),
    path("leads", ListaLeadsVendedor.as_view(), name="lista_leads_vendedor"),
    path("leads/<int:pk>", DetalhesLead.as_view(), name="detalhes_lead"),
    path("atribuir-lead/<int:pk>", DetalhesContrato.as_view(), name="detalhes_contrato"),

    path("bairro/leads", ListaLeadsBairro.as_view(), name="leads_bairro"),
    path("carregar-bairros", carregar_bairros, name="carregar_bairros"),
    path("atribuir-lead", AtribuirLead.as_view(), name="atribuir_lead"),
    path("contratos/<int:pk>/ligar/", ligar_cliente, name="ligar_cliente"),
]
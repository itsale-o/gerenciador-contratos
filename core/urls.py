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
    path("vendedores/<int:pk>", DetalhesVendedor.as_view(), name="detalhes_vendedor"),
    path("leads", ListaLeadsVendedor.as_view(), name="lista_leads_vendedor"),
    path("leads/<int:pk>", DetalhesLead.as_view(), name="detalhes_lead"),
    path("lead/status/<int:contrato_id>/", salvar_status_lead, name="salvar_status_lead"),
    path("atribuir-lead/<int:pk>", DetalhesContrato.as_view(), name="detalhes_contrato"),
    path("atribuir-leads-em-massa", atribuir_leads_massa, name="atribuir_leads_massa"),

    path("bairro/leads", ListaLeadsBairro.as_view(), name="leads_bairro"),
    path("carregar-bairros", carregar_bairros, name="carregar_bairros"),
    path("atribuir-lead", AtribuirLead.as_view(), name="atribuir_lead"),
    path("contatar-cliente/<int:contrato_id>/", contatar_cliente, name="contatar_cliente"),

    path("api/dashboard/leads-distribuicao/", DashboardLeadsDistribuicaoAPI.as_view(), name="api_leads_distribuicao"),
    path("api/dashboard/vendas-mes/", DashboardVendasMesAPI.as_view(), name="api_vendas_mes"),
    path("api/dashboard/retornos-urgentes/", DashboardRetornosUrgentesAPI.as_view(), name="api_retornos_urgentes"),
    path("api/dashboard/sessoes-ligacao/", DashboardSessoesLigacaoAPI.as_view(), name="api_sessoes_ligacao"),
    path("api/dashboard/tentativas-ligacao/", DashboardTentativasLigacaoAPI.as_view(), name="api_tentativas_ligacao"),
    path("api/dashboard/leads-sem-contato/", DashboardLeadsSemContatoAPI.as_view(), name="api_leads_sem_contato"),
    path("api/dashboard/leads-com-contato/", DashboardLeadsComContatoAPI.as_view(), name="api_leads_com_contato"),
    path("api/dashboard/leads-sem-venda/", DashboardLeadsSemVendaAPI.as_view(), name="api_leads_sem_venda"),
    path("api/dashboard/leads-nao-venda/", DashboardLeadsNaoVendaAPI.as_view(), name="api_leads_nao_venda"),
    path("api/dashboard/leads-caro/", DashboardLeadsCaroAPI.as_view(), name="api_leads_caro"),
    path("api/dashboard/leads-sem-interesse/", DashboardLeadsSemInteresseAPI.as_view(), name="api_leads_sem_interesse"),
    path("api/dashboard/reatribuir-lead/", DashboardReatribuirLeadAPI.as_view(), name="api_reatribuir_lead"),
    path("api/dashboard/vendedores-ativos/", DashboardVendedoresAtivosAPI.as_view(), name="api_vendedores_ativos"),
]
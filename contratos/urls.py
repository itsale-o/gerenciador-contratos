from django.urls import path
from .views import *

app_name = "contratos"

urlpatterns = [
    # path("teste/", lista_contratos_teste, name="teste_contratos"),
    path("contratos", ListaContratos.as_view(), name="lista_contratos"),
    path("admin-dashboard/", DashboardAdmin.as_view(), name="dashboard_admin"),
]
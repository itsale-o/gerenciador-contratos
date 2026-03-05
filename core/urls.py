from django.urls import path

from .views import *


app_name = "core"

urlpatterns = [
    path("", dashboard_redirect, name="home"),
    path("vendedores", ListaVendedores.as_view(), name="lista_vendedores"),
    path("leads", ListaLeadsVendedor.as_view(), name="lista_leads_vendedor")
]
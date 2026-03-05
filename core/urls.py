from django.urls import path

from .views import *


app_name = "core"

urlpatterns = [
    path("", dashboard_redirect, name="home"),
    path("dashboard-vendedor/", DashboardVendedor.as_view(), name="dashboard_vendedor"),
    path("vendedores", ListaVendedores.as_view(), name="lista_vendedores"),
]
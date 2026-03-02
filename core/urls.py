from django.urls import path

from .views import *


app_name = "core"

urlpatterns = [
    path("", dashboard_redirect, name="home")
]
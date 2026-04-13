from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include

from core.views import CustomLogin

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('comms/', include('comunicacao.urls')),
    path('contratos/', include('contratos.urls')),
    path('login/', CustomLogin.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout')
]

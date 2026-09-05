"""
URL configuration for rag_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
import os

from rag_app import api_auth

urlpatterns = [
    # Renamable so the default /admin/ URL isn't a standing brute-force target
    path(os.getenv('DJANGO_ADMIN_URL', 'admin/'), admin.site.urls),
    path('', include('rag_app.urls')),
    path('api/auth/csrf/', api_auth.csrf, name='api_auth_csrf'),
    path('api/auth/register/', api_auth.register, name='api_auth_register'),
    path('api/auth/login/', api_auth.login_view, name='api_auth_login'),
    path('api/auth/logout/', api_auth.logout_view, name='api_auth_logout'),
    path('api/auth/me/', api_auth.me, name='api_auth_me'),
]

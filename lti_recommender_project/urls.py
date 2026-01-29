# lti_recommender_project/lti_recommender_project/urls.py

"""
URL configuration for lti_recommender_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:   from my_app import views
    2. Add a URL to urlpatterns:   path('', views.home, name='home')
Class-based views
    1. Add an import:   from other_app.views import Home
    2. Add a URL to urlpatterns:   path('', Home.as_as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:   path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # LTI Integration and API endpoints
    path('', include('lti_recommender_project.apps.lti_integration.urls')),
    path('interactions/', include('lti_recommender_project.apps.interactions.urls')),
    path('analytics/', include('lti_recommender_project.apps.analytics.urls')),
    # Authentication for browser extension
    path('auth/', include('lti_recommender_project.apps.users.urls')),
]
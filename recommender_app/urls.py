# lti_recommender_project/recommender_app/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('lti/login/', views.lti_login, name='lti_login'),
    path('lti/launch/', views.lti_launch, name='lti_launch'),
    path('lti/jwks/', views.jwks, name='lti_jwks'),
    # Puedes añadir otras rutas específicas de tu aplicación aquí si las necesitas
]
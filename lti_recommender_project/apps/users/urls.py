"""
URL routes for user authentication.
"""
from django.urls import path
from .auth import LoginView, ProfileView, LogoutView

urlpatterns = [
    path('login/', LoginView.as_view(), name='auth-login'),
    path('profile/', ProfileView.as_view(), name='auth-profile'),
    path('logout/', LogoutView.as_view(), name='auth-logout'),
]

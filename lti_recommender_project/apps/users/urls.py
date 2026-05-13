"""
URL routes for user authentication.
"""
from django.urls import path
from .auth import LoginView, ProfileView, LogoutView, RegisterView, UserContextsView

urlpatterns = [
    path('login/', LoginView.as_view(), name='auth-login'),
    path('register/', RegisterView.as_view(), name='auth-register'),
    path('profile/', ProfileView.as_view(), name='auth-profile'),
    path('user-contexts/', UserContextsView.as_view(), name='auth-user-contexts'),
    path('logout/', LogoutView.as_view(), name='auth-logout'),
]



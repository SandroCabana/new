"""
Authentication views for the browser extension.
Provides email/password login that returns an auth token.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from django.contrib.auth.models import User


class LoginView(APIView):
    """
    POST /auth/login/
    Authenticate user with email/username and password, return auth token.
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        email = request.data.get('email', '').strip()
        password = request.data.get('password', '')
        
        if not email or not password:
            return Response(
                {'error': 'Email y contraseña son requeridos'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Try to find user by email first, then by username
        user = None
        
        # Try email lookup
        try:
            user_obj = User.objects.get(email__iexact=email)
            user = authenticate(username=user_obj.username, password=password)
        except User.DoesNotExist:
            # Try username lookup (in case they entered username instead of email)
            user = authenticate(username=email, password=password)
        
        if user is None:
            return Response(
                {'error': 'Credenciales inválidas'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if not user.is_active:
            return Response(
                {'error': 'Esta cuenta está desactivada'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Get or create token
        token, _ = Token.objects.get_or_create(user=user)
        
        return Response({
            'token': token.key,
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'display_name': user.get_full_name() or user.username,
        })


class ProfileView(APIView):
    """
    GET /auth/profile/
    Returns the authenticated user's profile information.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        return Response({
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'display_name': user.get_full_name() or user.username,
        })


class LogoutView(APIView):
    """
    POST /auth/logout/
    Invalidates the user's auth token.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        # Delete the user's token
        try:
            request.user.auth_token.delete()
        except Token.DoesNotExist:
            pass
        
        return Response({'message': 'Sesión cerrada correctamente'})

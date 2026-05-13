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
from django.db import models
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from .serializers import UserRegistrationSerializer


@method_decorator(csrf_exempt, name='dispatch')
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


@method_decorator(csrf_exempt, name='dispatch')
class RegisterView(APIView):

    """
    POST /auth/register/
    Register a new user and return an auth token.
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            
            # Create token for the new user
            token, _ = Token.objects.get_or_create(user=user)
            
            return Response({
                'token': token.key,
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'display_name': user.get_full_name() or user.username,
                'message': 'Usuario registrado exitosamente'
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class ProfileView(APIView):
    """
    GET /auth/profile/
    Returns the authenticated user's profile information.
    Supports both Token and JWT Bearer auth.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        # If JWT was used, enrich with GlobalUser data
        global_user_id = getattr(request.auth, 'payload', {}).get('global_user_id') if hasattr(request, 'auth') else None
        
        return Response({
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'display_name': user.get_full_name() or user.username,
            'global_user_id': global_user_id,
        })


class UserContextsView(APIView):
    """
    GET /auth/user-contexts/
    Returns the list of LTI contexts (courses) and unique domains for the authenticated user.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from lti_recommender_project.apps.users.models import GlobalUser, LTIIdentity
        from lti_recommender_project.apps.interactions.models import UserInteraction

        print(f"DEBUG: UserContextsView for user: {request.user.username}, email: {request.user.email}")

        contexts = []
        global_user = None

        try:
            # JWT path: global_user_id claim takes priority
            jwt_payload = getattr(request.auth, 'payload', {}) if request.auth else {}
            global_user_id = jwt_payload.get('global_user_id')

            if global_user_id:
                global_user = GlobalUser.objects.filter(id=global_user_id).first()

            # Token path: look up by email
            if not global_user:
                global_user = GlobalUser.objects.filter(email__iexact=request.user.email).first()

            if global_user:
                identities = LTIIdentity.objects.filter(global_user=global_user)
                for identity in identities:
                    identity_contexts = identity.contexts.all().values('context_id', 'title')
                    contexts.extend(list(identity_contexts))
                print(f"DEBUG: Found GlobalUser {global_user.id}, contexts count: {len(contexts)}")
            else:
                print(f"DEBUG: No GlobalUser found for {request.user.email}")

        except Exception as e:
            print(f"DEBUG: Error in UserContextsView: {e}")
            contexts = []

        # Unique domains from interactions
        domains = set()
        if global_user:
            interactions = UserInteraction.objects.filter(global_user=global_user)
            for interaction in interactions:
                if interaction.metadata and 'domains' in interaction.metadata:
                    for d in interaction.metadata['domains']:
                        domains.add(d)

        return Response({
            'contexts': list(contexts),
            'domains': sorted(list(domains)),
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

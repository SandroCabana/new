"""
Tests for user authentication endpoints.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework.authtoken.models import Token


class LoginViewTests(TestCase):
    """Tests for POST /auth/login/"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@institution.edu',
            first_name='Test',
            last_name='User'
        )
    
    def test_login_valid_email_password(self):
        """Test login with valid email and password."""
        response = self.client.post('/auth/login/', {
            'email': 'test@institution.edu',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['email'], 'test@institution.edu')
        self.assertEqual(response.data['username'], 'testuser')
    
    def test_login_valid_username_password(self):
        """Test login with username (fallback) and password."""
        response = self.client.post('/auth/login/', {
            'email': 'testuser',  # Username instead of email
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
    
    def test_login_invalid_password(self):
        """Test login with wrong password returns 401."""
        response = self.client.post('/auth/login/', {
            'email': 'test@institution.edu',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
    
    def test_login_nonexistent_user(self):
        """Test login with non-existent email returns 401."""
        response = self.client.post('/auth/login/', {
            'email': 'nonexistent@test.com',
            'password': 'anypassword'
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_login_missing_fields(self):
        """Test login without required fields returns 400."""
        response = self.client.post('/auth/login/', {
            'email': 'test@institution.edu'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_login_returns_display_name(self):
        """Test that login returns the user's display name."""
        response = self.client.post('/auth/login/', {
            'email': 'test@institution.edu',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['display_name'], 'Test User')


class ProfileViewTests(TestCase):
    """Tests for GET /auth/profile/"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@institution.edu'
        )
        self.token = Token.objects.create(user=self.user)
    
    def test_profile_authenticated(self):
        """Test that authenticated user can get profile."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = self.client.get('/auth/profile/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'test@institution.edu')
    
    def test_profile_unauthenticated(self):
        """Test that unauthenticated request returns 401."""
        response = self.client.get('/auth/profile/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class LogoutViewTests(TestCase):
    """Tests for POST /auth/logout/"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.token = Token.objects.create(user=self.user)
    
    def test_logout_invalidates_token(self):
        """Test that logout deletes the auth token."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = self.client.post('/auth/logout/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify token is deleted
        self.assertFalse(Token.objects.filter(user=self.user).exists())
    
    def test_logout_unauthenticated(self):
        """Test that unauthenticated request returns 401."""
        response = self.client.post('/auth/logout/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

"""
URL configuration for analytics app.
"""
from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    # Dashboard overview
    path('dashboard/', views.dashboard_overview, name='dashboard'),
    path('dashboard/visual/', views.visual_dashboard, name='visual_dashboard'),
    
    # Trends over time
    path('trends/', views.interaction_trends, name='trends'),
    
    # Resource analytics
    path('resources/', views.resource_analytics, name='resources'),
    
    # User engagement
    path('engagement/', views.user_engagement, name='engagement'),
    
    # ML model performance
    path('models/', views.model_performance, name='models'),
    
    # Context/course analytics
    path('context/', views.context_analytics, name='context_list'),
    path('context/<str:context_id>/', views.context_analytics, name='context_detail'),
]

from django.urls import path
from .views import TrackedDataBatchView, UserHistoryView, UserStatsView, DataPreviewView
from .xapi_views import XapiReceiverView

urlpatterns = [
    path('tracked-data-batch/', TrackedDataBatchView.as_view(), name='tracked-data-batch'),
    path('user-history/', UserHistoryView.as_view(), name='user-history'),
    path('user-stats/', UserStatsView.as_view(), name='user-stats'),
    path('preview/', DataPreviewView.as_view(), name='data-preview'),
    path('xapi/receiver/', XapiReceiverView.as_view(), name='xapi-receiver'),
]

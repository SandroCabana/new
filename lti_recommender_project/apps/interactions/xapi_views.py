from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class XapiReceiverView(APIView):
    """
    Endpoint for receiving xAPI statements from Moodle.
    Validates a Bearer Token for security.
    """
    permission_classes = [AllowAny] # We use custom Bearer token validation

    def post(self, request):
        # 1. Validate Bearer Token
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        expected_token = f"Bearer {getattr(settings, 'XAPI_BEARER_TOKEN', 'lti_recommender_xapi_secret_2026')}"
        
        if not auth_header or auth_header != expected_token:
            logger.warning("Unauthorized xAPI attempt detected.")
            return Response({"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

        # 2. Get statement data
        statement_data = request.data
        if not statement_data:
            return Response({"error": "Empty payload"}, status=status.HTTP_400_BAD_REQUEST)

        # Handle both single statement and list of statements
        if isinstance(statement_data, list):
            statements = statement_data
        else:
            statements = [statement_data]

        # 3. Queue for Celery processing
        from .tasks import process_xapi_statement
        
        for statement in statements:
            try:
                # We offload the heavy lifting to Celery
                process_xapi_statement.apply_async(args=[statement], queue='scraping') # Using scraping queue or default
            except Exception as e:
                logger.error(f"Error queuing xAPI statement: {e}")

        return Response({"status": "accepted", "count": len(statements)}, status=status.HTTP_202_ACCEPTED)

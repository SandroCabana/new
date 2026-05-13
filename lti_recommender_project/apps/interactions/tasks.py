from celery import shared_task
import logging
import hashlib
from django.db import transaction
from .models import UserInteraction
from lti_recommender_project.apps.resources.models import EducationalResource

logger = logging.getLogger(__name__)

# Mapping xAPI verbs to our interaction weights/types
# This defines how much "value" each interaction adds to the user profile
VERB_MAPPING = {
    'http://adlnet.gov/expapi/verbs/viewed': {'type': 'viewed', 'weight': 1.0},
    'http://adlnet.gov/expapi/verbs/attempted': {'type': 'attempted', 'weight': 2.0},
    'http://adlnet.gov/expapi/verbs/completed': {'type': 'completed', 'weight': 5.0},
    'http://adlnet.gov/expapi/verbs/passed': {'type': 'completed', 'weight': 5.0},
    'http://adlnet.gov/expapi/verbs/failed': {'type': 'viewed', 'weight': 0.5},
}

@shared_task(
    name='lti_recommender_project.apps.interactions.tasks.process_xapi_statement',
    queue='scraping', # Using the same queue for processing events
)
def process_xapi_statement(statement):
    """
    Asynchronously processes an xAPI statement received from Moodle.
    Maps actor, verb, and object to the internal Recommender models.
    """
    try:
        # 1. Identify Actor (User)
        actor = statement.get('actor', {})
        # Moodle xAPI typically provides actors with an email address
        user_email = actor.get('mbox', '').replace('mailto:', '')
        user_name = actor.get('name', 'Anonymous')
        
        if not user_email:
            # Fallback to account name if email is not available
            account = actor.get('account', {})
            user_id = account.get('name') or str(hashlib.md5(user_name.encode()).hexdigest())
        else:
            user_id = user_email

        # 2. Identify Verb
        verb = statement.get('verb', {})
        verb_id = verb.get('id', '')
        mapping = VERB_MAPPING.get(verb_id, {'type': 'viewed', 'weight': 1.0})

        # 3. Identify Object (Resource)
        obj = statement.get('object', {})
        resource_id_url = obj.get('id', '')
        definition = obj.get('definition', {})
        
        # Name/title often grouped by language in xAPI
        name_map = definition.get('name', {})
        resource_title = name_map.get('es') or name_map.get('en') or "Moodle Activity"
        
        if not resource_id_url:
            logger.warning("Statement object missing ID.")
            return "Ignored: No resource ID"

        # 4. Ingest/Update Resource and create Interaction (Transactional)
        with transaction.atomic():
            # Get or create the resource as a 'moodle_activity'
            resource, created = EducationalResource.objects.get_or_create(
                url=resource_id_url,
                defaults={
                    'resource_id': hashlib.md5(resource_id_url.encode()).hexdigest(),
                    'title': resource_title,
                    'resource_type': 'moodle_activity',
                    'description': definition.get('description', {}).get('es') or definition.get('description', {}).get('en') or "Generated from Moodle xAPI",
                }
            )

            # Check for existing statement_id in metadata to avoid processing duplicates
            statement_id = statement.get('id')
            if statement_id and UserInteraction.objects.filter(metadata__statement_id=statement_id).exists():
                return f"Statement {statement_id} already processed. Skipping."

            # Map xAPI context if available (Moodle course ID)
            context = statement.get('context', {})
            extensions = context.get('extensions', {})
            # Moodle context extension ID varies, but we try to find a sensible default or just use a generic 'moodle' label
            context_id = "moodle_context"
            for key in extensions:
                if 'course' in key.lower() or 'context' in key.lower():
                    context_id = str(extensions[key])
                    break

            # 5. Save the Interaction
            UserInteraction.objects.create(
                lti_user_id=user_id,
                lti_context_id=context_id,
                resource=resource,
                interaction_type=mapping['type'],
                value=mapping['weight'],
                completion_percentage=100.0 if mapping['type'] == 'completed' else 0.0,
                metadata={
                    'statement_id': statement_id,
                    'verb_id': verb_id,
                    'is_moodle': True,
                    'raw_object': obj
                }
            )

        logger.info(f"Successfully processed xAPI {mapping['type']} interaction for user {user_id}")
        return f"Processed {mapping['type']} for {user_id}"

    except Exception as e:
        logger.error(f"Error processing xAPI statement: {str(e)}")
        return f"Error: {str(e)}"

@shared_task(
    name='lti_recommender_project.apps.interactions.tasks.process_tracking_batch',
    queue='scraping'
)
def process_tracking_batch(global_user_id, context_id, items):
    """
    Asynchronously processes a batch of tracking data sent by the browser extension.
    """
    from lti_recommender_project.apps.users.models import GlobalUser
    
    try:
        user = GlobalUser.objects.get(id=global_user_id)
        
        with transaction.atomic():
            for item in items:
                # Use the keys defined in TrackedDataSerializer
                url = item.get('associatedURL')
                title = item.get('title') or item.get('resourceTitle') or 'Página Web'
                duration = item.get('duration', 0)
                
                if not url:
                    continue
                    
                # Identify or create resource
                resource, created = EducationalResource.objects.get_or_create(
                    url=url,
                    defaults={
                        'resource_id': hashlib.md5(url.encode()).hexdigest(),
                        'title': title,
                        'resource_type': 'article',  # Fallback for web pages
                        'description': 'Recurso rastreado mediante extensión de navegador.',
                    }
                )
                
                # We need a backward-compatible lti_user_id since it's a required CharField.
                # Use the global user id as string.
                lti_user_id_fallback = str(user.id)
                
                # Save interaction
                UserInteraction.objects.create(
                    global_user=user,
                    lti_user_id=lti_user_id_fallback,
                    lti_context_id=context_id or 'global_browsing',
                    resource=resource,
                    interaction_type='viewed',
                    time_spent=duration,
                    value=1.0,
                    metadata={'source': 'browser_extension', 'tracked_url': url}
                )
                
        logger.info(f"Processed batch of {len(items)} items for GlobalUser {global_user_id}")
        return f"Processed {len(items)} items"
        
    except Exception as e:
        logger.error(f"Error in process_tracking_batch: {e}")
        return f"Error: {str(e)}"

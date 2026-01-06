
import os
import django
import sys

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lti_recommender_project.settings')
django.setup()

from lti_recommender_project.apps.recommendations.services.embedding_service import get_embedding_service

def main():
    print("Starting embedding generation process...")
    try:
        service = get_embedding_service()
        print(f"Using model: {service.model_name}")
        
        # force_update=True to ensure all resources get cached embeddings
        updated, failed = service.update_resource_embeddings(force_update=True)
        
        print("-" * 50)
        print(f"Process completed.")
        print(f"Successfully updated: {updated}")
        print(f"Failed: {failed}")
        print("-" * 50)
        
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

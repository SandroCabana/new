
import os
import django
import numpy as np
import math
from collections import defaultdict
import json
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lti_recommender_project.settings')
django.setup()

from django.db import transaction
from lti_recommender_project.apps.interactions.models import UserInteraction
from lti_recommender_project.apps.resources.models import EducationalResource
from lti_recommender_project.apps.recommendations.services.recommendation_engine import RecommendationEngine

def calculate_metrics():
    print("Starting Metrics Calculation...")
    
    engine = RecommendationEngine()
    
    # Get all users with at least 5 interactions
    users = UserInteraction.objects.values('lti_user_id').annotate(
        count=django.db.models.Count('id')
    ).filter(count__gte=5).values_list('lti_user_id', flat=True)
    
    if not users:
        print("Not enough data for user-based evaluation (need users with 5+ interactions).")
        print("Calculating global coverage only.")
        return

    print(f"Evaluating on {len(users)} users...")
    
    total_precision = []
    total_recall = []
    total_ndcg = []
    squared_errors = []
    all_recommended_ids = set()
    total_resources_count = EducationalResource.objects.count()
    
    # Evaluation configuration
    K = 5
    TEST_RATIO = 0.2
    
    for user_id in users:
        # Get user interactions sorted by time
        interactions = list(UserInteraction.objects.filter(
            lti_user_id=user_id
        ).order_by('timestamp'))
        
        split_index = int(len(interactions) * (1 - TEST_RATIO))
        train_set = interactions[:split_index]
        test_set = interactions[split_index:]
        
        if not test_set:
            continue

        test_resource_ids = {i.resource_id for i in test_set}
        
        # We need to temporarily "hide" test_set from DB so the engine doesn't see it
        # Strategy: We will delete them, run recs, then recreate them.
        # Since we are in a script, we can do this safely if we catch exceptions.
        # BETTER: Use transaction.atomic() and raise an exception to rollback?
        # But we need the results out of the block.
        # Alternative: Just delete and re-insert.
        
        test_data_backups = []
        for i in test_set:
            backup = {
                'lti_user_id': i.lti_user_id,
                'lti_context_id': i.lti_context_id,
                'resource_id': i.resource_id,
                'interaction_type': i.interaction_type,
                'value': i.value,
                'rating': i.rating,
                'time_spent': i.time_spent,
                'completion_percentage': i.completion_percentage,
                # timestamp is auto_now_add, so we might lose exact time on restore, but order matters mostly.
                # UserInteraction model has auto_now_add=True, so we strictly can't force it easily without hacking.
                # However for recommendation engine, it mostly orders by timestamp descending.
                # If we re-insert, they become "newest", which matches "test set" being future.
                # Actually, wait. If we restore them, they get NEW timestamps (now).
                # This changes the history order for subsequent runs if we run this script multiple times.
                # Mitigaton: For this script, we can just delete from DB and NOT restore 
                # IF we assume this is a pure evaluation run? 
                # NO. We cannot delete user data permanently.
                
                # OK, strategy 3: Mocking is hard.
                # Strategy 4: We wrap the WHOLE processing for a user in transaction.atomic
                # calculate metrics, then RAISE exception to rollback.
            }
            test_data_backups.append(backup)

        try:
            with transaction.atomic():
                # Delete test set
                for i in test_set:
                    i.delete()
                
                # Get context_id from one of the interactions (or None if mixed)
                context_id = train_set[0].lti_context_id if train_set else interactions[0].lti_context_id
                
                # Get Recommendations
                recs = engine.get_recommendations(
                    user_id=user_id,
                    context_id=context_id,
                    limit=K,
                    exclude_viewed=True
                )
                
                rec_ids = [r['resource'].id for r in recs]
                all_recommended_ids.update(rec_ids)
                
                # Metrics Calculation
                hits = 0
                dcg = 0
                idcg = 0
                
                # Precision & Recall
                for rid in rec_ids:
                    if rid in test_resource_ids:
                        hits += 1
                
                precision = hits / K
                recall = hits / len(test_resource_ids)
                
                # NDCG
                # Relevance: 1 if in test set, 0 otherwise
                for i, rid in enumerate(rec_ids):
                    rel = 1 if rid in test_resource_ids else 0
                    dcg += (2**rel - 1) / math.log2(i + 2)
                
                # Ideal DCG: All hits at top
                ideal_hits = min(len(test_resource_ids), K)
                for i in range(ideal_hits):
                    idcg += (2**1 - 1) / math.log2(i + 2)
                
                ndcg = dcg / idcg if idcg > 0 else 0
                
                # RMSE (Predicted Score vs Normalized Actual Rating)
                # Only for items in Test Set that have a rating
                for i in test_set:
                    if i.rating:
                        # Find if this resource was recommended and get its score
                        # Or checking if the engine calculates a score for it.
                        # Since engine only returns Top K, we might not have scores for all test items.
                        # We can explicitly ask engine for score of test item.
                        
                        # Calculate resource score manually
                        from lti_recommender_project.apps.users.models import UserProfile
                        user_profile, _ = UserProfile.objects.get_or_create(lti_user_id=user_id)
                        
                        pred_score = engine._calculate_resource_score(
                            i.resource, user_profile, user_id, context_id
                        )
                        
                        # Normalize rating (1-5) to 0-1
                        actual_score = (i.rating - 1) / 4.0
                        squared_errors.append((pred_score - actual_score) ** 2)

                total_precision.append(precision)
                total_recall.append(recall)
                total_ndcg.append(ndcg)
                
                # FORCE ROLLBACK
                raise ValueError("Rolling back changes for evaluation")
                
        except ValueError as e:
            if str(e) == "Rolling back changes for evaluation":
                pass
            else:
                raise e

    # Aggregate Metrics
    avg_precision = np.mean(total_precision) if total_precision else 0
    avg_recall = np.mean(total_recall) if total_recall else 0
    f1 = 2 * (avg_precision * avg_recall) / (avg_precision + avg_recall) if (avg_precision + avg_recall) > 0 else 0
    avg_ndcg = np.mean(total_ndcg) if total_ndcg else 0
    rmse = math.sqrt(np.mean(squared_errors)) if squared_errors else 0
    coverage = len(all_recommended_ids) / total_resources_count if total_resources_count > 0 else 0
    
    print("\n" + "="*40)
    print("       SEMANTIC MODEL EVALUATION REPORT       ")
    print("="*40)
    print(f"Users Evaluated: {len(users)}")
    print(f"Total Resources: {total_resources_count}")
    print("-" * 40)
    print(f"• Precision@{K}: {avg_precision:.4f}")
    print(f"• Recall@{K}:    {avg_recall:.4f}")
    print(f"• F1 Score:      {f1:.4f}")
    print(f"• NDCG@{K}:       {avg_ndcg:.4f}")
    print(f"• RMSE:          {rmse:.4f}")
    print(f"• Coverage:      {coverage:.2%} ({len(all_recommended_ids)} unique items rec'd)")
    print("="*40)

if __name__ == "__main__":
    calculate_metrics()

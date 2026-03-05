"""
strands_orchestrator.py — Intent-based orchestrator
Calls only the relevant tool based on user intent
"""
import os
import logging
from typing import Dict, List, Any
from dotenv import load_dotenv

from agents.scheme.scheme_tool import search_schemes_tool
from agents.jobs.jobs_tool import search_jobs_tool
from agents.upskill.upskill_tool import search_upskill_tool
from common.providers.embedding_providers import BedrockTitanEmbeddingProvider

load_dotenv()

logger = logging.getLogger(__name__)

# Initialize embedding provider once for reuse
_embedding_provider = BedrockTitanEmbeddingProvider(
    region=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
    model="amazon.titan-embed-text-v2:0"
)


def orchestrate(user_profile: Dict[str, Any] = None, task: str = None, context: Dict[str, Any] = None, max_iterations: int = 10) -> Dict[str, Any]:
    """
    Intent-based orchestration - calls only the relevant tool based on user intent.
    
    Supported intents:
    - 'job' -> search_jobs_tool
    - 'upskill' -> search_upskill_tool
    - 'loan' -> search_schemes_tool
    
    Args:
        user_profile: User profile dict (for recommendations)
        task: High-level task description (for complex workflows)
        context: Additional context
        max_iterations: Maximum agentic loop iterations (unused in direct mode)
    
    Returns:
        Dictionary with results from the invoked agent
    """
    print(f"\n{'='*60}")
    print("INTENT-BASED ORCHESTRATION STARTED")
    print(f"{'='*60}")
    
    if not user_profile:
        raise ValueError("Must provide user_profile")
    
    # Extract profile fields
    skill = user_profile.get('profession_skill', user_profile.get('skill', ''))
    intent = user_profile.get('intent', 'job').lower()
    skill_level = user_profile.get('skill_rating', user_profile.get('skill_level', 3))
    state = user_profile.get('preferred_location', user_profile.get('state', 'All India'))
    
    print(f"\n📋 User Profile:")
    print(f"  Skill: {skill}")
    print(f"  Intent: {intent}")
    print(f"  Level: {skill_level}/5")
    print(f"  Location: {state}")
    
    # Generate embedding once (optimization)
    print(f"\n🔄 Generating embedding...")
    query_text = f"{skill} {intent} {state}"
    query_embedding = _embedding_provider.generate_embedding(query_text)
    print(f"✅ Embedding generated (1024 dimensions)")
    
    # Initialize empty results
    jobs = []
    schemes = []
    training_centers = []
    
    # Call only the relevant tool based on intent
    print(f"\n🔍 Calling tool based on intent: '{intent}'")
    
    if intent == 'job':
        print(f"  → Searching jobs...")
        jobs = search_jobs_tool(skill, skill_level, state, query_embedding=query_embedding)[:5]
        message = f"Found {len(jobs)} job opportunities for {skill} professionals in {state}."
        
    elif intent == 'upskill':
        print(f"  → Searching training centers...")
        training_centers = search_upskill_tool(skill, skill_level, state, query_embedding=query_embedding)[:5]
        message = f"Found {len(training_centers)} training programs for {skill} in {state}."
        
    elif intent == 'loan':
        print(f"  → Searching schemes...")
        schemes = search_schemes_tool(skill, intent, skill_level, state, query_embedding=query_embedding)[:5]
        message = f"Found {len(schemes)} government schemes for {skill} professionals in {state}."
        
    else:
        # Default to job search if intent is not recognized
        print(f"  ⚠️  Unknown intent '{intent}', defaulting to job search...")
        jobs = search_jobs_tool(skill, skill_level, state, query_embedding=query_embedding)[:5]
        message = f"Found {len(jobs)} job opportunities for {skill} professionals in {state}."
    
    print(f"\n✅ Results:")
    print(f"  Jobs: {len(jobs)}")
    print(f"  Schemes: {len(schemes)}")
    print(f"  Training Centers: {len(training_centers)}")
    
    all_results = {
        "profile": None,
        "vision_analysis": None,
        "jobs": jobs,
        "schemes": schemes,
        "training_centers": training_centers,
        "conversation": [],
        "summary": message
    }
    
    print(f"\n{'='*60}")
    print("INTENT-BASED ORCHESTRATION COMPLETE")
    print(f"{'='*60}")
    
    return all_results


# Convenience function for recommendations (backward compatibility)
def orchestrate_recommendations(user_profile: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience wrapper for recommendation use case"""
    return orchestrate(user_profile=user_profile, max_iterations=5)


def _deduplicate_by_id(items: List[Dict]) -> List[Dict]:
    """Remove duplicate items based on id field"""
    seen = set()
    unique = []
    for item in items:
        item_id = item.get('id') or item.get('scheme_id') or item.get('job_id')
        if item_id and item_id not in seen:
            seen.add(item_id)
            unique.append(item)
        elif not item_id:
            unique.append(item)
    return unique

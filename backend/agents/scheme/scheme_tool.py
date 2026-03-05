"""
scheme_tool.py — Scheme search tool definition
"""
from typing import Dict, List
import os
from dotenv import load_dotenv

load_dotenv()

def search_schemes_tool(skill: str, intent: str, skill_level: int, state: str, query_embedding: List[float] = None) -> List[Dict]:
    """
    Search for government schemes based on user's skill, intent, and location.
    
    Args:
        skill: User's skill or profession (e.g., 'handicraft artisan', 'weaver')
        intent: User's intent - 'job' (employment), 'upskill' (training), or 'loan' (financial assistance)
        skill_level: Skill proficiency level from 1-5
        state: User's state in India or 'All India'
        query_embedding: Pre-generated embedding vector (optional, for performance)
    
    Returns:
        List of relevant schemes ranked by eligibility score
    """
    from agents.scheme.scheme_agent import SchemeAgent
    from common.providers.embedding_providers import BedrockTitanEmbeddingProvider
    from common.stores.vector_stores import PostgresPgVectorStore
    
    embedding_provider = BedrockTitanEmbeddingProvider(
        region=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        model="amazon.titan-embed-text-v2:0"
    )
    
    vector_store = PostgresPgVectorStore(
        connection_string=os.getenv("POSTGRES_CONNECTION_STRING")
    )
    
    agent = SchemeAgent(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        index_name="schemes"
    )
    
    user_profile = {
        "skill": skill,
        "intent": intent,
        "skill_level": skill_level,
        "state": state
    }
    
    return agent.search_schemes(user_profile, limit=5, query_embedding=query_embedding)

SCHEME_TOOL_DEFINITION = {
    "name": "search_schemes",
    "description": "Search for government schemes based on user's skill, intent, and location. Returns relevant schemes ranked by eligibility.",
    "input_schema": {
        "type": "object",
        "properties": {
            "skill": {
                "type": "string",
                "description": "User's skill or profession (e.g., 'handicraft artisan', 'weaver')"
            },
            "intent": {
                "type": "string",
                "enum": ["job", "upskill", "loan"],
                "description": "User's intent: job (employment), upskill (training), or loan (financial assistance)"
            },
            "skill_level": {
                "type": "integer",
                "description": "Skill proficiency level from 1-5"
            },
            "state": {
                "type": "string",
                "description": "User's state in India or 'All India'"
            }
        },
        "required": ["skill", "intent", "skill_level", "state"]
    }
}

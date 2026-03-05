"""
jobs_tool.py — Jobs search tool definition
"""
from typing import Dict, List
import os
from dotenv import load_dotenv

load_dotenv()

def search_jobs_tool(skill: str, skill_level: int, state: str) -> List[Dict]:
    """
    Search for jobs based on user's skill and location.
    
    Args:
        skill: User's skill or profession
        skill_level: Skill proficiency level from 1-5
        state: User's state in India
    
    Returns:
        List of relevant jobs ranked by match score
    """
    from agents.jobs.jobs_agent import JobsAgent
    from common.providers.embedding_providers import BedrockTitanEmbeddingProvider
    from common.stores.vector_stores import PostgresPgVectorStore
    
    embedding_provider = BedrockTitanEmbeddingProvider(
        region=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        model="amazon.titan-embed-text-v2:0"
    )
    
    vector_store = PostgresPgVectorStore(
        connection_string=os.getenv("POSTGRES_CONNECTION_STRING")
    )
    
    agent = JobsAgent(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        index_name="jobs"  # Using jobs table now
    )
    
    user_profile = {
        "skill": skill,
        "skill_level": skill_level,
        "state": state
    }
    
    return agent.search_jobs(user_profile, limit=5)

JOBS_TOOL_DEFINITION = {
    "name": "search_jobs",
    "description": "Search for jobs based on user's skill and location. Returns relevant jobs ranked by match score.",
    "input_schema": {
        "type": "object",
        "properties": {
            "skill": {
                "type": "string",
                "description": "User's skill or profession"
            },
            "skill_level": {
                "type": "integer",
                "description": "Skill proficiency level from 1-5"
            },
            "state": {
                "type": "string",
                "description": "User's state in India"
            }
        },
        "required": ["skill", "skill_level", "state"]
    }
}

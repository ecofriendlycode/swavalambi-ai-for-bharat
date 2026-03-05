"""
upskill_agent.py — Upskill Agent for training/course matching.
"""

from agents.base_agent import BaseAgent


class UpskillAgent(BaseAgent):
    """AI Agent for training/course matching."""
    
    def _build_text_for_embedding(self, doc: dict) -> str:
        location = doc.get('location', '')
        return f"{doc['name']} {doc['description']} {' '.join(doc.get('skills', []))} {doc.get('provider', '')} {location}"
    
    def _build_query_text(self, user_profile: dict) -> str:
        state = user_profile.get('state', '')
        return f"{user_profile.get('skill', '')} training course {state}"
    
    def calculate_eligibility_score(self, course: dict, user_profile: dict) -> float:
        score = 0.0
        
        user_skill = user_profile.get("skill", "").lower()
        course_skills = [s.lower() for s in course.get("skills", [])]
        course_name = course.get("name", "").lower()
        if user_skill in course_name or any(user_skill in s for s in course_skills):
            score += 0.5
        
        user_level = user_profile.get("skill_level", 0)
        if user_level < 3:
            score += 0.3
        else:
            score += 0.1
        
        user_state = user_profile.get("state", "").lower()
        course_location = course.get("location", "").lower()
        if not course_location or "online" in course_location or user_state in course_location:
            score += 0.2
        
        return min(score, 1.0)
    
    def search_courses(self, user_profile: dict, limit: int = 10, query_embedding: list[float] = None) -> list[dict]:
        results = self.search(user_profile, limit, query_embedding=query_embedding)
        
        # Format results for UI compatibility
        for center in results:
            # Map skills to courses (UI expects 'courses' field)
            center['courses'] = center.get('skills', [])
            
            # Map provider to center_type (UI expects 'center_type' field)
            center['center_type'] = center.get('provider', 'Training Center')
            
            # Add URL (UI expects 'url' field)
            # Generate URL from contact/email if available
            contact = center.get('contact', '')
            email = center.get('email', '')
            if email:
                center['url'] = f"mailto:{email}"
            elif contact:
                center['url'] = f"tel:{contact.replace(' ', '')}"
            else:
                center['url'] = ""
            
            # Keep contact info for display
            if contact:
                center['contact_url'] = f"tel:{contact.replace(' ', '')}"
            if email:
                center['email_url'] = f"mailto:{email}"
        
        return results

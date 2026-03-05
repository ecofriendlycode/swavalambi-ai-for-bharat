"""
jobs_agent.py — Jobs Agent for job matching.
"""

from agents.base_agent import BaseAgent


class JobsAgent(BaseAgent):
    """AI Agent for job matching."""
    
    def _build_text_for_embedding(self, doc: dict) -> str:
        location = doc.get('location', '')
        return f"{doc['title']} {doc['description']} {doc.get('company', '')} {' '.join(doc.get('skills', []))} {location}"
    
    def _build_query_text(self, user_profile: dict) -> str:
        state = user_profile.get('state', '')
        return f"{user_profile.get('skill', '')} job {state}"
    
    def calculate_eligibility_score(self, job: dict, user_profile: dict) -> float:
        score = 0.0
        
        user_skill = user_profile.get("skill", "").lower()
        job_skills = [s.lower() for s in job.get("skills", [])]
        job_title = job.get("title", "").lower()
        if user_skill in job_title or any(user_skill in s for s in job_skills):
            score += 0.5
        
        user_level = user_profile.get("skill_level", 0)
        if user_level >= 3:
            score += 0.3
        elif user_level >= 1:
            score += 0.1
        
        user_state = user_profile.get("state", "").lower()
        job_location = job.get("location", "").lower()
        if user_state in job_location:
            score += 0.2
        
        return min(score, 1.0)
    
    def search_jobs(self, user_profile: dict, limit: int = 10, query_embedding: list[float] = None) -> list[dict]:
        results = self.search(user_profile, limit, query_embedding=query_embedding)
        
        # Format results for UI compatibility
        for job in results:
            # Format salary from min_salary and max_salary
            min_sal = job.get('min_salary', 0)
            max_sal = job.get('max_salary', 0)
            
            if min_sal and max_sal:
                job['salary'] = f"₹{int(min_sal):,} - ₹{int(max_sal):,}"
            elif min_sal:
                job['salary'] = f"₹{int(min_sal):,}+"
            elif max_sal:
                job['salary'] = f"Up to ₹{int(max_sal):,}"
            else:
                job['salary'] = "Salary not specified"
            
            # Add job application URL
            job_id = job.get('id', '')
            if job_id:
                job['apply_url'] = f"https://betacloud.ncs.gov.in/job-listing/applying/{job_id}"
            else:
                job['apply_url'] = ""
        
        return results

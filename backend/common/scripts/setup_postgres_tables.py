"""
setup_postgres_tables.py — Setup PostgreSQL RDS with pgvector for schemes, jobs, and upskill tables.
"""

import psycopg2
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# PostgreSQL RDS connection details from .env
PG_CONFIG = {
    "host": os.getenv("POSTGRES_HOST"),
    "port": int(os.getenv("POSTGRES_PORT", 5432)),
    "database": os.getenv("POSTGRES_DATABASE"),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD")
}

def setup_postgres_tables():
    """Setup PostgreSQL with pgvector extension and create schemes, jobs, upskill tables."""
    
    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(**PG_CONFIG)
        cur = conn.cursor()
        
        logger.info("Connected to PostgreSQL RDS")
        
        # Create pgvector extension
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        logger.info("✅ Created pgvector extension")
        
        # Drop existing tables if they exist
        cur.execute("DROP TABLE IF EXISTS schemes CASCADE")
        cur.execute("DROP TABLE IF EXISTS jobs CASCADE")
        cur.execute("DROP TABLE IF EXISTS upskill CASCADE")
        logger.info("✅ Dropped existing tables (if any)")
        
        # 1. Create schemes table
        cur.execute("""
            CREATE TABLE schemes (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                ministry TEXT,
                description TEXT,
                categories TEXT[],
                tags TEXT[],
                state TEXT,
                level TEXT,
                url TEXT,
                embedding vector(1024),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        logger.info("✅ Created schemes table")
        
        # 2. Create jobs table
        cur.execute("""
            CREATE TABLE jobs (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                company TEXT,
                skills TEXT[],
                location TEXT,
                job_type TEXT,
                vacancies INTEGER,
                min_salary NUMERIC,
                max_salary NUMERIC,
                experience TEXT,
                embedding vector(1024),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        logger.info("✅ Created jobs table")
        
        # 3. Create upskill table
        cur.execute("""
            CREATE TABLE upskill (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                provider TEXT,
                skills TEXT[],
                location TEXT,
                address TEXT,
                contact TEXT,
                email TEXT,
                embedding vector(1024),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        logger.info("✅ Created upskill table")
        
        # Create vector indexes for fast similarity search
        cur.execute("""
            CREATE INDEX schemes_embedding_idx 
            ON schemes USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """)
        cur.execute("""
            CREATE INDEX jobs_embedding_idx 
            ON jobs USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """)
        cur.execute("""
            CREATE INDEX upskill_embedding_idx 
            ON upskill USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """)
        logger.info("✅ Created vector indexes")
        
        # Create additional indexes
        cur.execute("CREATE INDEX schemes_state_idx ON schemes(state)")
        cur.execute("CREATE INDEX schemes_tags_idx ON schemes USING GIN(tags)")
        cur.execute("CREATE INDEX jobs_location_idx ON jobs(location)")
        cur.execute("CREATE INDEX jobs_skills_idx ON jobs USING GIN(skills)")
        cur.execute("CREATE INDEX upskill_location_idx ON upskill(location)")
        cur.execute("CREATE INDEX upskill_skills_idx ON upskill USING GIN(skills)")
        logger.info("✅ Created additional indexes")
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info("\n" + "="*80)
        logger.info("✅ PostgreSQL setup complete!")
        logger.info("="*80)
        logger.info("Created tables: schemes, jobs, upskill")
        logger.info("All tables have vector embeddings (1024 dimensions)")
        logger.info("="*80)
        
    except Exception as e:
        logger.error(f"❌ Error setting up PostgreSQL: {e}")
        raise

if __name__ == "__main__":
    setup_postgres_tables()

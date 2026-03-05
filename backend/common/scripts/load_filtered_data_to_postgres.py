"""
load_filtered_data_to_postgres.py — Load filtered CSV files into PostgreSQL tables
"""

import csv
import os
import psycopg2
from dotenv import load_dotenv
from pathlib import Path
import sys

load_dotenv()

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from common.providers.embedding_providers import BedrockTitanEmbeddingProvider

# Config
PG_CONN = os.getenv("POSTGRES_CONNECTION_STRING")
embedding_provider = BedrockTitanEmbeddingProvider(
    region=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
    model="amazon.titan-embed-text-v2:0"
)

def load_schemes(csv_file, conn):
    """Load schemes from CSV into schemes table"""
    print(f"\n📋 Loading schemes from {csv_file}...")
    
    cur = conn.cursor()
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        indexed = 0
        
        for row in reader:
            try:
                # Generate embedding
                categories = row['categories'].split('|') if row['categories'] else []
                tags = row['tags'].split('|') if row['tags'] else []
                
                text = f"{row['name']} {row['description']} {' '.join(categories)} {' '.join(tags)} {row['state']}"
                embedding = embedding_provider.generate_embedding(text)
                
                # Insert into database
                cur.execute("""
                    INSERT INTO schemes (id, name, ministry, description, categories, tags, state, level, url, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                """, (
                    row['id'],
                    row['name'],
                    row['ministry'],
                    row['description'],
                    categories,
                    tags,
                    row['state'],
                    row['level'],
                    row['url'],
                    embedding
                ))
                
                indexed += 1
                if indexed % 10 == 0:
                    print(f"  Indexed {indexed} schemes...")
                    conn.commit()
                
            except Exception as e:
                print(f"  Error loading scheme {row.get('name')}: {e}")
        
        conn.commit()
    
    cur.close()
    print(f"✅ Loaded {indexed} schemes")
    return indexed

def load_jobs(csv_file, conn):
    """Load jobs from CSV into jobs table"""
    print(f"\n💼 Loading jobs from {csv_file}...")
    
    cur = conn.cursor()
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        indexed = 0
        
        for row in reader:
            try:
                # Generate embedding
                skills = row['skills'].split('|') if row['skills'] else []
                
                text = f"{row['title']} {row['description']} {' '.join(skills)} {row['location']}"
                embedding = embedding_provider.generate_embedding(text)
                
                # Insert into database
                cur.execute("""
                    INSERT INTO jobs (id, title, description, company, skills, location, job_type, vacancies, min_salary, max_salary, experience, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                """, (
                    row['id'],
                    row['title'],
                    row['description'],
                    row['company'],
                    skills,
                    row['location'],
                    row['job_type'],
                    int(row['vacancies']) if row['vacancies'] else 0,
                    float(row['min_salary']) if row['min_salary'] else 0,
                    float(row['max_salary']) if row['max_salary'] else 0,
                    row['experience'],
                    embedding
                ))
                
                indexed += 1
                if indexed % 50 == 0:
                    print(f"  Indexed {indexed} jobs...")
                    conn.commit()
                
            except Exception as e:
                print(f"  Error loading job {row.get('title')}: {e}")
        
        conn.commit()
    
    cur.close()
    print(f"✅ Loaded {indexed} jobs")
    return indexed

def load_upskill(csv_file, conn):
    """Load training centers from CSV into upskill table"""
    print(f"\n🎓 Loading training centers from {csv_file}...")
    
    cur = conn.cursor()
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        indexed = 0
        
        for row in reader:
            try:
                # Generate embedding
                skills = row['skills'].split('|') if row['skills'] else []
                
                text = f"{row['name']} {row['description']} {' '.join(skills)} {row['location']}"
                embedding = embedding_provider.generate_embedding(text)
                
                # Insert into database
                cur.execute("""
                    INSERT INTO upskill (id, name, description, provider, skills, location, address, contact, email, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                """, (
                    row['id'],
                    row['name'],
                    row['description'],
                    row['provider'],
                    skills,
                    row['location'],
                    row['address'],
                    row['contact'],
                    row['email'],
                    embedding
                ))
                
                indexed += 1
                if indexed % 10 == 0:
                    print(f"  Indexed {indexed} training centers...")
                    conn.commit()
                
            except Exception as e:
                print(f"  Error loading training center {row.get('name')}: {e}")
        
        conn.commit()
    
    cur.close()
    print(f"✅ Loaded {indexed} training centers")
    return indexed

if __name__ == "__main__":
    # Set paths
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / "data"
    
    schemes_csv = data_dir / "schemes_filtered.csv"
    jobs_csv = data_dir / "jobs_filtered.csv"
    upskill_csv = data_dir / "upskill_filtered.csv"
    
    print("="*80)
    print("LOADING FILTERED DATA INTO POSTGRESQL")
    print("="*80)
    
    # Connect to PostgreSQL
    conn = psycopg2.connect(PG_CONN)
    
    # Load all data
    total_schemes = load_schemes(schemes_csv, conn)
    total_jobs = load_jobs(jobs_csv, conn)
    total_upskill = load_upskill(upskill_csv, conn)
    
    conn.close()
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"✅ Schemes: {total_schemes} records loaded")
    print(f"✅ Jobs: {total_jobs} records loaded")
    print(f"✅ Training: {total_upskill} records loaded")
    print(f"\nTotal: {total_schemes + total_jobs + total_upskill} records")
    print("="*80)

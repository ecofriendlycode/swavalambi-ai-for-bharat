from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from dotenv import load_dotenv
import os
import json
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Load environment variables from .env file — override=True ensures
# .env always wins over shell-level env vars (e.g. AWS_DEFAULT_REGION)
load_dotenv(override=True)

# If running in Lambda with Secrets Manager, load credentials into env vars
# so agents can access them via os.getenv() as usual
def _load_secrets_to_env():
    secret_name = os.getenv("AI_SECRETS_NAME", "swavalambi/ai-credentials")
    use_local = os.getenv("USE_LOCAL_CREDENTIALS", "false").lower() == "true"
    
    # In Lambda, always try to load from Secrets Manager
    if use_local:
        logging.info("Using local credentials from .env")
        return
    
    try:
        import boto3
        client = boto3.client("secretsmanager", region_name=os.getenv("AWS_REGION", "us-east-1"))
        secret = client.get_secret_value(SecretId=secret_name)
        creds = json.loads(secret["SecretString"])
        
        # Populate env vars so agents can use them transparently
        if "anthropic" in creds and "api_key" in creds["anthropic"]:
            os.environ["ANTHROPIC_API_KEY"] = creds["anthropic"]["api_key"]
            logging.info("Loaded Anthropic API key from Secrets Manager")
        
        if "sarvam" in creds and "api_key" in creds["sarvam"]:
            os.environ["SARVAM_API_KEY"] = creds["sarvam"]["api_key"]
            logging.info("Loaded Sarvam API key from Secrets Manager")
        
        if "openai" in creds and "api_key" in creds["openai"]:
            os.environ["OPENAI_API_KEY"] = creds["openai"]["api_key"]
            logging.info("Loaded OpenAI API key from Secrets Manager")
        
        # PostgreSQL credentials
        if "postgres" in creds:
            pg = creds["postgres"]
            if "host" in pg:
                os.environ["POSTGRES_HOST"] = pg["host"]
            if "port" in pg:
                os.environ["POSTGRES_PORT"] = str(pg["port"])
            if "database" in pg:
                os.environ["POSTGRES_DATABASE"] = pg["database"]
            if "user" in pg:
                os.environ["POSTGRES_USER"] = pg["user"]
            if "password" in pg:
                os.environ["POSTGRES_PASSWORD"] = pg["password"]
            
            # Build connection string
            if all(k in pg for k in ["user", "password", "host", "port", "database"]):
                conn_str = f"postgresql://{pg['user']}:{pg['password']}@{pg['host']}:{pg['port']}/{pg['database']}"
                os.environ["POSTGRES_CONNECTION_STRING"] = conn_str
                logging.info("Loaded PostgreSQL credentials from Secrets Manager")
            
    except Exception as e:
        logging.error(f"Failed to load secrets from Secrets Manager: {e}")
        raise

_load_secrets_to_env()

from api.routes_auth import router as auth_router
from api.routes_chat import router as chat_router
from api.routes_vision import router as vision_router
from api.routes_rag import router as rag_router
from api.routes_recommendations import router as recommendations_router
from api.routes_users import router as users_router
from api.routes_voice import router as voice_router
from api.routes_profile_picture import router as profile_picture_router

app = FastAPI(
    title="Swavalambi AI Gateway Backend",
    description="Backend for conversational intent extraction, skill assessment, and dynamic routing.",
    version="1.0.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "http://swavalambi-frontend-1772381208.s3-website-us-east-1.amazonaws.com",
        "https://d21tmg809bunv0.cloudfront.net",
        "https://www.swavalambi.co.in",
        "https://swavalambi.co.in"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(chat_router, prefix="/api/chat", tags=["AI Gateway Chat"])
app.include_router(vision_router, prefix="/api/vision", tags=["Vision Assessment"])
app.include_router(voice_router, prefix="/api/voice", tags=["Voice Services"])
app.include_router(rag_router, prefix="/api/rag", tags=["RAG Personalization"])
app.include_router(recommendations_router, prefix="/api/recommendations", tags=["Recommendations"])
app.include_router(users_router, prefix="/api/users", tags=["User Profiles"])
app.include_router(profile_picture_router, prefix="/api", tags=["Profile Picture"])

@app.on_event("startup")
async def startup_event():
    """Initialize S3 bucket and agent instances on startup."""
    try:
        from services.s3_service import S3Service
        s3_service = S3Service()
        s3_service.ensure_bucket_exists()
    except Exception as e:
        logging.error(f"Failed to initialize S3 bucket: {e}")
    
    # Pre-initialize agent instances and connection pool
    try:
        from agents.agent_factory import get_jobs_agent, get_scheme_agent, get_upskill_agent
        logging.info("Pre-initializing agent instances...")
        get_jobs_agent()
        get_scheme_agent()
        get_upskill_agent()
        logging.info("✅ All agents pre-initialized with connection pool")
    except Exception as e:
        logging.error(f"Failed to pre-initialize agents: {e}")

@app.get("/health")
def health_check():
    return {"status": "ok"}

# Handler for AWS Lambda (Mangum wrapper)
# Configure Mangum to handle API Gateway v2 with stage prefix
handler = Mangum(app, lifespan="off", api_gateway_base_path="/prod")

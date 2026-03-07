#!/bin/bash
#
# Backend Deployment Script
# Deploys backend code changes to AWS Lambda
#
# Usage: ./deploy-backend.sh
#
# Configuration: Set these environment variables or edit deploy-config.sh
#   AWS_PROFILE - AWS CLI profile name
#   AWS_REGION - AWS region
#   LAMBDA_FUNCTION - Lambda function name
#   S3_BUCKET - S3 bucket for deployment packages
#   API_GATEWAY_URL - API Gateway base URL
#

set -e  # Exit on error

# Load configuration from deploy-config.sh if it exists
if [ -f "deploy-config.sh" ]; then
    source deploy-config.sh
fi

# Configuration with defaults (override via environment variables or deploy-config.sh)
AWS_PROFILE="${AWS_PROFILE:-default}"
AWS_REGION="${AWS_REGION:-us-east-1}"
LAMBDA_FUNCTION="${LAMBDA_FUNCTION:-swavalambi-api}"
S3_BUCKET="${S3_BUCKET:-your-lambda-bucket}"
API_GATEWAY_URL="${API_GATEWAY_URL:-https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com/prod}"
PACKAGE_NAME="deployment-minimal.zip"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Backend Deployment Script${NC}"
echo -e "${BLUE}========================================${NC}"

# Validate configuration
if [ "$S3_BUCKET" = "your-lambda-bucket" ]; then
    echo -e "${RED}Error: Please configure deployment settings${NC}"
    echo -e "${YELLOW}Create deploy-config.sh with your AWS settings:${NC}"
    echo -e "  cp deploy-config.example.sh deploy-config.sh"
    echo -e "  # Edit deploy-config.sh with your values"
    exit 1
fi

echo -e "\nConfiguration:"
echo -e "  AWS Profile: $AWS_PROFILE"
echo -e "  AWS Region: $AWS_REGION"
echo -e "  Lambda Function: $LAMBDA_FUNCTION"
echo -e "  S3 Bucket: $S3_BUCKET"

# Check if we're in the right directory
if [ ! -f "backend/main.py" ]; then
    echo -e "${RED}Error: Please run this script from the project root directory${NC}"
    exit 1
fi

cd backend

echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}Deploying Backend${NC}"
echo -e "${BLUE}========================================${NC}"

echo -e "\n${YELLOW}Step 1: Packaging backend code...${NC}"
# Remove old package if exists
rm -f $PACKAGE_NAME

# Clean up old installations
echo -e "${YELLOW}Cleaning up old packages...${NC}"
rm -rf PIL/ Pillow* psycopg2/ psycopg2_binary* pgvector/ pgvector* *.dist-info/ *.libs/ numpy/ numpy*

# Install binary packages directly into backend directory (will be included in zip)
echo -e "${YELLOW}Installing binary packages for Lambda (Linux x86_64)...${NC}"

# Install numpy first (dependency for pgvector)
pip install numpy==1.26.4 -t . \
    --platform manylinux2014_x86_64 \
    --only-binary=:all: \
    --upgrade \
    --quiet

# Install psycopg2-binary
pip install psycopg2-binary==2.9.9 -t . \
    --platform manylinux2014_x86_64 \
    --only-binary=:all: \
    --upgrade \
    --quiet

# Install pgvector
pip install pgvector==0.3.6 -t . \
    --platform manylinux2014_x86_64 \
    --only-binary=:all: \
    --upgrade \
    --quiet

# Install Pillow
pip install Pillow==10.0.0 -t . \
    --platform manylinux2014_x86_64 \
    --only-binary=:all: \
    --upgrade \
    --quiet

# Install sarvamai SDK
pip install sarvamai -t . \
    --upgrade \
    --quiet

# Install websockets
pip install websockets -t . \
    --upgrade \
    --quiet

echo -e "${GREEN}✓ Binary packages installed${NC}"

# Verify packages were installed
if [ ! -d "numpy" ]; then
    echo -e "${RED}✗ numpy installation failed${NC}"
    exit 1
fi

if [ ! -d "psycopg2" ]; then
    echo -e "${RED}✗ psycopg2 installation failed${NC}"
    exit 1
fi

if [ ! -d "pgvector" ]; then
    echo -e "${RED}✗ pgvector installation failed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Verified: numpy, psycopg2, pgvector, Pillow installed${NC}"

# Create deployment package (code + binary packages)
echo -e "${YELLOW}Creating deployment package...${NC}"
zip -r $PACKAGE_NAME \
  main.py \
  agents/ \
  api/ \
  services/ \
  schemas/ \
  common/ \
  PIL/ \
  Pillow* \
  psycopg2/ \
  psycopg2_binary* \
  pgvector/ \
  pgvector* \
  numpy/ \
  numpy* \
  sarvamai/ \
  sarvamai* \
  websockets/ \
  websockets* \
  -x "*.pyc" -x "__pycache__/*" -x "tests/*" -x ".env" -x "*.md" > /dev/null

PACKAGE_SIZE=$(du -h $PACKAGE_NAME | cut -f1)
echo -e "${GREEN}✓ Package created: $PACKAGE_NAME ($PACKAGE_SIZE)${NC}"

echo -e "\n${YELLOW}Step 2: Uploading to S3...${NC}"
aws s3 cp $PACKAGE_NAME s3://$S3_BUCKET/ \
  --profile $AWS_PROFILE \
  --region $AWS_REGION

echo -e "${GREEN}✓ Uploaded to S3${NC}"

echo -e "\n${YELLOW}Step 3: Deploying to Lambda...${NC}"
aws lambda update-function-code \
  --function-name $LAMBDA_FUNCTION \
  --s3-bucket $S3_BUCKET \
  --s3-key $PACKAGE_NAME \
  --profile $AWS_PROFILE \
  --region $AWS_REGION \
  --output json > /dev/null

echo -e "${GREEN}✓ Deployed to Lambda${NC}"

echo -e "\n${YELLOW}Step 4: Waiting for code update to complete...${NC}"
aws lambda wait function-updated \
  --function-name $LAMBDA_FUNCTION \
  --profile $AWS_PROFILE \
  --region $AWS_REGION

echo -e "${GREEN}✓ Code update complete${NC}"

echo -e "\n${YELLOW}Step 5: Updating Lambda configuration...${NC}"

# Load non-sensitive env vars from .env.lambda (script runs inside backend/)
# To add a new Lambda env var: add it to backend/.env.lambda and reference it below
if [ -f ".env.lambda" ]; then
    source .env.lambda
else
    echo -e "${RED}Error: backend/.env.lambda not found${NC}"
    exit 1
fi

# Cognito IDs come from deploy-config.sh (environment-specific, not secrets)
if [ -z "$COGNITO_USER_POOL_ID" ] || [ -z "$COGNITO_CLIENT_ID" ]; then
    echo -e "${RED}Error: COGNITO_USER_POOL_ID and COGNITO_CLIENT_ID must be set in deploy-config.sh${NC}"
    exit 1
fi

aws lambda update-function-configuration \
  --function-name $LAMBDA_FUNCTION \
  --environment "Variables={
    AI_SECRETS_NAME=${AI_SECRETS_NAME},
    USE_LOCAL_CREDENTIALS=${USE_LOCAL_CREDENTIALS},
    USE_ANTHROPIC=${USE_ANTHROPIC},
    ANTHROPIC_MODEL_ID=${ANTHROPIC_MODEL_ID},
    BEDROCK_MODEL_ID=${BEDROCK_MODEL_ID},
    BEDROCK_EMBEDDING_MODEL=${BEDROCK_EMBEDDING_MODEL},
    ENABLE_STREAMING=${ENABLE_STREAMING},
    DYNAMODB_TABLE=${DYNAMODB_TABLE},
    COGNITO_USER_POOL_ID=${COGNITO_USER_POOL_ID},
    COGNITO_CLIENT_ID=${COGNITO_CLIENT_ID},
    VECTOR_STORE=${VECTOR_STORE},
    EMBEDDING_PROVIDER=${EMBEDDING_PROVIDER},
    EMBEDDING_CACHE_FILE=${EMBEDDING_CACHE_FILE},
    VOICE_PROVIDER=${VOICE_PROVIDER},
    VOICE_FALLBACK_ENABLED=${VOICE_FALLBACK_ENABLED},
    VOICE_ENABLE_TRANSLATION=${VOICE_ENABLE_TRANSLATION},
    VOICE_AUTO_PLAY=${VOICE_AUTO_PLAY},
    VOICE_SPEED=${VOICE_SPEED},
    SARVAM_STT_MODEL=${SARVAM_STT_MODEL},
    SARVAM_TTS_MODEL=${SARVAM_TTS_MODEL},
    SARVAM_TTS_SPEAKER=${SARVAM_TTS_SPEAKER},
    SARVAM_TRANSLATE_MODEL=${SARVAM_TRANSLATE_MODEL},
    SARVAM_TTS_SPEAKER_HI=${SARVAM_TTS_SPEAKER_HI},
    SARVAM_TTS_SPEAKER_TE=${SARVAM_TTS_SPEAKER_TE},
    SARVAM_TTS_SPEAKER_TA=${SARVAM_TTS_SPEAKER_TA},
    SARVAM_TTS_SPEAKER_MR=${SARVAM_TTS_SPEAKER_MR},
    SARVAM_TTS_SPEAKER_KN=${SARVAM_TTS_SPEAKER_KN},
    SARVAM_TTS_SPEAKER_BN=${SARVAM_TTS_SPEAKER_BN},
    SARVAM_TTS_SPEAKER_GU=${SARVAM_TTS_SPEAKER_GU},
    SARVAM_TTS_SPEAKER_ML=${SARVAM_TTS_SPEAKER_ML},
    SARVAM_TTS_SPEAKER_PA=${SARVAM_TTS_SPEAKER_PA},
    SARVAM_TTS_SPEAKER_EN=${SARVAM_TTS_SPEAKER_EN},
    AWS_S3_BUCKET=${AWS_S3_BUCKET},
    AWS_TRANSCRIBE_LANGUAGE=${AWS_TRANSCRIBE_LANGUAGE},
    AWS_POLLY_VOICE_ID=${AWS_POLLY_VOICE_ID},
    AWS_TRANSLATE_SOURCE_LANG=${AWS_TRANSLATE_SOURCE_LANG},
    AWS_TRANSLATE_TARGET_LANG=${AWS_TRANSLATE_TARGET_LANG},
    AWS_S3_BUCKET_NAME=${AWS_S3_BUCKET_NAME},
    VISION_MAX_FILE_SIZE_MB=${VISION_MAX_FILE_SIZE_MB},
    VISION_MAX_UPLOADS_PER_HOUR=${VISION_MAX_UPLOADS_PER_HOUR},
    VISION_MAX_UPLOADS_PER_10MIN=${VISION_MAX_UPLOADS_PER_10MIN},
    POSTGRES_HOST=${POSTGRES_HOST},
    POSTGRES_PORT=${POSTGRES_PORT},
    POSTGRES_DATABASE=${POSTGRES_DATABASE},
    POSTGRES_USER=${POSTGRES_USER}
  }" \
  --profile $AWS_PROFILE \
  --region $AWS_REGION \
  --output json > /dev/null

echo -e "${GREEN}✓ Configuration updated${NC}"

echo -e "\n${YELLOW}Step 6: Updating API Gateway CORS...${NC}"
# Get API Gateway ID from the API URL
API_ID=$(echo $API_GATEWAY_URL | sed -n 's|https://\([^.]*\)\.execute-api\..*|\1|p')

if [ -n "$API_ID" ]; then
    aws apigatewayv2 update-api \
      --api-id $API_ID \
      --cors-configuration "AllowOrigins=http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000,${S3_WEBSITE_URL},${CLOUDFRONT_URL},https://www.swavalambi.co.in,https://swavalambi.co.in,AllowMethods=GET,POST,PUT,DELETE,OPTIONS,PATCH,AllowHeaders=*,AllowCredentials=true,MaxAge=3600" \
      --profile $AWS_PROFILE \
      --region $AWS_REGION \
      --output json > /dev/null
    
    echo -e "${GREEN}✓ API Gateway CORS updated${NC}"
else
    echo -e "${YELLOW}⚠ Could not extract API Gateway ID - skipping CORS update${NC}"
fi

echo -e "\n${YELLOW}Step 7: Waiting for configuration update...${NC}"
sleep 3

echo -e "\n${YELLOW}Step 8: Testing health endpoint...${NC}"
HEALTH_URL="${API_GATEWAY_URL}/health"
RESPONSE=$(curl -s $HEALTH_URL)

if [[ $RESPONSE == *"ok"* ]]; then
    echo -e "${GREEN}✓ Health check passed: $RESPONSE${NC}"
else
    echo -e "${RED}✗ Health check failed: $RESPONSE${NC}"
    echo -e "${YELLOW}Check logs: aws logs tail /aws/lambda/$LAMBDA_FUNCTION --follow --profile $AWS_PROFILE --region $AWS_REGION${NC}"
fi

echo -e "\n${BLUE}========================================${NC}"
echo -e "${GREEN}Backend deployment complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "\nEndpoints:"
echo -e "  Health: ${API_GATEWAY_URL}/health"
echo -e "  API: ${API_GATEWAY_URL}"
echo -e "  Docs: ${API_GATEWAY_URL}/docs"
echo -e "\nView logs:"
echo -e "  aws logs tail /aws/lambda/$LAMBDA_FUNCTION --follow --profile $AWS_PROFILE --region $AWS_REGION"
echo ""

cd ..

#!/bin/bash
#
# Setup AWS Secrets Manager for Swavalambi
# Stores all API keys and sensitive credentials
#

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}AWS Secrets Manager Setup${NC}"
echo -e "${GREEN}========================================${NC}"

# Load from .env
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    exit 1
fi

source .env

# Configuration
SECRET_NAME="swavalambi/api-keys"
AWS_PROFILE="swavalambi-cli"
AWS_REGION="us-east-1"

echo -e "\n${YELLOW}Creating secret with all API keys...${NC}"

# Create JSON with all secrets
SECRET_JSON=$(cat <<EOF
{
  "ANTHROPIC_API_KEY": "$ANTHROPIC_API_KEY",
  "SARVAM_API_KEY": "$SARVAM_API_KEY",
  "AZURE_OPENAI_API_KEY": "$AZURE_OPENAI_API_KEY",
  "AZURE_OPENAI_ENDPOINT": "$AZURE_OPENAI_ENDPOINT",
  "AZURE_OPENAI_DEPLOYMENT": "$AZURE_OPENAI_DEPLOYMENT",
  "AZURE_OPENAI_API_VERSION": "$AZURE_OPENAI_API_VERSION",
  "POSTGRES_PASSWORD": "$POSTGRES_PASSWORD"
}
EOF
)

# Try to create secret (will fail if exists)
aws secretsmanager create-secret \
    --name $SECRET_NAME \
    --description "Swavalambi API keys and credentials" \
    --secret-string "$SECRET_JSON" \
    --profile $AWS_PROFILE \
    --region $AWS_REGION 2>/dev/null

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Secret created successfully${NC}"
else
    # Secret exists, update it
    echo -e "${YELLOW}Secret exists, updating...${NC}"
    aws secretsmanager update-secret \
        --secret-id $SECRET_NAME \
        --secret-string "$SECRET_JSON" \
        --profile $AWS_PROFILE \
        --region $AWS_REGION > /dev/null
    
    echo -e "${GREEN}✓ Secret updated successfully${NC}"
fi

# Get secret ARN
SECRET_ARN=$(aws secretsmanager describe-secret \
    --secret-id $SECRET_NAME \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    --query 'ARN' \
    --output text)

echo -e "\n${GREEN}Secret Details:${NC}"
echo -e "  Name: $SECRET_NAME"
echo -e "  ARN: $SECRET_ARN"

echo -e "\n${YELLOW}Updating Lambda IAM permissions...${NC}"

# Create IAM policy for Secrets Manager access
POLICY_JSON=$(cat <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "secretsmanager:GetSecretValue",
                "secretsmanager:DescribeSecret"
            ],
            "Resource": "$SECRET_ARN"
        }
    ]
}
EOF
)

# Get Lambda role name
LAMBDA_ROLE=$(aws lambda get-function \
    --function-name swavalambi-api \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    --query 'Configuration.Role' \
    --output text | awk -F'/' '{print $NF}')

echo -e "  Lambda Role: $LAMBDA_ROLE"

# Attach policy to Lambda role
aws iam put-role-policy \
    --role-name $LAMBDA_ROLE \
    --policy-name SecretsManagerAccess \
    --policy-document "$POLICY_JSON" \
    --profile $AWS_PROFILE 2>/dev/null

echo -e "${GREEN}✓ IAM permissions updated${NC}"

echo -e "\n${YELLOW}Updating Lambda environment variables...${NC}"

# Update Lambda to use Secrets Manager
aws lambda update-function-configuration \
    --function-name swavalambi-api \
    --environment "Variables={
        USE_SECRETS_MANAGER=true,
        SECRETS_NAME=$SECRET_NAME,
        AWS_DEFAULT_REGION=$AWS_REGION,
        POSTGRES_HOST=$POSTGRES_HOST,
        POSTGRES_PORT=$POSTGRES_PORT,
        POSTGRES_DATABASE=$POSTGRES_DATABASE,
        POSTGRES_USER=$POSTGRES_USER
    }" \
    --profile $AWS_PROFILE \
    --region $AWS_REGION > /dev/null

echo -e "${GREEN}✓ Lambda environment updated${NC}"

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"

echo -e "\n${YELLOW}Next steps:${NC}"
echo -e "  1. Update backend/main.py to load from Secrets Manager"
echo -e "  2. Remove API keys from .env (keep only non-sensitive config)"
echo -e "  3. Redeploy: ./deploy-backend.sh"
echo -e "\n${YELLOW}Test secret access:${NC}"
echo -e "  aws secretsmanager get-secret-value --secret-id $SECRET_NAME --profile $AWS_PROFILE --region $AWS_REGION"
echo ""

#!/bin/bash
#
# Update AWS Secrets Manager with Sarvam API key
#

set -e

# Load from .env
if [ ! -f ".env" ]; then
    echo "Error: .env file not found"
    exit 1
fi

source .env

SECRET_NAME="swavalambi/ai-credentials"
AWS_PROFILE="swavalambi-cli"
AWS_REGION="us-east-1"

echo "Fetching current secret..."

# Get current secret
CURRENT_SECRET=$(aws secretsmanager get-secret-value \
    --secret-id $SECRET_NAME \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    --query SecretString \
    --output text)

echo "Current secret structure:"
echo "$CURRENT_SECRET" | jq .

# Update with Sarvam key (preserving existing keys)
UPDATED_SECRET=$(echo "$CURRENT_SECRET" | jq --arg key "$SARVAM_API_KEY" '. + {"sarvam": {"api_key": $key}}')

echo ""
echo "Updating secret with Sarvam API key..."

aws secretsmanager update-secret \
    --secret-id $SECRET_NAME \
    --secret-string "$UPDATED_SECRET" \
    --profile $AWS_PROFILE \
    --region $AWS_REGION > /dev/null

echo "✓ Secret updated successfully"
echo ""
echo "Next: Redeploy backend with ./deploy-backend.sh"

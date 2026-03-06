#!/bin/bash
#
# Setup custom domain for CloudFront
#

set -e

# Load configuration
if [ -f "deploy-config.sh" ]; then
    source deploy-config.sh
fi

AWS_PROFILE="${AWS_PROFILE:-swavalambi-cli}"
CUSTOM_DOMAIN="${CUSTOM_DOMAIN:-www.swavalambi.co.in}"
APEX_DOMAIN="${APEX_DOMAIN:-swavalambi.co.in}"

echo "Setting up custom domain: $CUSTOM_DOMAIN"

# Get CloudFront distribution ID
DIST_ID=$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?contains(DomainName, 'd21tmg809bunv0')].Id" \
  --output text \
  --profile $AWS_PROFILE)

echo "Distribution ID: $DIST_ID"

# Get current config and ETag
aws cloudfront get-distribution-config \
  --id $DIST_ID \
  --profile $AWS_PROFILE \
  --output json > cf-temp.json

ETAG=$(jq -r '.ETag' cf-temp.json)
echo "ETag: $ETAG"

# Extract just the DistributionConfig
jq '.DistributionConfig' cf-temp.json > cf-config.json

# Update Aliases and Certificate
CERT_ARN="${CERTIFICATE_ARN:-$NEW_CERT_ARN}"

if [ -z "$CERT_ARN" ]; then
    echo "Error: Certificate ARN not found. Set NEW_CERT_ARN environment variable."
    echo "Example: export NEW_CERT_ARN=arn:aws:acm:us-east-1:..."
    exit 1
fi

echo "Using certificate: $CERT_ARN"

jq --arg domain1 "$CUSTOM_DOMAIN" --arg domain2 "$APEX_DOMAIN" --arg cert "$CERT_ARN" \
  '.Aliases = {"Quantity": 2, "Items": [$domain1, $domain2]} |
   .ViewerCertificate = {
     "ACMCertificateArn": $cert,
     "SSLSupportMethod": "sni-only",
     "MinimumProtocolVersion": "TLSv1.2_2021",
     "Certificate": $cert,
     "CertificateSource": "acm"
   }' \
  cf-config.json > cf-config-updated.json

# Apply update
aws cloudfront update-distribution \
  --id $DIST_ID \
  --if-match $ETAG \
  --distribution-config file://cf-config-updated.json \
  --profile $AWS_PROFILE

echo "✓ CloudFront updated"
echo "Wait 5-10 minutes for changes to propagate"
echo "Then test: https://$CUSTOM_DOMAIN"
echo ""
echo "Next steps:"
echo "  1. Update CORS in backend/main.py to include https://$CUSTOM_DOMAIN"
echo "  2. Redeploy backend: ./deploy-backend.sh"
echo "  3. (Optional) Get SSL certificate from AWS Certificate Manager"

# Cleanup
rm cf-temp.json cf-config.json cf-config-updated.json

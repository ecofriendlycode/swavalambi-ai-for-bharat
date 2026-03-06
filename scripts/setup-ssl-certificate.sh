#!/bin/bash
#
# Request SSL certificate from AWS Certificate Manager
#

set -e

# Load configuration
if [ -f "deploy-config.sh" ]; then
    source deploy-config.sh
fi

AWS_PROFILE="${AWS_PROFILE:-swavalambi-cli}"
DOMAIN="${CUSTOM_DOMAIN:-swavalambi.co.in}"
WWW_DOMAIN="www.${DOMAIN}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}SSL Certificate Setup${NC}"
echo -e "${BLUE}========================================${NC}"

echo -e "\n${YELLOW}Step 1: Requesting SSL certificate...${NC}"
echo "Domain: $DOMAIN"
echo "Alternate: $WWW_DOMAIN"

# Request certificate (must be in us-east-1 for CloudFront)
CERT_ARN=$(aws acm request-certificate \
  --domain-name $DOMAIN \
  --subject-alternative-names $WWW_DOMAIN \
  --validation-method DNS \
  --region us-east-1 \
  --profile $AWS_PROFILE \
  --query 'CertificateArn' \
  --output text)

echo -e "${GREEN}✓ Certificate requested${NC}"
echo "Certificate ARN: $CERT_ARN"

echo -e "\n${YELLOW}Step 2: Getting DNS validation records...${NC}"
sleep 5  # Wait for AWS to generate validation records

aws acm describe-certificate \
  --certificate-arn $CERT_ARN \
  --region us-east-1 \
  --profile $AWS_PROFILE \
  --query 'Certificate.DomainValidationOptions[*].[DomainName,ResourceRecord.Name,ResourceRecord.Value]' \
  --output table

echo -e "\n${BLUE}========================================${NC}"
echo -e "${YELLOW}IMPORTANT: Add these DNS records in GoDaddy${NC}"
echo -e "${BLUE}========================================${NC}"

# Get validation records in a more readable format
VALIDATION=$(aws acm describe-certificate \
  --certificate-arn $CERT_ARN \
  --region us-east-1 \
  --profile $AWS_PROFILE \
  --query 'Certificate.DomainValidationOptions[0].ResourceRecord' \
  --output json)

RECORD_NAME=$(echo $VALIDATION | jq -r '.Name')
RECORD_VALUE=$(echo $VALIDATION | jq -r '.Value')

echo -e "\n${YELLOW}Go to GoDaddy DNS Management and add:${NC}"
echo -e "  Type: ${GREEN}CNAME${NC}"
echo -e "  Name: ${GREEN}${RECORD_NAME}${NC}"
echo -e "  Value: ${GREEN}${RECORD_VALUE}${NC}"
echo -e "  TTL: ${GREEN}600${NC}"

echo -e "\n${YELLOW}After adding the DNS record:${NC}"
echo "  1. Wait 5-10 minutes for DNS propagation"
echo "  2. Check certificate status:"
echo "     aws acm describe-certificate --certificate-arn $CERT_ARN --region us-east-1 --profile $AWS_PROFILE --query 'Certificate.Status'"
echo "  3. Once status is 'ISSUED', run:"
echo "     ./setup-custom-domain.sh"

echo -e "\n${BLUE}Certificate ARN (save this):${NC}"
echo "$CERT_ARN"

# Save to file for later use
echo "CERTIFICATE_ARN=$CERT_ARN" > .ssl-cert-arn

echo -e "\n${GREEN}Done! Follow the steps above to validate your certificate.${NC}"

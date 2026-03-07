#!/bin/bash
#
# ECS Deployment Script
# Builds Docker image, pushes to ECR, and updates ECS service
#
# Usage: ./deploy-ecs.sh
# Requires: deploy-config.sh with ECR_REPO, ECS_CLUSTER, ECS_SERVICE set
#

set -e

# Load configuration
if [ -f "deploy-config.sh" ]; then
    source deploy-config.sh
else
    echo "Error: deploy-config.sh not found"
    exit 1
fi

# Validate required config
if [ -z "$ECR_REPO" ] || [ -z "$ECS_CLUSTER" ] || [ -z "$ECS_SERVICE" ]; then
    echo "Error: ECR_REPO, ECS_CLUSTER, ECS_SERVICE must be set in deploy-config.sh"
    echo "Add:"
    echo "  export ECR_REPO=<account-id>.dkr.ecr.us-east-1.amazonaws.com/swavalambi-backend"
    echo "  export ECS_CLUSTER=swavalambi-cluster"
    echo "  export ECS_SERVICE=swavalambi-backend"
    exit 1
fi

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}ECS Deployment Script${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "  ECR Repo:    $ECR_REPO"
echo -e "  ECS Cluster: $ECS_CLUSTER"
echo -e "  ECS Service: $ECS_SERVICE"

echo -e "\n${YELLOW}Step 1: Logging in to ECR...${NC}"
aws ecr get-login-password \
  --region $AWS_REGION \
  --profile $AWS_PROFILE | \
  docker login --username AWS --password-stdin \
  $(echo $ECR_REPO | cut -d'/' -f1)
echo -e "${GREEN}✓ ECR login successful${NC}"

echo -e "\n${YELLOW}Step 2: Building Docker image...${NC}"
docker build -t swavalambi-backend ./backend
echo -e "${GREEN}✓ Image built${NC}"

echo -e "\n${YELLOW}Step 3: Tagging and pushing to ECR...${NC}"
docker tag swavalambi-backend:latest $ECR_REPO:latest
docker push $ECR_REPO:latest
echo -e "${GREEN}✓ Image pushed to ECR${NC}"

echo -e "\n${YELLOW}Step 4: Updating ECS service...${NC}"
aws ecs update-service \
  --cluster $ECS_CLUSTER \
  --service $ECS_SERVICE \
  --force-new-deployment \
  --profile $AWS_PROFILE \
  --region $AWS_REGION \
  --output json > /dev/null
echo -e "${GREEN}✓ ECS service update triggered${NC}"

echo -e "\n${YELLOW}Step 5: Waiting for deployment to stabilize...${NC}"
aws ecs wait services-stable \
  --cluster $ECS_CLUSTER \
  --services $ECS_SERVICE \
  --profile $AWS_PROFILE \
  --region $AWS_REGION
echo -e "${GREEN}✓ ECS service stable${NC}"

echo -e "\n${BLUE}========================================${NC}"
echo -e "${GREEN}ECS deployment complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "\nView logs:"
echo -e "  aws logs tail /ecs/swavalambi-backend --follow --profile $AWS_PROFILE --region $AWS_REGION"

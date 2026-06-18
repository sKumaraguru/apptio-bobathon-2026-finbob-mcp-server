#!/bin/bash
set -e

# Detect container runtime (docker or podman)
if command -v podman &> /dev/null; then
    CONTAINER_CMD="podman"
    echo "🐳 Using Podman as container runtime"
elif command -v docker &> /dev/null; then
    CONTAINER_CMD="docker"
    echo "🐳 Using Docker as container runtime"
else
    echo "❌ Error: Neither docker nor podman found. Please install one of them."
    exit 1
fi

# Configuration
STAGE="${1:-dev1}"
REGION="${2:-us-east-1}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
SERVICE_NAME="csa-assessments-mcp"
REPO_NAME="${SERVICE_NAME}-${STAGE}-mcpserver"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}"

echo "🚀 Deploying MCP Server with Docker image"
echo "   Stage: ${STAGE}"
echo "   Region: ${REGION}"
echo "   ECR Repository: ${REPO_NAME}"
echo ""

# Step 1: Prepare dependencies
# echo "📦 Step 1: Preparing dependencies..."
# npm run prepare
# echo "✅ Dependencies prepared"
# echo ""

# Step 2: Create ECR repository if it doesn't exist
echo "🏗️  Step 2: Ensuring ECR repository exists..."
if aws ecr describe-repositories --repository-names "${REPO_NAME}" --region "${REGION}" >/dev/null 2>&1; then
    echo "✅ ECR repository already exists: ${REPO_NAME}"
else
    echo "   Creating ECR repository: ${REPO_NAME}"
    aws ecr create-repository \
        --repository-name "${REPO_NAME}" \
        --region "${REGION}" \
        --image-scanning-configuration scanOnPush=true \
        --tags Key=Service,Value=${SERVICE_NAME} Key=Environment,Value=${STAGE}
    echo "✅ ECR repository created"
fi
echo ""

# Step 3: Build Docker image
echo "🐳 Step 3: Building Docker image..."
echo "   Command: ${CONTAINER_CMD} build --platform linux/arm64 -t ${REPO_NAME}:latest -f mcp/Dockerfile mcp/"
${CONTAINER_CMD} build --platform linux/arm64 -t "${REPO_NAME}:latest" -f mcp/Dockerfile mcp/

# Verify image was created
echo "   Verifying image was created..."
if ${CONTAINER_CMD} images | grep -q "${REPO_NAME}"; then
    echo "✅ Docker image built successfully"
    ${CONTAINER_CMD} images | grep "${REPO_NAME}"
else
    echo "❌ Error: Image was not created"
    echo "   Listing all images:"
    ${CONTAINER_CMD} images
    exit 1
fi
echo ""

# Step 4: Authenticate with ECR
echo "🔐 Step 4: Authenticating with ECR..."
aws ecr get-login-password --region "${REGION}" | \
    ${CONTAINER_CMD} login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
echo "✅ Authenticated with ECR"
echo ""

# Step 5: Tag and push image
echo "📤 Step 5: Tagging and pushing image to ECR..."
echo "   Tagging: ${REPO_NAME}:latest -> ${ECR_URI}:latest"
${CONTAINER_CMD} tag "${REPO_NAME}:latest" "${ECR_URI}:latest"

echo "   Pushing to ECR..."
${CONTAINER_CMD} push "${ECR_URI}:latest"
echo "✅ Image pushed to ECR"
echo ""

# Step 6: Clear Serverless cache
echo "🧹 Step 6: Clearing Serverless cache..."
rm -rf .serverless
echo "✅ Cache cleared"
echo ""

# Step 7: Deploy Serverless stack
echo "☁️  Step 7: Deploying Serverless stack..."
serverless deploy --stage "${STAGE}" --region "${REGION}" --param "ENVIRONMENT_TAG=dev"
echo "✅ Serverless stack deployed"
echo ""

echo "🎉 Deployment complete!"
echo ""
echo "Verify deployment:"
echo "  aws ecr list-images --repository-name ${REPO_NAME} --region ${REGION}"
echo "  aws ecs list-tasks --cluster ${SERVICE_NAME}-${STAGE} --region ${REGION}"

# Made with Bob

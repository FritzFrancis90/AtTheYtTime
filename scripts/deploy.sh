#!/usr/bin/env bash
set -euo pipefail

# Configuration (can be overridden via environment variables)
AWS_REGION="${AWS_REGION:-us-east-1}"
ECR_REPO_NAME="${ECR_REPO_NAME:-podtube}"
LAMBDA_FUNCTION_NAME="${LAMBDA_FUNCTION_NAME:-podtube-sync}"

echo "==> 1/5 Running unit tests..."
python3 -m unittest discover -s tests -v

echo "==> 2/5 Resolving AWS Account & authenticating Docker with ECR (${AWS_REGION})..."
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
aws ecr get-login-password --region "${AWS_REGION}" | \
  docker login --username AWS --password-stdin "${ECR_URI}"

echo "==> 3/5 Building Docker image (${ECR_REPO_NAME}:latest for linux/amd64)..."
docker build \
  --platform linux/amd64 \
  --provenance=false \
  -t "${ECR_REPO_NAME}:latest" .

echo "==> 4/5 Pushing image to ECR (${ECR_URI}/${ECR_REPO_NAME}:latest)..."
docker tag "${ECR_REPO_NAME}:latest" "${ECR_URI}/${ECR_REPO_NAME}:latest"
docker push "${ECR_URI}/${ECR_REPO_NAME}:latest"

echo "==> 5/5 Updating Lambda function (${LAMBDA_FUNCTION_NAME})..."
aws lambda update-function-code \
  --function-name "${LAMBDA_FUNCTION_NAME}" \
  --image-uri "${ECR_URI}/${ECR_REPO_NAME}:latest" \
  --region "${AWS_REGION}" >/dev/null

echo "Waiting for Lambda update to complete..."
aws lambda wait function-updated \
  --function-name "${LAMBDA_FUNCTION_NAME}" \
  --region "${AWS_REGION}"

echo "Deployment complete!"


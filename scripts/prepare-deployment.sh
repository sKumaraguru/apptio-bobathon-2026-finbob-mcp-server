#!/bin/bash
set -e

echo "🔧 Preparing deployment packages..."
echo ""

# ============================================
# Backend Preparation (Lambda with vendor/)
# ============================================
echo "📦 Backend: Preparing Lambda deployment package..."

# Clean up existing artifacts
echo "  ├─ Cleaning up old artifacts..."
rm -rf backend/vendor
rm -rf backend/.deployment-venv
mkdir -p backend/vendor

cd backend

echo "  ├─ Creating temporary virtual environment..."
# Create a temporary venv for deployment
uv venv .deployment-venv --python python3.13

echo "  ├─ Installing dependencies with uv sync..."
echo "     (This properly uses CodeArtifact index configuration from pyproject.toml)"
# Use uv sync to install all dependencies - this respects the index configuration
# and properly handles private CodeArtifact packages (cwcore, cwshareddriveutils)
VIRTUAL_ENV=.deployment-venv uv sync --no-dev --active

echo "  ├─ Copying installed packages to vendor/..."
cp -r .deployment-venv/lib/python3.13/site-packages/* vendor/

echo "  ├─ Replacing native packages with Linux ARM64 versions..."
# Remove macOS native packages
rm -rf vendor/numpy vendor/numpy.libs vendor/numpy*.dist-info
rm -rf vendor/pandas vendor/pandas*.dist-info
rm -rf vendor/cffi vendor/cffi*.dist-info vendor/_cffi_backend*.so

# Download Linux ARM64 versions of native packages
uv pip install pip --python .deployment-venv/bin/python
.deployment-venv/bin/pip download \
  --platform manylinux_2_28_aarch64 \
  --platform manylinux2014_aarch64 \
  --python-version 3.13 \
  --implementation cp \
  --only-binary=:all: \
  --no-deps \
  -d /tmp/lambda-wheels \
  "numpy>=2.0,<3" \
  "pandas>=2.0,<4" \
  "cffi>=1.17,<2"

# Unpack into vendor
for whl in /tmp/lambda-wheels/*.whl; do
  unzip -qo "$whl" -d vendor/
done

# echo "  ├─ Exporting requirements..."
# uv export --no-dev --no-hashes > /tmp/lambda-requirements.txt

# echo "  ├─ Exporting requirements..."
# uv export --no-dev --no-hashes > /tmp/lambda-requirements.txt

# echo "  ├─ Installing Linux ARM64 packages into vendor/..."
# uv pip install pip --python .deployment-venv/bin/python
# .deployment-venv/bin/python -m pip download \
#   --platform manylinux2014_aarch64 \
#   --platform manylinux_2_28_aarch64 \
#   --python-version 3.13 \
#   --implementation cp \
#   --only-binary=:all: \
#   --extra-index-url "https://${UV_INDEX_CW_USERNAME}:${UV_INDEX_CW_PASSWORD}@cloudwiry-282711413064.d.codeartifact.us-west-2.amazonaws.com/pypi/r0/simple/" \
#   -r /tmp/lambda-requirements.txt \
#   -d /tmp/lambda-wheels || true

# echo "  ├─ Unpacking wheels into vendor/..."
# for whl in /tmp/lambda-wheels/*.whl; do
#   unzip -qo "$whl" -d vendor/
# done

# echo "  ├─ Cleaning up..."
# rm -rf /tmp/lambda-wheels /tmp/lambda-requirements.txt

# echo "  ├─ Copying installed packages to vendor/ folder..."
# # Copy all installed packages from the venv to vendor/
# # Python 3.13 is the target runtime
# cp -r .deployment-venv/lib/python3.13/site-packages/* vendor/

echo "  ├─ Cleaning up temporary virtual environment..."
rm -rf .deployment-venv

echo "  ├─ Creating empty requirements.txt for serverless plugin..."
# The serverless-python-requirements plugin expects this file
touch requirements.txt

echo "  └─ Backend vendor folder ready!"
du -sh vendor/

cd ..

echo ""

# ============================================
# MCP Server Preparation (ECS Fargate)
# ============================================
echo "📦 MCP Server: Preparing Docker deployment..."

cd mcp

echo "  ├─ Generating requirements.txt..."
uv export --no-dev --no-hashes > requirements.txt

echo "  └─ MCP requirements.txt ready!"
wc -l requirements.txt

cd ..

echo ""
echo "✅ Deployment preparation complete!"
echo ""
echo "Summary:"
echo "  • Backend vendor/: $(du -sh backend/vendor/ | cut -f1)"
echo "  • Backend requirements.txt: Empty (dependencies in vendor/)"
echo "  • MCP requirements.txt: $(wc -l < mcp/requirements.txt) dependencies"

# Made with Bob

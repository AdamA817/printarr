#!/bin/bash
#
# Printarr Deploy Script for Unraid
# ==================================
#
# This script builds and deploys Printarr on an Unraid server.
#
# Prerequisites:
#   - Git installed on Unraid
#   - Docker installed (comes with Unraid)
#   - This repo cloned to your Unraid server
#
# Setup:
#   1. Clone this repo: git clone https://github.com/AdamA817/printarr.git
#   2. Copy deploy.conf.example to deploy.conf: cp scripts/deploy.conf.example scripts/deploy.conf
#   3. Edit deploy.conf with your paths
#   4. Run: ./scripts/deploy.sh
#
# Usage:
#   ./scripts/deploy.sh         # Build and deploy
#   ./scripts/deploy.sh --build # Build only, don't restart container
#   ./scripts/deploy.sh --help  # Show this help
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

# Configuration file
CONFIG_FILE="${SCRIPT_DIR}/deploy.conf"

# Defaults (can be overridden in deploy.conf)
CONTAINER_NAME="printarr"
IMAGE_NAME="printarr"
IMAGE_TAG="latest"
PORT="3333"
CONFIG_PATH="/mnt/user/appdata/printarr/config"
DATA_PATH="/mnt/user/appdata/printarr/data"
STAGING_PATH="/mnt/user/downloads/printarr-staging"
LIBRARY_PATH="/mnt/user/3d-library"
CACHE_PATH="/mnt/user/appdata/printarr/cache"
LOG_LEVEL="INFO"

# Telegram API credentials (required for v0.2+)
# Get these from https://my.telegram.org
TELEGRAM_API_ID=""
TELEGRAM_API_HASH=""

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_help() {
    head -25 "$0" | tail -20
    exit 0
}

# Parse arguments
BUILD_ONLY=false
for arg in "$@"; do
    case $arg in
        --build)
            BUILD_ONLY=true
            ;;
        --help|-h)
            show_help
            ;;
    esac
done

# Load configuration
if [[ -f "$CONFIG_FILE" ]]; then
    log_info "Loading configuration from $CONFIG_FILE"
    source "$CONFIG_FILE"
else
    log_warn "No deploy.conf found. Using defaults."
    log_warn "Copy scripts/deploy.conf.example to scripts/deploy.conf and customize."
fi

# Change to repo directory
cd "$REPO_DIR"

# Pull latest code
log_info "Pulling latest code from git..."
git pull

# Build Docker image
log_info "Building Docker image: ${IMAGE_NAME}:${IMAGE_TAG}"
docker build -t "${IMAGE_NAME}:${IMAGE_TAG}" .

if [[ "$BUILD_ONLY" == true ]]; then
    log_info "Build complete. Skipping deployment (--build flag)."
    exit 0
fi

# Create directories if they don't exist
log_info "Ensuring directories exist..."
mkdir -p "$CONFIG_PATH" "$DATA_PATH" "$STAGING_PATH" "$LIBRARY_PATH" "$CACHE_PATH"

# Stop existing container if running
if docker ps -q -f name="$CONTAINER_NAME" | grep -q .; then
    log_info "Stopping existing container: $CONTAINER_NAME"
    docker stop "$CONTAINER_NAME"
fi

# Remove existing container if exists
if docker ps -aq -f name="$CONTAINER_NAME" | grep -q .; then
    log_info "Removing existing container: $CONTAINER_NAME"
    docker rm "$CONTAINER_NAME"
fi

# Validate Telegram credentials
if [[ -z "$TELEGRAM_API_ID" || -z "$TELEGRAM_API_HASH" ]]; then
    log_error "TELEGRAM_API_ID and TELEGRAM_API_HASH are required!"
    log_error "Get these from https://my.telegram.org and set them in deploy.conf"
    exit 1
fi

# Start new container
log_info "Starting new container: $CONTAINER_NAME"
docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    -p "${PORT}:3333" \
    -v "${CONFIG_PATH}:/config" \
    -v "${DATA_PATH}:/data" \
    -v "${STAGING_PATH}:/staging" \
    -v "${LIBRARY_PATH}:/library" \
    -v "${CACHE_PATH}:/cache" \
    -e "PRINTARR_LOG_LEVEL=${LOG_LEVEL}" \
    -e "TELEGRAM_API_ID=${TELEGRAM_API_ID}" \
    -e "TELEGRAM_API_HASH=${TELEGRAM_API_HASH}" \
    "${IMAGE_NAME}:${IMAGE_TAG}"

# Wait for container to be healthy
log_info "Waiting for container to be healthy..."
sleep 5

# Check if container is running
if docker ps -q -f name="$CONTAINER_NAME" | grep -q .; then
    log_info "Container is running!"
    log_info "Access Printarr at: http://$(hostname -I | awk '{print $1}'):${PORT}"
else
    log_error "Container failed to start. Check logs with: docker logs $CONTAINER_NAME"
    exit 1
fi

log_info "Deployment complete!"

#!/bin/bash
# Printarr Deployment Script
# Handles Docker cleanup to prevent storage bloat from repeated rebuilds
#
# Usage:
#   ./deploy.sh              # Standard deploy (production mode)
#   ./deploy.sh --fast       # Fast deploy (use cache, no cleanup)
#   ./deploy.sh --pull       # Git pull latest code, then deploy
#   ./deploy.sh --clean      # Deep clean before deploy (removes build cache)
#   ./deploy.sh --prune-all  # Nuclear option: prune ALL unused Docker resources (CAREFUL!)
#   ./deploy.sh --logs       # Just show logs (no deploy)
#   ./deploy.sh --unraid     # Build for Unraid and push to GHCR

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
CLEAN_BUILD_CACHE=false
PRUNE_ALL=false
GIT_PULL=false
SHOW_LOGS=false
LOG_SERVICE=""
DEPLOY=true
FAST_MODE=false
UNRAID_BUILD=false
PUSH_GHCR=false
VERSION_TAG="latest"
UNRAID_RESET=false
UNRAID_CONFIG_DIR="/mnt/user/appdata/printarr"
CONTAINER_NAME="Printarr"

for arg in "$@"; do
    case $arg in
        --clean)
            CLEAN_BUILD_CACHE=true
            ;;
        --prune-all)
            PRUNE_ALL=true
            ;;
        --pull)
            GIT_PULL=true
            ;;
        --fast)
            FAST_MODE=true
            ;;
        --unraid)
            UNRAID_BUILD=true
            DEPLOY=false
            ;;
        --push)
            PUSH_GHCR=true
            ;;
        --tag=*)
            VERSION_TAG="${arg#*=}"
            ;;
        --reset)
            UNRAID_RESET=true
            ;;
        --config-dir=*)
            UNRAID_CONFIG_DIR="${arg#*=}"
            ;;
        --container=*)
            CONTAINER_NAME="${arg#*=}"
            ;;
        --logs)
            SHOW_LOGS=true
            DEPLOY=false
            ;;
        --logs=*)
            SHOW_LOGS=true
            DEPLOY=false
            LOG_SERVICE="${arg#*=}"
            ;;
        --help|-h)
            echo "Printarr Deployment Script"
            echo ""
            echo "Usage: ./deploy.sh [OPTIONS]"
            echo ""
            echo "Deployment Options:"
            echo "  --fast        Fast deploy: use Docker cache, skip cleanup"
            echo "                (use when no new dependencies were added)"
            echo "  --pull        Git pull latest code before deploying"
            echo "  --clean       Remove Docker build cache before building"
            echo "  --prune-all   Nuclear option: prune ALL unused Docker resources"
            echo "                WARNING: May affect other stopped containers!"
            echo ""
            echo "Unraid/GHCR Options:"
            echo "  --unraid            Build container for Unraid deployment"
            echo "  --push              Push to GitHub Container Registry (ghcr.io)"
            echo "  --tag=VERSION       Tag for the image (default: latest)"
            echo "                      Example: --tag=v1.0.0"
            echo "  --reset             Stop container, wipe database, restart fresh"
            echo "  --config-dir=PATH   Config directory (default: /mnt/user/appdata/printarr)"
            echo "  --container=NAME    Container name to reset (default: Printarr)"
            echo ""
            echo "Log Options (standalone, skips deployment):"
            echo "  --logs              Show logs (follow mode)"
            echo "  --logs=printarr     Show printarr logs only"
            echo "  --logs=flaresolverr Show flaresolverr logs only"
            echo ""
            echo "  -h, --help    Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./deploy.sh                 # Production deploy (default)"
            echo "  ./deploy.sh --fast          # Quick rebuild (code changes only)"
            echo "  ./deploy.sh --pull --fast   # Pull and quick rebuild"
            echo "  ./deploy.sh --pull          # Pull latest and full deploy"
            echo "  ./deploy.sh --pull --clean  # Pull, clean build cache, deploy"
            echo "  ./deploy.sh --logs          # Follow all logs (Ctrl+C to stop)"
            echo ""
            echo "Unraid Examples:"
            echo "  ./deploy.sh --unraid                    # Build container locally"
            echo "  ./deploy.sh --unraid --push             # Build and push to GHCR as :latest"
            echo "  ./deploy.sh --unraid --push --tag=v1.0.0   # Build and push with version tag"
            echo "  ./deploy.sh --pull --unraid --push      # Pull, build, and push"
            echo "  ./deploy.sh --reset                     # Stop, wipe DB, restart container"
            echo "  ./deploy.sh --pull --unraid --push --reset  # Full rebuild + fresh start"
            echo ""
            echo "What gets cleaned automatically (SAFE for other containers):"
            echo "  - Dangling images (untagged images from previous builds)"
            echo "  - Old Printarr images"
            echo ""
            echo "What --fast skips:"
            echo "  - Image cleanup (uses Docker layer cache)"
            echo "  - Volume renewal"
            echo "  - Disk usage report"
            echo ""
            echo "What --clean adds (SAFE):"
            echo "  - Docker build cache"
            echo ""
            echo "What --prune-all adds (DANGEROUS - affects ALL Docker):"
            echo "  - ALL unused images (not just dangling)"
            echo "  - ALL unused networks"
            echo "  - ALL unused volumes (may delete data from stopped containers!)"
            exit 0
            ;;
    esac
done

# Handle --logs mode (standalone, no deployment)
if [ "$SHOW_LOGS" = true ]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Printarr Logs${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "${YELLOW}Press Ctrl+C to stop following logs${NC}"
    echo ""

    if [ -n "$LOG_SERVICE" ]; then
        echo -e "Showing logs for: ${GREEN}$LOG_SERVICE${NC}"
        echo ""
        docker compose logs -f --tail=100 "$LOG_SERVICE"
    else
        echo -e "Showing logs for: ${GREEN}all services${NC}"
        echo ""
        docker compose logs -f --tail=50
    fi
    exit 0
fi

# Handle --unraid mode (container build for GHCR)
if [ "$UNRAID_BUILD" = true ]; then
    GHCR_REPO="ghcr.io/adama817/printarr"

    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Printarr Container Build${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "Tag: ${YELLOW}${VERSION_TAG}${NC}"
    if [ "$PUSH_GHCR" = true ]; then
        echo -e "Push to GHCR: ${GREEN}Yes${NC}"
    else
        echo -e "Push to GHCR: ${YELLOW}No (use --push to enable)${NC}"
    fi
    echo ""

    # Step 1: Git pull (optional)
    if [ "$GIT_PULL" = true ]; then
        echo -e "${YELLOW}[1/5] Pulling latest code from git...${NC}"
        git pull
        echo ""
    else
        echo -e "${YELLOW}[1/5] Skipping git pull (use --pull to enable)${NC}"
    fi

    # Step 2: Reset container and database (optional)
    if [ "$UNRAID_RESET" = true ]; then
        echo -e "${YELLOW}[2/5] Resetting Printarr container...${NC}"

        # Stop and remove container (case-insensitive search)
        FOUND_CONTAINER=$(docker ps -a --format '{{.Names}}' | grep -i "^${CONTAINER_NAME}$" | head -1)
        if [ -n "$FOUND_CONTAINER" ]; then
            echo -e "  Found container: ${FOUND_CONTAINER}"
            echo -e "  Stopping ${FOUND_CONTAINER}..."
            docker stop "$FOUND_CONTAINER" 2>/dev/null || true
            echo -e "  Removing ${FOUND_CONTAINER}..."
            docker rm "$FOUND_CONTAINER" 2>/dev/null || true
        else
            echo -e "  Container '${CONTAINER_NAME}' not found, skipping stop/remove"
            echo -e "  (Available containers: $(docker ps -a --format '{{.Names}}' | tr '\n' ' '))"
        fi

        # Wipe database (SQLite)
        if [ -f "${UNRAID_CONFIG_DIR}/config/printarr.db" ]; then
            echo -e "  ${RED}Wiping database at ${UNRAID_CONFIG_DIR}/config/printarr.db...${NC}"
            rm -f "${UNRAID_CONFIG_DIR}/config/printarr.db"
            rm -f "${UNRAID_CONFIG_DIR}/config/printarr.db-shm"
            rm -f "${UNRAID_CONFIG_DIR}/config/printarr.db-wal"
            echo -e "  Database wiped"
        else
            echo -e "  No database found at ${UNRAID_CONFIG_DIR}/config/printarr.db"
        fi

        # Optionally wipe Telegram session
        if [ -f "${UNRAID_CONFIG_DIR}/config/telegram.session" ]; then
            echo -e "  ${YELLOW}Telegram session found. Remove it? (y/N)${NC}"
            read -p "" -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                rm -f "${UNRAID_CONFIG_DIR}/config/telegram.session"
                echo -e "  Telegram session removed (you'll need to re-authenticate)"
            fi
        fi
        echo ""
    else
        echo -e "${YELLOW}[2/5] Skipping reset (use --reset to enable)${NC}"
    fi

    # Step 3: Build the image
    echo -e "${YELLOW}[3/5] Building container...${NC}"
    if [ "$FAST_MODE" = true ]; then
        docker build -t "${GHCR_REPO}:${VERSION_TAG}" .
    else
        docker build --no-cache -t "${GHCR_REPO}:${VERSION_TAG}" .
    fi
    echo ""

    # Step 4: Also tag as latest if using version tag
    if [ "$VERSION_TAG" != "latest" ]; then
        echo -e "${YELLOW}[4/5] Tagging as latest...${NC}"
        docker tag "${GHCR_REPO}:${VERSION_TAG}" "${GHCR_REPO}:latest"
        echo ""
    else
        echo -e "${YELLOW}[4/5] Already tagged as latest${NC}"
    fi

    # Step 5: Push to GHCR (optional)
    if [ "$PUSH_GHCR" = true ]; then
        echo -e "${YELLOW}[5/5] Pushing to GitHub Container Registry...${NC}"
        docker push "${GHCR_REPO}:${VERSION_TAG}"
        if [ "$VERSION_TAG" != "latest" ]; then
            docker push "${GHCR_REPO}:latest"
        fi
        echo ""
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}Build and Push Complete!${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo ""
        echo -e "Images pushed:"
        echo -e "  ${GREEN}${GHCR_REPO}:${VERSION_TAG}${NC}"
        if [ "$VERSION_TAG" != "latest" ]; then
            echo -e "  ${GREEN}${GHCR_REPO}:latest${NC}"
        fi
        echo ""
        echo -e "To deploy on Unraid:"
        echo -e "  1. Go to Docker tab"
        echo -e "  2. Click the Printarr container icon"
        echo -e "  3. Select 'Force Update'"
        echo -e ""
        echo -e "Or from Unraid terminal:"
        echo -e "  ${YELLOW}docker pull ${GHCR_REPO}:latest${NC}"
        echo -e "  ${YELLOW}docker stop Printarr && docker rm Printarr${NC}"
        echo -e "  Then recreate from template"
    else
        echo -e "${YELLOW}[5/5] Skipping push (use --push to enable)${NC}"
        echo ""
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}Build Complete!${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo ""
        echo -e "Local image: ${GREEN}${GHCR_REPO}:${VERSION_TAG}${NC}"
        echo ""
        echo -e "To push to GHCR, run:"
        echo -e "  ${YELLOW}docker push ${GHCR_REPO}:${VERSION_TAG}${NC}"
        if [ "$VERSION_TAG" != "latest" ]; then
            echo -e "  ${YELLOW}docker push ${GHCR_REPO}:latest${NC}"
        fi
    fi
    exit 0
fi

echo -e "${GREEN}========================================${NC}"
if [ "$FAST_MODE" = true ]; then
    echo -e "${GREEN}Printarr Fast Deployment${NC}"
else
    echo -e "${GREEN}Printarr Deployment${NC}"
fi
echo -e "${GREEN}========================================${NC}"
echo ""

# Step 0: Git pull (optional, before anything else so we fail fast if conflicts)
if [ "$GIT_PULL" = true ]; then
    echo -e "${YELLOW}[0/5] Pulling latest code from git...${NC}"
    git pull
    echo ""
fi

# Step 1: Stop existing containers
echo -e "${YELLOW}[1/5] Stopping existing containers...${NC}"
docker compose down --remove-orphans 2>/dev/null || true

# Fast mode skips cleanup steps 2-4
if [ "$FAST_MODE" = true ]; then
    echo -e "${YELLOW}[2-4] Skipping cleanup (--fast mode)${NC}"
else
    # Step 2: Clean up OLD Printarr images specifically (safe for other containers)
    echo -e "${YELLOW}[2/5] Cleaning old Printarr images...${NC}"
    # Remove previous printarr images
    for img in "printarr" "printarr_printarr"; do
        OLD_IMAGES=$(docker images --filter "reference=*${img}*" -q 2>/dev/null || true)
        if [ -n "$OLD_IMAGES" ]; then
            echo "$OLD_IMAGES" | xargs -r docker rmi -f 2>/dev/null || true
            echo -e "  Removed old ${img} image(s)"
        fi
    done

    # Also clean dangling images (safe - these are untagged/unused)
    DANGLING=$(docker images -f "dangling=true" -q 2>/dev/null | wc -l)
    if [ "$DANGLING" -gt 0 ]; then
        docker image prune -f
        echo -e "  Removed $DANGLING dangling image(s)"
    else
        echo -e "  No dangling images"
    fi

    # Step 3: Clean up anonymous volumes
    echo -e "${YELLOW}[3/5] Cleaning anonymous volumes...${NC}"
    echo -e "  Will be renewed with --renew-anon-volumes during startup"

    # Step 4: Optional deep clean
    if [ "$PRUNE_ALL" = true ]; then
        echo -e "${YELLOW}[4/5] Running full system prune (--prune-all)...${NC}"
        echo -e "${RED}WARNING: This removes ALL unused Docker resources!${NC}"
        echo -e "${RED}This may affect other stopped containers on this system!${NC}"
        read -p "Are you sure? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker system prune -af --volumes
        else
            echo -e "  Skipped"
        fi
    elif [ "$CLEAN_BUILD_CACHE" = true ]; then
        echo -e "${YELLOW}[4/5] Cleaning build cache (--clean)...${NC}"
        docker builder prune -f
    else
        echo -e "${YELLOW}[4/5] Skipping deep clean (use --clean or --prune-all if needed)${NC}"
    fi

    # Show space recovered
    echo ""
    echo -e "${YELLOW}Current Docker disk usage:${NC}"
    docker system df
fi

# Step 5: Build and start
echo ""
if [ "$FAST_MODE" = true ]; then
    echo -e "${YELLOW}[5/5] Building (cached) and starting containers...${NC}"
    docker compose build
    docker compose up -d --force-recreate
else
    echo -e "${YELLOW}[5/5] Building and starting containers...${NC}"
    docker compose build --no-cache
    docker compose up -d --force-recreate --renew-anon-volumes
fi

# Wait for health check
echo ""
echo -e "${YELLOW}Waiting for Printarr to start...${NC}"
sleep 10

# Check health
HEALTH=$(curl -s http://localhost:3333/api/health 2>/dev/null || echo '{"status":"starting"}')
VERSION=$(echo "$HEALTH" | grep -o '"version":"[^"]*"' | cut -d'"' -f4)
STATUS=$(echo "$HEALTH" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Version: ${BLUE}${VERSION:-unknown}${NC}"
echo -e "Status:  ${GREEN}${STATUS:-starting}${NC}"
echo ""
echo "Services:"
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
echo ""
echo -e "Access Printarr at: ${BLUE}http://localhost:3333${NC}"

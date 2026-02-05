#!/bin/bash
# Pre-deployment preflight checks for job-agent
# Run this before deploying to production

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PASS=0
FAIL=0
WARN=0

pass() {
  echo -e "${GREEN}✓${NC} $1"
  ((PASS++))
}

fail() {
  echo -e "${RED}✗${NC} $1"
  ((FAIL++))
}

warn() {
  echo -e "${YELLOW}!${NC} $1"
  ((WARN++))
}

info() {
  echo -e "${BLUE}ℹ${NC} $1"
}

# Change to project root
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

echo "========================================"
echo "     Pre-Deployment Preflight Check    "
echo "========================================"
echo ""
info "Project root: $PROJECT_ROOT"
echo ""

# ===========================================
# 1. Required Files Check
# ===========================================
echo "--- 1. Required Files ---"

REQUIRED_FILES=(
  "Dockerfile.frontend:Frontend Docker image"
  "frontend/app/api/health/route.ts:Frontend health endpoint"
  "scripts/grant-frontend-read-permissions.sql:Frontend DB permissions"
  "docker-compose.yml:Docker Compose configuration"
  "docker-compose.prod.yml:Production overrides"
  "Caddyfile:Reverse proxy configuration"
  "frontend/next.config.ts:Next.js configuration"
  "frontend/prisma/schema.prisma:Prisma schema"
)

for item in "${REQUIRED_FILES[@]}"; do
  file="${item%%:*}"
  desc="${item##*:}"
  if [ -f "$file" ]; then
    pass "$file ($desc)"
  else
    fail "$file MISSING ($desc)"
  fi
done

# ===========================================
# 2. Next.js Configuration Check
# ===========================================
echo ""
echo "--- 2. Next.js Configuration ---"

if [ -f "frontend/next.config.ts" ]; then
  if grep -q "output.*standalone" frontend/next.config.ts 2>/dev/null; then
    pass "Standalone output configured in next.config.ts"
  else
    fail "Missing 'output: standalone' in next.config.ts"
  fi
else
  fail "next.config.ts not found"
fi

# Check for health endpoint content
if [ -f "frontend/app/api/health/route.ts" ]; then
  if grep -q "healthy" frontend/app/api/health/route.ts 2>/dev/null; then
    pass "Health endpoint returns 'healthy' status"
  else
    warn "Health endpoint may not return expected response"
  fi
fi

# ===========================================
# 3. Environment Variables Check
# ===========================================
echo ""
echo "--- 3. Environment Variables ---"

if [ -f .env ]; then
  # Source .env file safely
  set -a
  source .env 2>/dev/null || true
  set +a
  
  # Required variables
  REQUIRED_VARS=(
    "POSTGRES_PASSWORD:Database admin password"
    "POSTGRES_UI_PASSWORD:Database UI user password"
    "BETTER_AUTH_SECRET:Authentication secret key"
    "BETTER_AUTH_GOOGLE_CLIENT_ID:Google OAuth client ID"
    "BETTER_AUTH_GOOGLE_CLIENT_SECRET:Google OAuth client secret"
    "UPLOADTHING_TOKEN:UploadThing file upload token"
    "JOB_LAND_API_KEY:Backend API key"
  )
  
  # Production-specific variables (warn if missing)
  PROD_VARS=(
    "FRONTEND_DOMAIN:Frontend domain (e.g., app.example.com)"
    "API_DOMAIN:API domain (e.g., api.example.com)"
    "APEX_DOMAIN:Apex domain for redirect (e.g., example.com)"
    "CORS_ORIGINS:CORS allowed origins"
  )
  
  for item in "${REQUIRED_VARS[@]}"; do
    var="${item%%:*}"
    desc="${item##*:}"
    if [ -n "${!var}" ]; then
      pass "$var is set ($desc)"
    else
      fail "$var is NOT SET ($desc)"
    fi
  done
  
  echo ""
  info "Production-specific variables:"
  for item in "${PROD_VARS[@]}"; do
    var="${item%%:*}"
    desc="${item##*:}"
    if [ -n "${!var}" ]; then
      pass "$var is set ($desc)"
    else
      warn "$var is not set ($desc) - Required for production"
    fi
  done
else
  fail ".env file not found - copy from .env.example"
fi

# ===========================================
# 4. Docker Compose Validation
# ===========================================
echo ""
echo "--- 4. Docker Compose Validation ---"

# Check if docker is available
if command -v docker &> /dev/null; then
  # Validate base compose file
  if docker compose -f docker-compose.yml config --quiet 2>/dev/null; then
    pass "docker-compose.yml is valid"
  else
    fail "docker-compose.yml has syntax errors"
  fi
  
  # Validate prod overlay
  if docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet 2>/dev/null; then
    pass "docker-compose.prod.yml overlay is valid"
  else
    fail "docker-compose.prod.yml has syntax errors"
  fi
  
  # Check if frontend service exists
  if docker compose -f docker-compose.yml config 2>/dev/null | grep -q "frontend:"; then
    pass "Frontend service defined in docker-compose.yml"
  else
    fail "Frontend service MISSING in docker-compose.yml"
  fi
else
  warn "Docker not found - skipping compose validation"
fi

# ===========================================
# 5. Caddyfile Check
# ===========================================
echo ""
echo "--- 5. Caddyfile Configuration ---"

if [ -f "Caddyfile" ]; then
  # Check for frontend routing
  if grep -q "frontend:3000" Caddyfile 2>/dev/null; then
    pass "Frontend reverse proxy configured"
  else
    fail "Frontend routing MISSING in Caddyfile"
  fi
  
  # Check for API routing
  if grep -q "api:8000" Caddyfile 2>/dev/null; then
    pass "API reverse proxy configured"
  else
    fail "API routing MISSING in Caddyfile"
  fi
  
  # Check for domain variables
  if grep -q '\$FRONTEND_DOMAIN' Caddyfile 2>/dev/null || grep -q '{$FRONTEND_DOMAIN}' Caddyfile 2>/dev/null; then
    pass "Frontend domain variable used"
  else
    warn "Consider using FRONTEND_DOMAIN variable in Caddyfile"
  fi
else
  fail "Caddyfile not found"
fi

# ===========================================
# 6. Security Checks
# ===========================================
echo ""
echo "--- 6. Security Checks ---"

# Check .env is gitignored
if grep -q "^\.env$" .gitignore 2>/dev/null || grep -q "^\.env\s" .gitignore 2>/dev/null; then
  pass ".env is in .gitignore"
else
  fail ".env might not be gitignored - SECURITY RISK"
fi

# Check BETTER_AUTH_SECRET length
if [ -n "$BETTER_AUTH_SECRET" ]; then
  SECRET_LENGTH=${#BETTER_AUTH_SECRET}
  if [ $SECRET_LENGTH -ge 32 ]; then
    pass "BETTER_AUTH_SECRET length is sufficient ($SECRET_LENGTH chars)"
  else
    fail "BETTER_AUTH_SECRET should be at least 32 characters (current: $SECRET_LENGTH)"
  fi
fi

# Check passwords are different
if [ -n "$POSTGRES_PASSWORD" ] && [ -n "$POSTGRES_UI_PASSWORD" ]; then
  if [ "$POSTGRES_PASSWORD" != "$POSTGRES_UI_PASSWORD" ]; then
    pass "Database passwords are different"
  else
    fail "POSTGRES_PASSWORD and POSTGRES_UI_PASSWORD should be different"
  fi
fi

# Check for common weak passwords
WEAK_PASSWORDS=("password" "123456" "admin" "postgres" "secret")
if [ -n "$POSTGRES_PASSWORD" ]; then
  WEAK=false
  for weak in "${WEAK_PASSWORDS[@]}"; do
    if [ "$POSTGRES_PASSWORD" = "$weak" ]; then
      WEAK=true
      break
    fi
  done
  if [ "$WEAK" = true ]; then
    fail "POSTGRES_PASSWORD appears to be a weak password"
  else
    pass "POSTGRES_PASSWORD does not match common weak passwords"
  fi
fi

# ===========================================
# 7. Frontend Dependencies
# ===========================================
echo ""
echo "--- 7. Frontend Dependencies ---"

if [ -f "frontend/package-lock.json" ]; then
  pass "package-lock.json exists"
else
  warn "package-lock.json missing - run 'npm install' in frontend/"
fi

if [ -d "frontend/node_modules" ]; then
  pass "node_modules directory exists"
else
  warn "node_modules missing - run 'npm install' in frontend/"
fi

# ===========================================
# 8. Git Status Check
# ===========================================
echo ""
echo "--- 8. Git Status ---"

if command -v git &> /dev/null && [ -d ".git" ]; then
  # Check for uncommitted changes
  if git diff --quiet 2>/dev/null && git diff --staged --quiet 2>/dev/null; then
    pass "No uncommitted changes"
  else
    warn "Uncommitted changes detected - consider committing before deploy"
  fi
  
  # Check for untracked files in critical directories
  UNTRACKED=$(git status --porcelain 2>/dev/null | grep "^??" | grep -E "(Dockerfile|docker-compose|Caddyfile)" || true)
  if [ -n "$UNTRACKED" ]; then
    warn "Untracked deployment files detected - consider adding to git"
  fi
else
  info "Not a git repository - skipping git checks"
fi

# ===========================================
# Summary
# ===========================================
echo ""
echo "========================================"
echo "             SUMMARY                    "
echo "========================================"
echo -e "${GREEN}Passed:${NC}   $PASS"
echo -e "${RED}Failed:${NC}   $FAIL"
echo -e "${YELLOW}Warnings:${NC} $WARN"
echo ""

if [ $FAIL -gt 0 ]; then
  echo -e "${RED}╔════════════════════════════════════════╗${NC}"
  echo -e "${RED}║   PREFLIGHT FAILED - Fix issues above  ║${NC}"
  echo -e "${RED}╚════════════════════════════════════════╝${NC}"
  exit 1
elif [ $WARN -gt 0 ]; then
  echo -e "${YELLOW}╔════════════════════════════════════════════════════╗${NC}"
  echo -e "${YELLOW}║   PREFLIGHT PASSED with WARNINGS - Review above    ║${NC}"
  echo -e "${YELLOW}╚════════════════════════════════════════════════════╝${NC}"
  exit 0
else
  echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
  echo -e "${GREEN}║   PREFLIGHT PASSED - Ready to deploy   ║${NC}"
  echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
  exit 0
fi

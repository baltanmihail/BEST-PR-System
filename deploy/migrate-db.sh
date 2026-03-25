#!/bin/bash
set -e

echo "=== BEST PR System — Database Migration from Railway ==="
echo ""
echo "This script imports a Railway PostgreSQL dump into the local Docker PostgreSQL."
echo ""

PROJECT_DIR="/home/misha_b/best-pr-system"
cd "$PROJECT_DIR"

# Load .env to get local DB credentials
source .env

DUMP_FILE="${1:-railway_dump.sql}"

if [ ! -f "$DUMP_FILE" ]; then
    echo "Usage: $0 <dump_file.sql>"
    echo ""
    echo "How to get the dump from Railway:"
    echo "  Option A (Railway CLI):"
    echo "    railway run pg_dump -Fc > railway_dump.sql"
    echo ""
    echo "  Option B (Direct connection string from Railway dashboard):"
    echo "    pg_dump 'postgresql://USER:PASS@HOST:PORT/DB' -Fc > railway_dump.sql"
    echo ""
    echo "  Option C (Railway web console -> Database -> Connect -> copy connection string):"
    echo "    PGPASSWORD=xxx pg_dump -h HOST -p PORT -U USER -d DB -Fc > railway_dump.sql"
    echo ""
    echo "Then upload to server: scp railway_dump.sql misha_b@192.144.12.196:~/best-pr-system/"
    exit 1
fi

echo "[1/3] Stopping backend to prevent writes..."
docker compose stop backend || true

echo "[2/3] Restoring database from $DUMP_FILE..."
# Copy dump into postgres container
docker cp "$DUMP_FILE" best_pr_postgres:/tmp/dump.sql

# Drop and recreate database
docker compose exec -T postgres psql -U "${POSTGRES_USER:-best_pr_user}" -c "DROP DATABASE IF EXISTS ${POSTGRES_DB:-best_pr_system};"
docker compose exec -T postgres psql -U "${POSTGRES_USER:-best_pr_user}" -c "CREATE DATABASE ${POSTGRES_DB:-best_pr_system};"

# Detect format and restore
if file "$DUMP_FILE" | grep -q "text"; then
    docker compose exec -T postgres psql -U "${POSTGRES_USER:-best_pr_user}" -d "${POSTGRES_DB:-best_pr_system}" < "$DUMP_FILE"
else
    docker compose exec -T postgres pg_restore -U "${POSTGRES_USER:-best_pr_user}" -d "${POSTGRES_DB:-best_pr_system}" --no-owner --no-acl /tmp/dump.sql || true
fi

echo "[3/3] Starting backend..."
docker compose start backend

echo ""
echo "=== Database migration complete! ==="
echo "Verify: docker compose exec postgres psql -U ${POSTGRES_USER:-best_pr_user} -d ${POSTGRES_DB:-best_pr_system} -c 'SELECT count(*) FROM users;'"

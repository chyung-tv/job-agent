#!/usr/bin/env bash
# Create job_agent_admin and job_agent_ui with schema and default privileges.
# Runs once when Postgres data dir is empty (docker-entrypoint-initdb.d).
# Requires: POSTGRES_ADMIN_PASSWORD, POSTGRES_UI_PASSWORD, POSTGRES_DB (from postgres image).
set -e

# Escape single quotes in passwords for use inside SQL single-quoted strings
ADMIN_PASS="${POSTGRES_ADMIN_PASSWORD:-}"
UI_PASS="${POSTGRES_UI_PASSWORD:-}"
ADMIN_PASS_ESCAPED="${ADMIN_PASS//\'/\'\'}"
UI_PASS_ESCAPED="${UI_PASS//\'/\'\'}"

DB="${POSTGRES_DB:-job_agent}"

psql -v ON_ERROR_STOP=1 -U postgres -d "$DB" <<EOSQL
-- Backend/Alembic user: full privileges on public schema
CREATE ROLE job_agent_admin WITH LOGIN PASSWORD '${ADMIN_PASS_ESCAPED}';
-- Frontend user (Phase 2): SELECT, INSERT, UPDATE only; no DDL
CREATE ROLE job_agent_ui WITH LOGIN PASSWORD '${UI_PASS_ESCAPED}';

-- Schema: admin gets all; UI gets usage only. Admin owns public so it can DROP/CREATE SCHEMA in reset_db.
GRANT ALL ON SCHEMA public TO job_agent_admin;
GRANT USAGE ON SCHEMA public TO job_agent_ui;
ALTER SCHEMA public OWNER TO job_agent_admin;
-- So admin can CREATE SCHEMA public after DROP in ./setup.sh --overwrite
GRANT CREATE ON DATABASE "$DB" TO job_agent_admin;

-- Future tables/sequences created by job_agent_admin get these grants for job_agent_ui
ALTER DEFAULT PRIVILEGES FOR ROLE job_agent_admin IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE ON TABLES TO job_agent_ui;
ALTER DEFAULT PRIVILEGES FOR ROLE job_agent_admin IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO job_agent_ui;
EOSQL

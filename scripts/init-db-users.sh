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
-- Create roles if they don't exist, or alter password if they do
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'job_agent_admin') THEN
    CREATE ROLE job_agent_admin WITH LOGIN PASSWORD '${ADMIN_PASS_ESCAPED}';
  ELSE
    ALTER ROLE job_agent_admin WITH PASSWORD '${ADMIN_PASS_ESCAPED}';
  END IF;
  
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'job_agent_ui') THEN
    CREATE ROLE job_agent_ui WITH LOGIN PASSWORD '${UI_PASS_ESCAPED}';
  ELSE
    ALTER ROLE job_agent_ui WITH PASSWORD '${UI_PASS_ESCAPED}';
  END IF;
END \$\$;

-- Schema: admin gets all; UI gets usage only. Admin owns public so it can DROP/CREATE SCHEMA in reset_db.
GRANT ALL ON SCHEMA public TO job_agent_admin;
GRANT USAGE ON SCHEMA public TO job_agent_ui;
ALTER SCHEMA public OWNER TO job_agent_admin;
-- So admin can CREATE SCHEMA public after DROP in ./setup.sh --overwrite
GRANT CREATE ON DATABASE "$DB" TO job_agent_admin;

-- Future tables/sequences created by job_agent_admin get these grants for job_agent_ui
ALTER DEFAULT PRIVILEGES FOR ROLE job_agent_admin IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO job_agent_ui;
ALTER DEFAULT PRIVILEGES FOR ROLE job_agent_admin IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO job_agent_ui;

-- Explicit grants on Better Auth tables (if they exist - will be created by migrations)
-- These grants will fail gracefully if tables don't exist yet, which is fine
DO \$\$
BEGIN
  IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'user') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.user TO job_agent_ui;
  END IF;
  IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'session') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.session TO job_agent_ui;
  END IF;
  IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'account') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.account TO job_agent_ui;
  END IF;
  IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'verification') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.verification TO job_agent_ui;
  END IF;
END \$\$;
EOSQL

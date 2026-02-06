-- One-time script for existing DBs (volume already has data; init-db-users.sh did not run).
-- Run as postgres once, e.g.:
--   psql -v admin_pass='YOUR_ADMIN_PASSWORD' -v ui_pass='YOUR_UI_PASSWORD' -d job_agent -f scripts/grant-two-users-existing-db.sql
-- Escape single quotes in passwords by doubling them (''). If roles already exist, skip or drop them first.

\set ON_ERROR_STOP on

-- Create roles if they don't exist, or alter password if they do
-- Set session variables for the DO block to access
SELECT set_config('var.admin_pass', :'admin_pass', true);
SELECT set_config('var.ui_pass', :'ui_pass', true);

DO $$
DECLARE
  v_admin_pass text := current_setting('var.admin_pass');
  v_ui_pass text := current_setting('var.ui_pass');
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'job_agent_admin') THEN
    EXECUTE format('CREATE ROLE job_agent_admin WITH LOGIN PASSWORD %L', v_admin_pass);
  ELSE
    EXECUTE format('ALTER ROLE job_agent_admin WITH PASSWORD %L', v_admin_pass);
  END IF;
  
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'job_agent_ui') THEN
    EXECUTE format('CREATE ROLE job_agent_ui WITH LOGIN PASSWORD %L', v_ui_pass);
  ELSE
    EXECUTE format('ALTER ROLE job_agent_ui WITH PASSWORD %L', v_ui_pass);
  END IF;
END $$;

GRANT ALL ON SCHEMA public TO job_agent_admin;
GRANT USAGE ON SCHEMA public TO job_agent_ui;
-- Admin owns public so it can DROP/CREATE SCHEMA in reset_db (./setup.sh --overwrite).
ALTER SCHEMA public OWNER TO job_agent_admin;
-- So admin can CREATE SCHEMA public after DROP. (If POSTGRES_DB differs, change DB name here.)
GRANT CREATE ON DATABASE job_agent TO job_agent_admin;

-- Explicit grants on Better Auth tables only (idempotent - uses IF EXISTS)
DO $$
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
END $$;

-- Sequences (for Better Auth tables that use sequences)
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO job_agent_ui;

-- Future objects created by job_agent_admin
ALTER DEFAULT PRIVILEGES FOR ROLE job_agent_admin IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO job_agent_ui;
ALTER DEFAULT PRIVILEGES FOR ROLE job_agent_admin IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO job_agent_ui;

-- One-time script for existing DBs (volume already has data; init-db-users.sh did not run).
-- Run as postgres once, e.g.:
--   psql -v admin_pass='YOUR_ADMIN_PASSWORD' -v ui_pass='YOUR_UI_PASSWORD' -d job_agent -f scripts/grant-two-users-existing-db.sql
-- Escape single quotes in passwords by doubling them (''). If roles already exist, skip or drop them first.

\set ON_ERROR_STOP on

CREATE ROLE job_agent_admin WITH LOGIN PASSWORD :'admin_pass';
CREATE ROLE job_agent_ui WITH LOGIN PASSWORD :'ui_pass';

GRANT ALL ON SCHEMA public TO job_agent_admin;
GRANT USAGE ON SCHEMA public TO job_agent_ui;
-- Admin owns public so it can DROP/CREATE SCHEMA in reset_db (./setup.sh --overwrite).
ALTER SCHEMA public OWNER TO job_agent_admin;
-- So admin can CREATE SCHEMA public after DROP. (If POSTGRES_DB differs, change DB name here.)
GRANT CREATE ON DATABASE job_agent TO job_agent_admin;

-- Existing tables and sequences (created by postgres or previous admin)
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO job_agent_ui;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO job_agent_ui;

-- Future objects created by job_agent_admin
ALTER DEFAULT PRIVILEGES FOR ROLE job_agent_admin IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE ON TABLES TO job_agent_ui;
ALTER DEFAULT PRIVILEGES FOR ROLE job_agent_admin IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO job_agent_ui;

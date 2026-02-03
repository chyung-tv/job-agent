-- Grant permissions on Better Auth tables to job_agent_ui
-- Idempotent: safe to run multiple times
-- Run this after migrations to ensure Better Auth tables have proper permissions

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

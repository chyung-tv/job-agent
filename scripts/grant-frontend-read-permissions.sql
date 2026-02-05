-- Grant SELECT on backend tables to job_agent_ui (frontend)
-- Run after migrations create these tables

DO $$
BEGIN
  IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'job_searches') THEN
    GRANT SELECT ON TABLE public.job_searches TO job_agent_ui;
  END IF;
  IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'runs') THEN
    GRANT SELECT ON TABLE public.runs TO job_agent_ui;
  END IF;
  IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'matched_jobs') THEN
    GRANT SELECT ON TABLE public.matched_jobs TO job_agent_ui;
  END IF;
  IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'job_postings') THEN
    GRANT SELECT ON TABLE public.job_postings TO job_agent_ui;
  END IF;
  IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'artifacts') THEN
    GRANT SELECT ON TABLE public.artifacts TO job_agent_ui;
  END IF;
  IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'company_research') THEN
    GRANT SELECT ON TABLE public.company_research TO job_agent_ui;
  END IF;
END $$;

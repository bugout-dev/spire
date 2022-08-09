CREATE TABLE public.github_checks (
    id uuid NOT NULL,
    issue_pr_id uuid NOT NULL,
    repo_id uuid NOT NULL,
    event_id uuid NOT NULL,
    github_check_name character varying NOT NULL,
    github_status character varying,
    github_conclusion character varying,
    github_check_id character varying NOT NULL
);

ALTER TABLE ONLY public.github_checks
    ADD CONSTRAINT pk_github_checks PRIMARY KEY (id);

ALTER TABLE ONLY public.github_checks
    ADD CONSTRAINT uq_github_checks_id UNIQUE (id);

ALTER TABLE ONLY public.github_checks
    ADD CONSTRAINT fk_github_checks_event_id_github_oauth_events FOREIGN KEY (event_id) REFERENCES public.github_oauth_events(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.github_checks
    ADD CONSTRAINT fk_github_checks_issue_pr_id_github_issues_prs FOREIGN KEY (issue_pr_id) REFERENCES public.github_issues_prs(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.github_checks
    ADD CONSTRAINT fk_github_checks_repo_id_github_repos FOREIGN KEY (repo_id) REFERENCES public.github_repos(id) ON DELETE CASCADE;

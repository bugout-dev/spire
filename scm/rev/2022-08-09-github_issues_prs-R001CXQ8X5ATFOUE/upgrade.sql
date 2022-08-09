CREATE TABLE public.github_issues_prs (
    id uuid NOT NULL,
    repo_id uuid NOT NULL,
    event_id uuid NOT NULL,
    comments_url character varying,
    terminal_hash character varying,
    branch character varying,
    entry_id character varying
);

ALTER TABLE ONLY public.github_issues_prs
    ADD CONSTRAINT pk_github_issues_prs PRIMARY KEY (id);

ALTER TABLE ONLY public.github_issues_prs
    ADD CONSTRAINT uq_github_issues_prs_id UNIQUE (id);

ALTER TABLE ONLY public.github_issues_prs
    ADD CONSTRAINT fk_github_issues_prs_event_id_github_oauth_events FOREIGN KEY (event_id) REFERENCES public.github_oauth_events(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.github_issues_prs
    ADD CONSTRAINT fk_github_issues_prs_repo_id_github_repos FOREIGN KEY (repo_id) REFERENCES public.github_repos(id) ON DELETE CASCADE;

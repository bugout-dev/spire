CREATE TABLE public.github_repos (
    id uuid NOT NULL,
    event_id uuid NOT NULL,
    github_repo_id integer NOT NULL,
    github_repo_name character varying NOT NULL,
    github_repo_url character varying NOT NULL,
    private boolean NOT NULL,
    default_branch character varying NOT NULL
);

ALTER TABLE ONLY public.github_repos
    ADD CONSTRAINT pk_github_repos PRIMARY KEY (id);

ALTER TABLE ONLY public.github_repos
    ADD CONSTRAINT uq_github_repos_id UNIQUE (id);

ALTER TABLE ONLY public.github_repos
    ADD CONSTRAINT fk_github_repos_event_id_github_oauth_events FOREIGN KEY (event_id) REFERENCES public.github_oauth_events(id) ON DELETE CASCADE;

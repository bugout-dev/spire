CREATE TABLE public.github_oauth_events (
    id uuid NOT NULL,
    access_code character varying,
    access_token character varying,
    access_token_expire_ts timestamp with time zone,
    deleted boolean NOT NULL,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL,
    github_account_id integer NOT NULL,
    github_installation_id integer NOT NULL,
    github_installation_url character varying NOT NULL
);

ALTER TABLE ONLY public.github_oauth_events
    ADD CONSTRAINT pk_github_oauth_events PRIMARY KEY (id);

ALTER TABLE ONLY public.github_oauth_events
    ADD CONSTRAINT uq_github_oauth_events_github_account_id UNIQUE (github_account_id);

ALTER TABLE ONLY public.github_oauth_events
    ADD CONSTRAINT uq_github_oauth_events_github_installation_id UNIQUE (github_installation_id);

ALTER TABLE ONLY public.github_oauth_events
    ADD CONSTRAINT uq_github_oauth_events_github_installation_url UNIQUE (github_installation_url);

ALTER TABLE ONLY public.github_oauth_events
    ADD CONSTRAINT uq_github_oauth_events_id UNIQUE (id);

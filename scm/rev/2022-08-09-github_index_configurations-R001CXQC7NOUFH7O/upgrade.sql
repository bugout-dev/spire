CREATE TABLE public.github_index_configurations (
    github_oauth_event_id uuid NOT NULL,
    index_name character varying NOT NULL,
    index_url character varying NOT NULL,
    description character varying,
    use_bugout_auth boolean NOT NULL,
    use_bugout_client_id boolean NOT NULL,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL
);

ALTER TABLE ONLY public.github_index_configurations
    ADD CONSTRAINT pk_github_index_configurations PRIMARY KEY (github_oauth_event_id, index_name);

ALTER TABLE ONLY public.github_index_configurations
    ADD CONSTRAINT fk_github_index_configurations_github_oauth_event_id_gi_6103 FOREIGN KEY (github_oauth_event_id) REFERENCES public.github_oauth_events(id) ON DELETE CASCADE;

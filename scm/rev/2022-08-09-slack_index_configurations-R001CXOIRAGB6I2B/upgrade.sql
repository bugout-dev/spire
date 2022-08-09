CREATE TABLE public.slack_index_configurations (
    slack_oauth_event_id uuid NOT NULL,
    index_name character varying NOT NULL,
    index_url character varying NOT NULL,
    use_bugout_auth boolean NOT NULL,
    use_bugout_client_id boolean NOT NULL,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL,
    description character varying
);

ALTER TABLE ONLY public.slack_index_configurations
    ADD CONSTRAINT pk_slack_index_configurations PRIMARY KEY (slack_oauth_event_id, index_name);

ALTER TABLE ONLY public.slack_index_configurations
    ADD CONSTRAINT fk_slack_bugout_users_slack_oauth_events_id FOREIGN KEY (slack_oauth_event_id) REFERENCES public.slack_oauth_events(id) ON DELETE CASCADE;

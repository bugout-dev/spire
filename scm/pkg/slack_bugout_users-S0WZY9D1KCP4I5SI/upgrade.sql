CREATE TABLE public.slack_bugout_users (
    id uuid NOT NULL,
    slack_oauth_event_id uuid,
    bugout_user_id character varying NOT NULL,
    bugout_access_token character varying,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL,
    bugout_group_id character varying
);

ALTER TABLE ONLY public.slack_bugout_users
    ADD CONSTRAINT slack_bugout_users_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.slack_bugout_users
    ADD CONSTRAINT uq_slack_bugout_users_id UNIQUE (id);

ALTER TABLE ONLY public.slack_bugout_users
    ADD CONSTRAINT fk_slack_bugout_users_slack_oauth_events_id FOREIGN KEY (slack_oauth_event_id) REFERENCES public.slack_oauth_events(id) ON DELETE CASCADE;

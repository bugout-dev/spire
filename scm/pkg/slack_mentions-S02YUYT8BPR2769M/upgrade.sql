CREATE TABLE public.slack_mentions (
    id uuid NOT NULL,
    slack_oauth_event_id uuid,
    team_id character varying NOT NULL,
    user_id character varying NOT NULL,
    thread_ts character varying,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL,
    channel_id character varying NOT NULL,
    invocation character varying NOT NULL,
    responded boolean
);

ALTER TABLE ONLY public.slack_mentions
    ADD CONSTRAINT slack_mentions_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.slack_mentions
    ADD CONSTRAINT uq_slack_mentions_id UNIQUE (id);

ALTER TABLE ONLY public.slack_mentions
    ADD CONSTRAINT fk_slack_mentions_slack_oauth_events_id FOREIGN KEY (slack_oauth_event_id) REFERENCES public.slack_oauth_events(id) ON DELETE CASCADE;

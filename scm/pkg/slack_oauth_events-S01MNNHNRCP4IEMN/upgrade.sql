CREATE TABLE public.slack_oauth_events (
    id uuid NOT NULL,
    bot_access_token character varying NOT NULL,
    team_id character varying NOT NULL,
    team_name character varying,
    enterprise_id character varying,
    enterprise_name character varying,
    user_access_token character varying,
    authed_user_id character varying,
    authed_user_scope character varying,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL,
    bot_scope character varying NOT NULL,
    bot_user_id character varying NOT NULL,
    version integer NOT NULL,
    deleted boolean
);

ALTER TABLE ONLY public.slack_oauth_events
    ADD CONSTRAINT slack_oauth_events_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.slack_oauth_events
    ADD CONSTRAINT uq_slack_oauth_events_id UNIQUE (id);

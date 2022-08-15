CREATE TABLE public.github_bugout_users (
    id uuid NOT NULL,
    event_id uuid,
    bugout_user_id character varying NOT NULL,
    bugout_access_token character varying,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL,
    bugout_group_id character varying
);

ALTER TABLE ONLY public.github_bugout_users
    ADD CONSTRAINT pk_github_bugout_users PRIMARY KEY (id);

ALTER TABLE ONLY public.github_bugout_users
    ADD CONSTRAINT fk_github_bugout_users_event_id_github_oauth_events FOREIGN KEY (event_id) REFERENCES public.github_oauth_events(id) ON DELETE CASCADE;

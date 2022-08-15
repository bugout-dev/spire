CREATE TABLE public.humbug_bugout_user_tokens (
    restricted_token_id uuid NOT NULL,
    event_id uuid,
    user_id uuid,
    app_name character varying NOT NULL,
    app_version character varying NOT NULL,
    store_ip boolean NOT NULL
);

ALTER TABLE ONLY public.humbug_bugout_user_tokens
    ADD CONSTRAINT pk_humbug_bugout_user_tokens PRIMARY KEY (restricted_token_id);

ALTER TABLE ONLY public.humbug_bugout_user_tokens
    ADD CONSTRAINT fk_humbug_bugout_user_tokens_event_id_humbug_events FOREIGN KEY (event_id) REFERENCES public.humbug_events(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.humbug_bugout_user_tokens
    ADD CONSTRAINT fk_humbug_bugout_user_tokens_user_id_humbug_bugout_users FOREIGN KEY (user_id) REFERENCES public.humbug_bugout_users(user_id) ON DELETE CASCADE;


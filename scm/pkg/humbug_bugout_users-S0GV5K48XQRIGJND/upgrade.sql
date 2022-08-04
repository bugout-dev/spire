CREATE TABLE public.humbug_bugout_users (
    user_id uuid NOT NULL,
    access_token_id uuid,
    event_id uuid,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL
);

ALTER TABLE ONLY public.humbug_bugout_users
    ADD CONSTRAINT pk_humbug_bugout_users PRIMARY KEY (user_id);

ALTER TABLE ONLY public.humbug_bugout_users
    ADD CONSTRAINT uq_humbug_bugout_users_event_id UNIQUE (event_id, user_id);

ALTER TABLE ONLY public.humbug_bugout_users
    ADD CONSTRAINT fk_humbug_bugout_users_event_id_humbug_events FOREIGN KEY (event_id) REFERENCES public.humbug_events(id) ON DELETE CASCADE;

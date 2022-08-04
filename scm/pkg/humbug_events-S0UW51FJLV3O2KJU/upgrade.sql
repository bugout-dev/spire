CREATE TABLE public.humbug_events (
    id uuid NOT NULL,
    group_id uuid NOT NULL,
    journal_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL
);

ALTER TABLE ONLY public.humbug_events
    ADD CONSTRAINT pk_humbug_events PRIMARY KEY (id);

ALTER TABLE ONLY public.humbug_events
    ADD CONSTRAINT uq_humbug_events_group_id UNIQUE (group_id, journal_id);

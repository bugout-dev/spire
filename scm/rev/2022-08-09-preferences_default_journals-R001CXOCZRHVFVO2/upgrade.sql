CREATE TABLE public.preferences_default_journals (
    user_id character varying NOT NULL,
    journal_id character varying NOT NULL,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL
);

ALTER TABLE ONLY public.preferences_default_journals
    ADD CONSTRAINT pk_preferences_default_journals PRIMARY KEY (user_id);

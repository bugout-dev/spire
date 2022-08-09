CREATE TABLE public.permalink_journal_entries (
    entry_id uuid NOT NULL,
    journal_id uuid NOT NULL,
    permalink character varying NOT NULL,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL
);

ALTER TABLE ONLY public.permalink_journal_entries
    ADD CONSTRAINT pk_permalink_journal_entries PRIMARY KEY (entry_id);

ALTER TABLE ONLY public.permalink_journal_entries
    ADD CONSTRAINT uq_permalink_journal_entries_journal_id UNIQUE (journal_id, permalink);

ALTER TABLE ONLY public.permalink_journal_entries
    ADD CONSTRAINT uq_permalink_journal_entries_permalink UNIQUE (permalink);

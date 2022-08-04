CREATE TABLE public.journal_entries (
    id uuid NOT NULL,
    journal_id uuid,
    content character varying NOT NULL,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL,
    version_id integer NOT NULL,
    title character varying,
    context_id character varying,
    context_type character varying DEFAULT 'bugout'::character varying NOT NULL,
    context_url character varying
);

ALTER TABLE ONLY public.journal_entries
    ADD CONSTRAINT journal_entries_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.journal_entries
    ADD CONSTRAINT uq_journal_entries_id UNIQUE (id);

CREATE INDEX ix_journal_entries_created_at ON public.journal_entries USING btree (created_at);

CREATE INDEX ix_journal_entries_journal_id_created_at ON public.journal_entries USING btree (journal_id, created_at);

CREATE INDEX ix_journal_entries_updated_at ON public.journal_entries USING btree (updated_at);

ALTER TABLE ONLY public.journal_entries
    ADD CONSTRAINT fk_journal_entries_journals_id FOREIGN KEY (journal_id) REFERENCES public.journals(id) ON DELETE CASCADE;

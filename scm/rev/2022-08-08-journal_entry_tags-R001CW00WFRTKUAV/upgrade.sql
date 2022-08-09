CREATE TABLE public.journal_entry_tags (
    id uuid NOT NULL,
    journal_entry_id uuid,
    tag character varying NOT NULL,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL
);

ALTER TABLE ONLY public.journal_entry_tags
    ADD CONSTRAINT journal_entry_tags_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.journal_entry_tags
    ADD CONSTRAINT uc_journal_entry_tags_journal_entry_id_tag UNIQUE (journal_entry_id, tag);

ALTER TABLE ONLY public.journal_entry_tags
    ADD CONSTRAINT uq_journal_entry_tags_id UNIQUE (id);

ALTER TABLE ONLY public.journal_entry_tags
    ADD CONSTRAINT fk_journal_entry_tags_journal_entries_id FOREIGN KEY (journal_entry_id) REFERENCES public.journal_entries(id) ON DELETE CASCADE;

CREATE INDEX ix_journal_entry_tags_tag ON public.journal_entry_tags USING btree (tag);

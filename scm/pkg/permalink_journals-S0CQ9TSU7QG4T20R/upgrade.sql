CREATE TABLE public.permalink_journals (
    journal_id uuid NOT NULL,
    permalink character varying NOT NULL,
    public boolean NOT NULL,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL
);

ALTER TABLE ONLY public.permalink_journals
    ADD CONSTRAINT pk_permalink_journals PRIMARY KEY (journal_id);

ALTER TABLE ONLY public.permalink_journals
    ADD CONSTRAINT uq_permalink_journals_permalink UNIQUE (permalink);

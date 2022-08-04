CREATE TABLE public.github_check_notes (
    id uuid NOT NULL,
    check_id uuid NOT NULL,
    note character varying NOT NULL,
    created_by character varying NOT NULL,
    accepted boolean NOT NULL,
    accepted_by character varying,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL
);

ALTER TABLE ONLY public.github_check_notes
    ADD CONSTRAINT pk_github_check_notes PRIMARY KEY (id);

ALTER TABLE ONLY public.github_check_notes
    ADD CONSTRAINT uq_github_check_notes_id UNIQUE (id);

ALTER TABLE ONLY public.github_check_notes
    ADD CONSTRAINT fk_github_check_notes_check_id_github_checks FOREIGN KEY (check_id) REFERENCES public.github_checks(id) ON DELETE CASCADE;

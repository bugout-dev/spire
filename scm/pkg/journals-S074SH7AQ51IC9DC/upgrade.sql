CREATE TABLE public.journals (
    id uuid NOT NULL,
    bugout_user_id character varying NOT NULL,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL,
    name character varying NOT NULL,
    version_id integer NOT NULL,
    deleted boolean NOT NULL,
    search_index character varying
);

ALTER TABLE ONLY public.journals
    ADD CONSTRAINT journals_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.journals
    ADD CONSTRAINT uc_journals_bugout_user_id_name UNIQUE (bugout_user_id, name);

ALTER TABLE ONLY public.journals
    ADD CONSTRAINT uq_journals_id UNIQUE (id);

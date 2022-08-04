CREATE TABLE public.public_journals (
    journal_id uuid NOT NULL,
    user_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL
);

ALTER TABLE ONLY public.public_journals
    ADD CONSTRAINT pk_public_journals PRIMARY KEY (journal_id);

ALTER TABLE ONLY public.public_journals
    ADD CONSTRAINT fk_public_journals_user_id_public_users FOREIGN KEY (user_id) REFERENCES public.public_users(user_id) ON DELETE CASCADE;

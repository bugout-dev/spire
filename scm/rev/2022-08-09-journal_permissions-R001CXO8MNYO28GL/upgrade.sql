CREATE TABLE public.journal_permissions (
    holder_type public.holder_type NOT NULL,
    journal_id uuid NOT NULL,
    holder_id character varying NOT NULL,
    permission character varying NOT NULL
);

ALTER TABLE ONLY public.journal_permissions
    ADD CONSTRAINT pk_journal_permissions PRIMARY KEY (holder_type, journal_id, holder_id, permission);

ALTER TABLE ONLY public.journal_permissions
    ADD CONSTRAINT fk_journal_permissions_journals_id FOREIGN KEY (journal_id) REFERENCES public.journals(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.journal_permissions
    ADD CONSTRAINT fk_journal_permissions_spire_oauth_scopes_scope FOREIGN KEY (permission) REFERENCES public.spire_oauth_scopes(scope) ON UPDATE CASCADE ON DELETE CASCADE;

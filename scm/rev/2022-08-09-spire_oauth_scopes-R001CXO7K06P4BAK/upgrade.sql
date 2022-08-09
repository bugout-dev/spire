CREATE TABLE public.spire_oauth_scopes (
    api character varying NOT NULL,
    scope character varying NOT NULL,
    description character varying NOT NULL
);

ALTER TABLE ONLY public.spire_oauth_scopes
    ADD CONSTRAINT pk_spire_oauth_scopes PRIMARY KEY (api, scope);

ALTER TABLE ONLY public.spire_oauth_scopes
    ADD CONSTRAINT uq_spire_oauth_scopes_scope UNIQUE (scope);

CREATE TABLE public.spire_alembic_version (
    version_num character varying(32) NOT NULL
);

ALTER TABLE ONLY public.spire_alembic_version
    ADD CONSTRAINT spire_alembic_version_pkc PRIMARY KEY (version_num);

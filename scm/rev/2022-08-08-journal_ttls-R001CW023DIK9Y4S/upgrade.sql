CREATE TABLE public.journal_ttls (
    id integer NOT NULL,
    journal_id uuid NOT NULL,
    name character varying(256) NOT NULL,
    conditions jsonb NOT NULL,
    action character varying(1024) NOT NULL,
    active boolean NOT NULL,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL
);

CREATE SEQUENCE public.journal_ttls_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.journal_ttls_id_seq OWNED BY public.journal_ttls.id;

ALTER TABLE ONLY public.journal_ttls ALTER COLUMN id SET DEFAULT nextval('public.journal_ttls_id_seq'::regclass);

ALTER TABLE ONLY public.journal_ttls
    ADD CONSTRAINT pk_journal_ttls PRIMARY KEY (id);

ALTER TABLE ONLY public.journal_ttls
    ADD CONSTRAINT fk_journal_ttls_journal_id_journals FOREIGN KEY (journal_id) REFERENCES public.journals(id) ON DELETE CASCADE;

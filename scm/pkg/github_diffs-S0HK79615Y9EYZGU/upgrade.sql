CREATE TABLE public.github_diffs (
    id uuid NOT NULL,
    comments_url character varying,
    installation_id integer NOT NULL,
    terminal_hash character varying NOT NULL
);

ALTER TABLE ONLY public.github_diffs
    ADD CONSTRAINT pk_github_diffs PRIMARY KEY (id);


ALTER TABLE ONLY public.github_diffs
    ADD CONSTRAINT uq_github_diffs_id UNIQUE (id);

CREATE TABLE public.github_locusts (
    id uuid NOT NULL,
    issue_pr_id uuid NOT NULL,
    terminal_hash character varying NOT NULL,
    s3_uri character varying,
    response_url character varying,
    commented_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL
);

ALTER TABLE ONLY public.github_locusts
    ADD CONSTRAINT pk_github_locusts PRIMARY KEY (id);

ALTER TABLE ONLY public.github_locusts
    ADD CONSTRAINT fk_github_locusts_issue_pr_id_github_issues_prs FOREIGN KEY (issue_pr_id) REFERENCES public.github_issues_prs(id) ON DELETE CASCADE;


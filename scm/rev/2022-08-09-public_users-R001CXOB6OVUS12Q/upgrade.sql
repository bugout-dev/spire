CREATE TABLE public.public_users (
    user_id uuid NOT NULL,
    access_token_id uuid NOT NULL,
    restricted_token_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, statement_timestamp()) NOT NULL
);

ALTER TABLE ONLY public.public_users
    ADD CONSTRAINT pk_public_users PRIMARY KEY (user_id, restricted_token_id);

ALTER TABLE ONLY public.public_users
    ADD CONSTRAINT uq_public_users_access_token_id UNIQUE (access_token_id);

ALTER TABLE ONLY public.public_users
    ADD CONSTRAINT uq_public_users_restricted_token_id UNIQUE (restricted_token_id);

ALTER TABLE ONLY public.public_users
    ADD CONSTRAINT uq_public_users_user_id UNIQUE (user_id);

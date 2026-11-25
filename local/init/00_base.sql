-- Entorno local: roles de PostgREST y tabla Docs.
-- Se ejecuta la primera vez que arranca el contenedor de Postgres.
-- Reproduce lo mínimo que Supabase pone a disposición de la API REST.

create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;
create role authenticator noinherit login password 'authenticator';

grant anon, authenticated, service_role to authenticator;
grant usage on schema public to anon, authenticated, service_role;

alter default privileges in schema public grant all on tables to anon, authenticated, service_role;
alter default privileges in schema public grant all on sequences to anon, authenticated, service_role;
alter default privileges in schema public grant execute on functions to anon, authenticated, service_role;

-- Tabla principal del README: id, created_at, texto_bruto, texto_resumido, transcripcion.
create table "Docs" (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  texto_bruto text not null default '',
  texto_resumido text not null default '',
  transcripcion jsonb
);

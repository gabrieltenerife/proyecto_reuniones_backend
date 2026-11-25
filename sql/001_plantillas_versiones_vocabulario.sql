-- Migración 001: tipo de reunión, historial de versiones y vocabulario propio.
-- Ejecutar una vez en el SQL Editor de Supabase.

alter table "Docs" add column if not exists tipo text not null default 'general';

create table if not exists versiones (
  id bigint generated always as identity primary key,
  doc_id bigint not null references "Docs"(id) on delete cascade,
  campo text not null check (campo in ('transcripcion', 'texto_resumido')),
  contenido jsonb not null,
  origen text not null default 'manual',
  created_at timestamptz not null default now()
);

create index if not exists versiones_doc_id_idx on versiones (doc_id, created_at desc);

create table if not exists vocabulario (
  id bigint generated always as identity primary key,
  termino text not null,
  variante text not null default '',
  created_at timestamptz not null default now(),
  unique (termino, variante)
);

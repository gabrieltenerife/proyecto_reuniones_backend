-- Migración 004: registro de exportaciones (email, Slack...).
-- Ejecutar una vez en el SQL Editor de Supabase, después de la 003.

create table if not exists exportaciones (
  id bigint generated always as identity primary key,
  doc_id bigint not null references "Docs"(id) on delete cascade,
  destino text not null check (destino in ('email', 'slack')),
  destinatario text not null default '',
  estado text not null check (estado in ('enviado', 'error')),
  detalle text not null default '',
  created_at timestamptz not null default now()
);

create index if not exists exportaciones_doc_id_idx on exportaciones (doc_id, created_at desc);

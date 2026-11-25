-- Migración 003: memoria de temas entre reuniones.
-- Ejecutar una vez en el SQL Editor de Supabase, después de la 002.

create table if not exists temas (
  id bigint generated always as identity primary key,
  titulo text not null,
  descripcion text not null default '',
  estado text not null default 'abierto' check (estado in ('abierto', 'resuelto', 'pospuesto')),
  embedding vector(1536) not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists menciones_temas (
  id bigint generated always as identity primary key,
  tema_id bigint not null references temas(id) on delete cascade,
  doc_id bigint not null references "Docs"(id) on delete cascade,
  estado text not null check (estado in ('abierto', 'resuelto', 'pospuesto')),
  minuto double precision not null,
  resumen text not null default '',
  created_at timestamptz not null default now(),
  unique (tema_id, doc_id)
);

create index if not exists menciones_temas_doc_id_idx on menciones_temas (doc_id);
create index if not exists temas_embedding_idx on temas using hnsw (embedding vector_cosine_ops);

create or replace function buscar_temas_similares(
  embedding_consulta vector(1536),
  umbral double precision default 0.45,
  limite int default 5,
  excluir_reunion bigint default null
)
returns table (
  tema_id bigint,
  titulo text,
  descripcion text,
  estado text,
  similitud double precision
)
language sql
stable
as $$
  select t.id, t.titulo, t.descripcion, t.estado,
         1 - (t.embedding <=> embedding_consulta) as similitud
  from temas t
  where 1 - (t.embedding <=> embedding_consulta) >= umbral
    and (
      excluir_reunion is null
      or not exists (
        select 1 from menciones_temas m
        where m.tema_id = t.id and m.doc_id = excluir_reunion
      )
    )
  order by t.embedding <=> embedding_consulta
  limit limite;
$$;

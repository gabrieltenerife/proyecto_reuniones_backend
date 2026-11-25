-- Migración 002: fragmentos indexados por minuto y búsqueda híbrida (semántica + palabras clave).
-- Ejecutar una vez en el SQL Editor de Supabase, después de la 001.

create extension if not exists vector;

create table if not exists fragmentos (
  id bigint generated always as identity primary key,
  doc_id bigint not null references "Docs"(id) on delete cascade,
  inicio double precision not null,
  fin double precision not null,
  hablante text not null,
  texto text not null,
  embedding vector(1536) not null,
  fts tsvector generated always as (to_tsvector('spanish', texto)) stored
);

create index if not exists fragmentos_doc_id_idx on fragmentos (doc_id);
create index if not exists fragmentos_fts_idx on fragmentos using gin (fts);
create index if not exists fragmentos_embedding_idx on fragmentos using hnsw (embedding vector_cosine_ops);

create or replace function buscar_fragmentos(
  consulta text,
  embedding_consulta vector(1536),
  reuniones bigint[] default null,
  limite int default 8
)
returns table (
  fragmento_id bigint,
  reunion_id bigint,
  inicio double precision,
  fin double precision,
  hablante text,
  texto text,
  puntuacion double precision
)
language sql
stable
as $$
  with candidatos as (
    select f.*
    from fragmentos f
    where reuniones is null or f.doc_id = any(reuniones)
  ),
  semantica as (
    select c.id,
           row_number() over (order by c.embedding <=> embedding_consulta) as posicion
    from candidatos c
    order by c.embedding <=> embedding_consulta
    limit 30
  ),
  palabras as (
    select c.id,
           row_number() over (order by ts_rank(c.fts, websearch_to_tsquery('spanish', consulta)) desc) as posicion
    from candidatos c
    where c.fts @@ websearch_to_tsquery('spanish', consulta)
    order by ts_rank(c.fts, websearch_to_tsquery('spanish', consulta)) desc
    limit 30
  ),
  fusion as (
    select coalesce(s.id, p.id) as id,
           coalesce(1.0 / (60 + s.posicion), 0) + coalesce(1.0 / (60 + p.posicion), 0) as puntuacion
    from semantica s
    full outer join palabras p on p.id = s.id
  )
  select f.id, f.doc_id, f.inicio, f.fin, f.hablante, f.texto, fu.puntuacion
  from fusion fu
  join fragmentos f on f.id = fu.id
  order by fu.puntuacion desc
  limit limite;
$$;

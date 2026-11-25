-- Migración 005: cuentas de usuario y separación de reuniones por propietario.

create table if not exists usuarios (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  password_hash text not null,
  created_at timestamptz not null default now(),
  constraint usuarios_email_normalizado check (email = lower(btrim(email)))
);

-- La API usa la clave de servicio. Los roles públicos no deben leer hashes.
revoke all on table usuarios from anon, authenticated;
grant all on table usuarios to service_role;

alter table "Docs"
  add column if not exists owner_id uuid references usuarios(id) on delete set null;
create index if not exists docs_owner_created_at_idx
  on "Docs" (owner_id, created_at desc);

alter table vocabulario
  add column if not exists owner_id uuid references usuarios(id) on delete cascade;
alter table vocabulario drop constraint if exists vocabulario_termino_variante_key;
alter table vocabulario drop constraint if exists vocabulario_owner_unique;
alter table vocabulario add constraint vocabulario_owner_unique
  unique (owner_id, termino, variante);
create index if not exists vocabulario_owner_id_idx on vocabulario (owner_id);

alter table temas
  add column if not exists owner_id uuid references usuarios(id) on delete cascade;
create index if not exists temas_owner_id_idx on temas (owner_id);

-- El primer usuario creado adopta los datos heredados sin propietario.
-- La inserción y la asignación se ejecutan en una sola transacción.
create or replace function registrar_usuario(p_email text, p_password_hash text)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  nuevo_id uuid;
begin
  insert into usuarios (email, password_hash)
  values (lower(btrim(p_email)), p_password_hash)
  on conflict (email) do nothing
  returning id into nuevo_id;

  if nuevo_id is null then
    return null;
  end if;

  update "Docs" set owner_id = nuevo_id where owner_id is null;
  update vocabulario set owner_id = nuevo_id where owner_id is null;
  update temas set owner_id = nuevo_id where owner_id is null;

  return nuevo_id;
end;
$$;

revoke all on function registrar_usuario(text, text) from public, anon, authenticated;
grant execute on function registrar_usuario(text, text) to service_role;

-- Las búsquedas semánticas deben permanecer dentro de la cuenta autenticada.
drop function if exists buscar_fragmentos(text, vector, bigint[], integer);
create or replace function buscar_fragmentos(
  propietario uuid,
  consulta text,
  embedding_consulta vector(1536),
  reuniones bigint[] default null,
  limite integer default 8
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
    join "Docs" d on d.id = f.doc_id
    where d.owner_id = propietario
      and (reuniones is null or f.doc_id = any(reuniones))
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

drop function if exists buscar_temas_similares(vector, double precision, integer, bigint);
create or replace function buscar_temas_similares(
  propietario uuid,
  embedding_consulta vector(1536),
  umbral double precision default 0.45,
  limite integer default 5,
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
  where t.owner_id is not distinct from propietario
    and 1 - (t.embedding <=> embedding_consulta) >= umbral
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

notify pgrst, 'reload schema';

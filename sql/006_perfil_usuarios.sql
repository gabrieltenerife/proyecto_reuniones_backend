-- Migración 006: foto de perfil y revocación de sesiones al cambiar contraseña.

alter table usuarios
  add column if not exists avatar_url text;

alter table usuarios
  add column if not exists token_version integer not null default 0
  check (token_version >= 0);

notify pgrst, 'reload schema';

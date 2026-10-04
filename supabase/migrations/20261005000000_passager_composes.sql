-- A passager may in turn compose evenings of their own, and an instigateur be invited to someone else's: an account
-- is now the instigateur of the evenings it keeps and the passager of those it joined. join_evening no longer turns
-- away an account that keeps evenings; it still refuses one's own invitation.

create or replace function public.join_evening(code text) returns void
language plpgsql security definer set search_path = public as $$
declare
  s public.soirees_choisies;
begin
  if auth.uid() is null then
    raise exception 'Connectez-vous d''abord.';
  end if;
  select * into s from public.soirees_choisies where invite_code = code for update;
  if not found then
    raise exception 'Invitation introuvable : demandez un nouveau lien.';
  end if;
  if s.user_id = auth.uid() then
    raise exception 'C''est votre propre invitation : envoyez-la à votre passager.';
  end if;
  if s.passager is not null and s.passager <> auth.uid() then
    raise exception 'Cette invitation a déjà été acceptée.';
  end if;
  update public.soirees_choisies
  set passager = auth.uid(), passager_email = auth.jwt() ->> 'email', joined_at = now()
  where id = s.id;
end $$;

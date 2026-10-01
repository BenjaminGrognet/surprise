-- How the programme of a kept evening is lifted for its passager (chosen by the instigateur, on their own row):
--   etapes  each step shows a quarter of an hour before it starts (the default)
--   veille  the whole programme shows the day before, after a few days of clues
--   arrivee each step stays veiled until the passager arrives on the spot (or its hour comes)
alter table public.soirees_choisies
  add column reveal_mode text not null default 'etapes'
  check (reveal_mode in ('etapes', 'veille', 'arrivee'));

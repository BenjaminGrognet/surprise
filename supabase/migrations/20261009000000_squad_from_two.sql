-- Secret Squad from two: an evening out with a friend, not a date. A couple's evening stays two; a band's, 2 to 10.
alter table public.soirees_choisies
  drop constraint soirees_choisies_party,
  add constraint soirees_choisies_party check (formule = 'squad' or personnes = 2);

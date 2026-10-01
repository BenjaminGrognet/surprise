-- The secret name of a kept evening ("Le Pacte de l'Île Saint-Louis", surprise.parcours.secret_title): a word of
-- its mood and its quarter, no venue. Fixed when the evening is kept, shown to the instigateur and the passager alike.

alter table public.soirees_choisies add column if not exists secret_title text;

-- Couples' answers to the questionnaire (surprise.quiz) and the profile drawn from them:
-- weighted vibes, persona, audace, refusals, budget, hours. Personal data: no public policy,
-- only the service role reads and writes them.
create table public.couple_profiles (
  id text primary key,
  answers jsonb not null,
  profile jsonb not null,
  created_at timestamptz not null default now()
);

alter table public.couple_profiles enable row level security;

-- The couple's content fed beside the collection (surprise.inspirations, docs/complicite.md « Alimenter les
-- contenus »): the public pages of couple questions, quizzes and défis read again now and then, each idea kept as an
-- inspiration, never shown as is; our version of it (re-imagined by the rules, by Claude on demand, or written in the
-- moderation) published at the end of the journey: a question of the day, a défi, a card, or with seven others a
-- quiz series.
create table pipeline.inspiration_pages (
  url text primary key,
  source_id text not null,
  found integer not null default 0,
  fetched_at timestamptz not null default now()
);

create table pipeline.inspirations (
  id text primary key, -- the harvested text's fingerprint: an idea met again is not kept twice
  source_id text not null,
  url text not null,
  texte text not null, -- the source's words, for the moderation only
  genre text not null check (genre in ('question', 'quiz', 'defi', 'carte')),
  palier smallint not null check (palier between 1 and 4),
  statut text not null default 'nouvelle' check (statut in ('nouvelle', 'proposee', 'gardee', 'publiee', 'ecartee')),
  proposition jsonb, -- our version, in the shape of its genre
  proposee_par text, -- 'regles', a Claude model, or 'moderation'
  publiee text, -- where it went: 'questions_du_jour:109', 'quiz_series:17'…
  fetched_at timestamptz not null default now(),
  decided_at timestamptz
);
create index inspirations_statut_idx on pipeline.inspirations (statut, genre);

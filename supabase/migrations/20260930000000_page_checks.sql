-- What a booking link or official site says (surprise.booking.page_verdict): read again after a month.
create table pipeline.page_checks (
  url text primary key,
  engine text,
  closed boolean not null,
  checked_at timestamptz not null default now()
);

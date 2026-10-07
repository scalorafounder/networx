-- Networx tables. Own schema so nothing touches your other tables.
create schema if not exists event_agent;
create table if not exists event_agent.people (
  id bigserial primary key,
  event text not null,
  name text not null,
  company text,
  link text,
  what_they_do text,
  heard_at text,
  created_at timestamptz default now(),
  unique (event, name)
);
create table if not exists event_agent.promises (
  id bigserial primary key,
  event text not null,
  person text not null,
  who_owes text not null,          -- 'me' or 'them'
  what text not null,
  by_when text,
  quote text,
  status text not null default 'open',  -- open, doing, ready, done, needs_you
  agent_session text,
  research text,
  draft text,
  channel text,
  telegram_sent_at timestamptz,
  updated_at timestamptz default now(),
  created_at timestamptz default now()
);
create table if not exists event_agent.runs (
  id bigserial primary key,
  kind text, note text, created_at timestamptz default now()
);

-- live feed the screen reads: one row per thing the agent does
create table if not exists event_agent.events (
  id bigserial primary key,
  ts timestamptz default now(),
  event text,
  kind text not null,       -- heard, person, promise, box, found, draft, sent, recap
  promise_id bigint,
  person text,
  text text
);

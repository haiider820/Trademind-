-- TradeMind AI initial schema for Supabase Postgres

create extension if not exists "pgcrypto";

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  name text,
  role text not null default 'user' check (role in ('user', 'admin')),
  subscription text not null default 'free' check (subscription in ('free', 'premium')),
  created_at timestamptz not null default now()
);

create table if not exists public.signals (
  id uuid primary key default gen_random_uuid(),
  pair text not null,
  trade_type text not null check (trade_type in ('long', 'short')),
  entry numeric(18,8) not null,
  sl numeric(18,8) not null,
  tp numeric(18,8) not null,
  risk_level text not null check (risk_level in ('low', 'medium', 'high')),
  status text not null default 'open' check (status in ('open', 'tp_hit', 'sl_hit', 'closed')),
  pnl numeric(18,8) not null default 0,
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now()
);

create table if not exists public.lessons (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  category text not null,
  video_url text,
  description text,
  thumbnail text,
  created_at timestamptz not null default now()
);

create table if not exists public.news (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  content text,
  sentiment text not null default 'neutral' check (sentiment in ('bullish', 'bearish', 'neutral')),
  category text not null default 'crypto' check (category in ('crypto', 'forex', 'macro')),
  source text,
  published_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists public.whale_alerts (
  id uuid primary key default gen_random_uuid(),
  coin text not null,
  amount numeric(24,8) not null,
  wallet_type text,
  action text,
  created_at timestamptz not null default now()
);

create table if not exists public.liquidations (
  id uuid primary key default gen_random_uuid(),
  coin text not null,
  amount numeric(24,8) not null,
  side text not null check (side in ('long', 'short')),
  created_at timestamptz not null default now()
);

create table if not exists public.device_tokens (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  token text not null unique,
  platform text not null check (platform in ('android', 'ios', 'web')),
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.profiles enable row level security;
alter table public.signals enable row level security;
alter table public.lessons enable row level security;
alter table public.news enable row level security;
alter table public.whale_alerts enable row level security;
alter table public.liquidations enable row level security;
alter table public.device_tokens enable row level security;

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
as $$
begin
  insert into public.profiles (id, name, role, subscription)
  values (new.id, coalesce(new.raw_user_meta_data->>'name', ''), 'user', 'free')
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute procedure public.handle_new_user();

create policy "profiles_select_own"
on public.profiles
for select
using (auth.uid() = id);

create policy "profiles_insert_own"
on public.profiles
for insert
with check (auth.uid() = id);

create policy "profiles_update_own"
on public.profiles
for update
using (auth.uid() = id)
with check (auth.uid() = id);

create policy "signals_select_all_authenticated"
on public.signals
for select
using (auth.role() = 'authenticated');

create policy "signals_admin_write"
on public.signals
for all
using (
  exists (
    select 1 from public.profiles p
    where p.id = auth.uid() and p.role = 'admin'
  )
)
with check (
  exists (
    select 1 from public.profiles p
    where p.id = auth.uid() and p.role = 'admin'
  )
);

create policy "lessons_select_all_authenticated"
on public.lessons
for select
using (auth.role() = 'authenticated');

create policy "lessons_admin_write"
on public.lessons
for all
using (
  exists (
    select 1 from public.profiles p
    where p.id = auth.uid() and p.role = 'admin'
  )
)
with check (
  exists (
    select 1 from public.profiles p
    where p.id = auth.uid() and p.role = 'admin'
  )
);

create policy "news_select_all_authenticated"
on public.news
for select
using (auth.role() = 'authenticated');

create policy "news_admin_write"
on public.news
for all
using (
  exists (
    select 1 from public.profiles p
    where p.id = auth.uid() and p.role = 'admin'
  )
)
with check (
  exists (
    select 1 from public.profiles p
    where p.id = auth.uid() and p.role = 'admin'
  )
);

create policy "device_tokens_select_own"
on public.device_tokens
for select
using (auth.uid() = user_id);

create policy "device_tokens_insert_own"
on public.device_tokens
for insert
with check (auth.uid() = user_id);

create policy "device_tokens_update_own"
on public.device_tokens
for update
using (auth.uid() = user_id)
with check (auth.uid() = user_id);


-- TradeMind AI initial schema for Supabase

create extension if not exists "pgcrypto";

-- =========================
-- TABLES
-- =========================

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  name text,
  role text not null default 'user'
    check (role in ('user', 'admin')),
  subscription text not null default 'free'
    check (subscription in ('free', 'premium')),
  created_at timestamptz not null default now()
);

create table if not exists public.signals (
  id uuid primary key default gen_random_uuid(),
  pair text not null,
  trade_type text not null
    check (trade_type in ('long', 'short')),
  entry numeric(18,8) not null,
  sl numeric(18,8) not null,
  tp numeric(18,8) not null,
  risk_level text not null
    check (risk_level in ('low', 'medium', 'high')),
  status text not null default 'open'
    check (status in ('open', 'tp_hit', 'sl_hit', 'closed')),
  pnl numeric(18,8) not null default 0,
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now()
);

create table if not exists public.lessons (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  category text not null,
  video_url text,
  description text,
  thumbnail text,
  created_at timestamptz not null default now()
);

create table if not exists public.news (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  content text,
  sentiment text not null default 'neutral'
    check (sentiment in ('bullish', 'bearish', 'neutral')),
  category text not null default 'crypto'
    check (category in ('crypto', 'forex', 'macro')),
  source text,
  published_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists public.whale_alerts (
  id uuid primary key default gen_random_uuid(),
  coin text not null,
  amount numeric(24,8) not null,
  wallet_type text,
  action text,
  created_at timestamptz not null default now()
);

create table if not exists public.liquidations (
  id uuid primary key default gen_random_uuid(),
  coin text not null,
  amount numeric(24,8) not null,
  side text not null
    check (side in ('long', 'short')),
  created_at timestamptz not null default now()
);

-- =========================
-- ENABLE RLS
-- =========================

alter table public.profiles enable row level security;
alter table public.signals enable row level security;
alter table public.lessons enable row level security;
alter table public.news enable row level security;
alter table public.whale_alerts enable row level security;
alter table public.liquidations enable row level security;

-- =========================
-- REMOVE OLD POLICIES
-- =========================

drop policy if exists "profiles_select_own" on public.profiles;

drop policy if exists "signals_select_all_authenticated" on public.signals;
drop policy if exists "signals_admin_write" on public.signals;

drop policy if exists "lessons_select_all_authenticated" on public.lessons;
drop policy if exists "lessons_admin_write" on public.lessons;

drop policy if exists "news_select_all_authenticated" on public.news;
drop policy if exists "news_admin_write" on public.news;

drop policy if exists "whale_alerts_select_all_authenticated" on public.whale_alerts;
drop policy if exists "whale_alerts_admin_write" on public.whale_alerts;

drop policy if exists "liquidations_select_all_authenticated" on public.liquidations;
drop policy if exists "liquidations_admin_write" on public.liquidations;

-- =========================
-- PROFILES POLICIES
-- =========================

create policy "profiles_select_own"
on public.profiles
for select
using (auth.uid() = id);

create policy "profiles_update_own"
on public.profiles
for update
using (auth.uid() = id);

-- =========================
-- SIGNALS POLICIES
-- =========================

create policy "signals_select_all_authenticated"
on public.signals
for select
using (auth.role() = 'authenticated');

create policy "signals_admin_write"
on public.signals
for all
using (
  exists (
    select 1
    from public.profiles p
    where p.id = auth.uid()
    and p.role = 'admin'
  )
)
with check (
  exists (
    select 1
    from public.profiles p
    where p.id = auth.uid()
    and p.role = 'admin'
  )
);

-- =========================
-- LESSONS POLICIES
-- =========================

create policy "lessons_select_all_authenticated"
on public.lessons
for select
using (auth.role() = 'authenticated');

create policy "lessons_admin_write"
on public.lessons
for all
using (
  exists (
    select 1
    from public.profiles p
    where p.id = auth.uid()
    and p.role = 'admin'
  )
)
with check (
  exists (
    select 1
    from public.profiles p
    where p.id = auth.uid()
    and p.role = 'admin'
  )
);

-- =========================
-- NEWS POLICIES
-- =========================

create policy "news_select_all_authenticated"
on public.news
for select
using (auth.role() = 'authenticated');

create policy "news_admin_write"
on public.news
for all
using (
  exists (
    select 1
    from public.profiles p
    where p.id = auth.uid()
    and p.role = 'admin'
  )
)
with check (
  exists (
    select 1
    from public.profiles p
    where p.id = auth.uid()
    and p.role = 'admin'
  )
);

-- =========================
-- WHALE ALERTS POLICIES
-- =========================

create policy "whale_alerts_select_all_authenticated"
on public.whale_alerts
for select
using (auth.role() = 'authenticated');

create policy "whale_alerts_admin_write"
on public.whale_alerts
for all
using (
  exists (
    select 1
    from public.profiles p
    where p.id = auth.uid()
    and p.role = 'admin'
  )
)
with check (
  exists (
    select 1
    from public.profiles p
    where p.id = auth.uid()
    and p.role = 'admin'
  )
);

-- =========================
-- LIQUIDATIONS POLICIES
-- =========================

create policy "liquidations_select_all_authenticated"
on public.liquidations
for select
using (auth.role() = 'authenticated');

create policy "liquidations_admin_write"
on public.liquidations
for all
using (
  exists (
    select 1
    from public.profiles p
    where p.id = auth.uid()
    and p.role = 'admin'
  )
)
with check (
  exists (
    select 1
    from public.profiles p
    where p.id = auth.uid()
    and p.role = 'admin'
  )
);

-- =========================
-- AUTO CREATE PROFILE
-- =========================

create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id)
  values (new.id);

  return new;
end;
$$ language plpgsql security definer;

drop trigger if exists on_auth_user_created on auth.users;

create trigger on_auth_user_created
after insert on auth.users
for each row
execute procedure public.handle_new_user();
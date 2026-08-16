create table if not exists public.device_tokens (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  token text not null unique,
  platform text not null check (platform in ('android', 'ios', 'web')),
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.device_tokens enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'device_tokens' and policyname = 'device_tokens_select_own'
  ) then
    create policy "device_tokens_select_own"
    on public.device_tokens
    for select
    using (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'device_tokens' and policyname = 'device_tokens_insert_own'
  ) then
    create policy "device_tokens_insert_own"
    on public.device_tokens
    for insert
    with check (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'device_tokens' and policyname = 'device_tokens_update_own'
  ) then
    create policy "device_tokens_update_own"
    on public.device_tokens
    for update
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);
  end if;
end $$;

alter table public.news add column if not exists external_id text;
create unique index if not exists idx_news_external_id on public.news(external_id);

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

alter table public.signals add column if not exists tp1 numeric(18,8);
alter table public.signals add column if not exists tp2 numeric(18,8);
alter table public.signals add column if not exists tp3 numeric(18,8);
alter table public.signals add column if not exists tp1_hit boolean not null default false;
alter table public.signals add column if not exists realized_pnl numeric(18,8) not null default 0;
alter table public.signals add column if not exists realized_at timestamptz;

create table if not exists public.watchlists (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  symbol text not null,
  sort_order int not null default 0,
  created_at timestamptz not null default now(),
  unique (user_id, symbol)
);

create table if not exists public.notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  title text not null,
  body text not null,
  type text not null default 'info',
  data jsonb,
  is_read boolean not null default false,
  created_at timestamptz not null default now()
);

create table if not exists public.user_notification_prefs (
  user_id uuid primary key references auth.users(id) on delete cascade,
  signals boolean not null default true,
  news boolean not null default true,
  whale_alerts boolean not null default true,
  liquidations boolean not null default true,
  breaking_news boolean not null default true,
  updated_at timestamptz not null default now()
);

create table if not exists public.chat_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.chat_messages (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.chat_sessions(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  content text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.user_lesson_progress (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  lesson_id uuid not null references public.lessons(id) on delete cascade,
  percent_watched int not null default 0,
  quiz_score int,
  completed_at timestamptz,
  updated_at timestamptz not null default now(),
  unique (user_id, lesson_id)
);

alter table public.watchlists enable row level security;
alter table public.notifications enable row level security;
alter table public.user_notification_prefs enable row level security;
alter table public.chat_sessions enable row level security;
alter table public.chat_messages enable row level security;
alter table public.user_lesson_progress enable row level security;

create policy "watchlists_select_own"
on public.watchlists for select using (auth.uid() = user_id);
create policy "watchlists_write_own"
on public.watchlists for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy "notifications_select_own"
on public.notifications for select using (auth.uid() = user_id or user_id is null);
create policy "notifications_write_own"
on public.notifications for all using (auth.uid() = user_id) with check (auth.uid() = user_id or user_id is null);

create policy "user_notification_prefs_select_own"
on public.user_notification_prefs for select using (auth.uid() = user_id);
create policy "user_notification_prefs_write_own"
on public.user_notification_prefs for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy "chat_sessions_select_own"
on public.chat_sessions for select using (auth.uid() = user_id);
create policy "chat_sessions_write_own"
on public.chat_sessions for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy "chat_messages_select_own"
on public.chat_messages for select using (auth.uid() = user_id);
create policy "chat_messages_write_own"
on public.chat_messages for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy "user_lesson_progress_select_own"
on public.user_lesson_progress for select using (auth.uid() = user_id);
create policy "user_lesson_progress_write_own"
on public.user_lesson_progress for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

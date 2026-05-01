-- ── FAZA C: KOMENTARZE NA SPOTACH (clean install) ─────────────────────────
-- UWAGA: dropi istniejącą tabelę spot_comments z poprzedniej (wadliwej) próby
-- ───────────────────────────────────────────────────────────────────────────

drop view  if exists v_spot_comments cascade;
drop trigger if exists trg_spot_comments_count on spot_comments;
drop function if exists _spot_comments_count_trigger() cascade;
drop table if exists spot_comments cascade;

create table spot_comments (
  id          bigserial primary key,
  spot_id     bigint not null references spots(id) on delete cascade,
  user_id     uuid not null references auth.users(id) on delete cascade,
  text        text not null check (length(text) between 1 and 500),
  created_at  timestamptz not null default now()
);

create index spot_comments_spot_idx on spot_comments(spot_id, created_at desc);
create index spot_comments_user_idx on spot_comments(user_id);

alter table spots add column if not exists comment_count integer not null default 0;

alter table spot_comments enable row level security;

create policy "spot_comments_select" on spot_comments
  for select using (true);

create policy "spot_comments_insert" on spot_comments
  for insert with check (auth.uid() = user_id);

create policy "spot_comments_delete" on spot_comments
  for delete using (
    auth.uid() = user_id
    or auth.uid() = (select posted_by from spots where id = spot_id)
  );

create or replace function _spot_comments_count_trigger() returns trigger
language plpgsql security definer as $$
begin
  if TG_OP = 'INSERT' then
    update spots set comment_count = comment_count + 1 where id = new.spot_id;
    return new;
  elsif TG_OP = 'DELETE' then
    update spots set comment_count = greatest(0, comment_count - 1) where id = old.spot_id;
    return old;
  end if;
  return null;
end $$;

create trigger trg_spot_comments_count
  after insert or delete on spot_comments
  for each row execute function _spot_comments_count_trigger();

create or replace view v_spot_comments as
select
  c.id, c.spot_id, c.user_id, c.text, c.created_at,
  p.display_name as author_name,
  p.avatar_url   as author_avatar
from spot_comments c
left join profiles p on p.id = c.user_id;

grant select on v_spot_comments to anon, authenticated;

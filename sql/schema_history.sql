-- Supabase の SQL Editor で1回だけ実行する（「この案にする」で選んだ献立の記録）。
-- 先に schema_nicknames.sql を実行しておくこと（nicknames を参照する）。
-- 用途：昨日・一昨日に選んだ料理を、提案の候補から外す。
create table if not exists meal_history (
  nickname    text not null references nicknames(nickname) on delete cascade,
  served_date date not null,                                   -- 日本時間の日付
  slot        text not null check (slot in ('morning', 'lunch', 'dinner')),
  recipe_id   text not null check (char_length(recipe_id) between 1 and 50),
  name        text not null default '' check (char_length(name) <= 80),
  created_at  timestamptz not null default now(),
  primary key (nickname, served_date, slot)                    -- 同じ日に選び直したら上書き
);

-- nicknames と同じ方針：RLSを有効にしてポリシーは作らない（アプリは Secret key で操作する）
alter table meal_history enable row level security;

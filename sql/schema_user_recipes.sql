-- Supabase の SQL Editor で1回だけ実行する（自作レシピのテーブル）。
-- 先に schema_nicknames.sql を実行しておくこと（nicknames を参照する）。
create table if not exists user_recipes (
  id            bigint generated always as identity primary key,
  nickname      text not null references nicknames(nickname) on delete cascade,
  name          text not null check (char_length(name) between 1 and 40),
  description   text not null default '' check (char_length(description) <= 500),
  cost_yen      numeric not null,
  prep_min      numeric not null,
  kcal          numeric not null,
  protein_g     numeric not null,
  fat_g         numeric not null,
  carb_g        numeric not null,
  fiber_g       numeric,          -- 補助栄養は任意（空欄可）
  salt_g        numeric,
  calcium_mg    numeric,
  iron_mg       numeric,
  vitamin_c_mg  numeric,
  exclude_slots text not null default '',   -- 食べられない枠。例 'lunch,dinner'（meals.csv と同じ書式）
  ai_estimated  boolean not null default false,
  is_public     boolean not null default false,
  created_at    timestamptz not null default now()
);

create index if not exists user_recipes_nickname_idx on user_recipes (nickname);
create index if not exists user_recipes_public_idx on user_recipes (is_public);

-- nicknames と同じ方針：RLSを有効にしてポリシーは作らない（アプリは Secret key で操作する）
alter table user_recipes enable row level security;

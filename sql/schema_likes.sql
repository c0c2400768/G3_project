-- Supabase の SQL Editor で1回だけ実行する（好き度のテーブル）。
-- 先に schema_nicknames.sql を実行しておくこと（nicknames を参照する）。
create table if not exists likes (
  nickname   text not null references nicknames(nickname) on delete cascade,
  recipe_id  text not null check (char_length(recipe_id) between 1 and 50),  -- 自作レシピは 'U'+id
  score      smallint not null check (score between 1 and 5),
  updated_at timestamptz not null default now(),
  primary key (nickname, recipe_id)
);

-- nicknames と同じ方針：RLSを有効にしてポリシーは作らない（アプリは service_role キーで操作する）
alter table likes enable row level security;

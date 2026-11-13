-- Supabase の SQL Editor で1回だけ実行する（ニックネームとパスワードのテーブル）。
create table if not exists nicknames (
  nickname     text primary key,              -- 重複はこの主キー制約で防ぐ
  salt         text not null,
  pass_hash    text not null,
  failed_count integer not null default 0,
  locked_until timestamptz,
  created_at   timestamptz not null default now()
);

-- 行レベルセキュリティを有効にし、ポリシーは作らない。
-- → 公開用の anon キーでは読み書きできない（ハッシュを外から取れない）。
-- アプリは service_role キー（RLSを通過する）を Secrets に置いて使う。
alter table nicknames enable row level security;

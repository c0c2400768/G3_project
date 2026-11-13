"""Supabase への接続と、ニックネーム＋パスワード（数字4桁）の登録・ログイン。

担当：トップ画面（岩間）。好き度（likes）と自作レシピ（user_recipes）の保存関数は、
それぞれの担当者がこのファイルに追加する（接続は get_client() を使う）。

Secrets（.streamlit/secrets.toml または Streamlit Community Cloud の Secrets）に必要な値:
    [supabase]  url, key      ← key は service_role。サーバー側だけで使い、GitHub に上げない
    [auth]      pepper        ← パスワードのハッシュに混ぜる秘密の値（長いランダム文字列）

注意：4桁の数字は総当たりに弱い。ロック（5回失敗で10分）と salt＋pepper のハッシュで
「気軽ななりすまし」を防ぐ程度の強さで、本格的な認証ではない。個人情報は扱わない前提。
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

import streamlit as st

try:
    from supabase import create_client
except ImportError:  # ライブラリ未インストールでも画面は動かす（登録なしで使える）
    create_client = None

MAX_FAILS = 5          # 連続失敗の上限
LOCK_MINUTES = 10      # ロック時間（仮案）
NICKNAME_MAX = 20
PBKDF2_ROUNDS = 200_000
_PIN_RE = re.compile(r"[0-9]{4}")  # \d は全角数字も通すので使わない

UNAVAILABLE_MSG = "データベースに接続できませんでした。「登録なし」で続けられます。"


# ---------- 接続 ----------
@st.cache_resource
def _make_client(url: str, key: str):
    return create_client(url, key)


def get_client():
    """Supabase クライアント。使えないときは None。"""
    if create_client is None:
        return None
    try:
        sb = st.secrets["supabase"]
        return _make_client(sb["url"], sb["key"])
    except Exception:
        return None


def _pepper() -> str | None:
    try:
        return st.secrets["auth"]["pepper"]
    except Exception:
        return None


def is_available() -> bool:
    """登録・ログインに必要な設定（接続情報と pepper）がそろっているか。"""
    return get_client() is not None and _pepper() is not None


# ---------- 入力の検証 ----------
def normalize_nickname(raw: str | None) -> str:
    return (raw or "").strip()


def validate_nickname(nick: str) -> str | None:
    if not 1 <= len(nick) <= NICKNAME_MAX:
        return f"ニックネームは1〜{NICKNAME_MAX}文字で入力してください。"
    return None


def validate_pin(pin: str | None) -> str | None:
    if not pin or not _PIN_RE.fullmatch(pin):
        return "パスワードは半角の数字4桁で入力してください。"
    return None


# ---------- ハッシュ ----------
def _hash_pin(pin: str, salt_hex: str, pepper: str) -> str:
    """利用者ごとの salt と Secrets の pepper を混ぜたハッシュ。平文は保存しない。"""
    return hashlib.pbkdf2_hmac(
        "sha256", pin.encode(), bytes.fromhex(salt_hex) + pepper.encode(), PBKDF2_ROUNDS
    ).hex()


def _is_duplicate(e: Exception) -> bool:
    text = str(e).lower()
    return getattr(e, "code", None) == "23505" or "23505" in text or "duplicate key" in text


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# ---------- 登録・ログイン ----------
def register(nickname: str, pin: str) -> tuple[bool, str]:
    """新規登録。重複は「確認してから追加」ではなく、追加を試みて主キー制約の失敗で判定する。"""
    nick = normalize_nickname(nickname)
    err = validate_nickname(nick) or validate_pin(pin)
    if err:
        return False, err
    if not is_available():
        return False, UNAVAILABLE_MSG
    salt = secrets.token_hex(16)
    try:
        get_client().table("nicknames").insert(
            {"nickname": nick, "salt": salt, "pass_hash": _hash_pin(pin, salt, _pepper())}
        ).execute()
    except Exception as e:
        if _is_duplicate(e):
            return False, "このニックネームは使われています。別の名前にしてください。"
        return False, UNAVAILABLE_MSG
    return True, "登録しました。"


def login(nickname: str, pin: str) -> tuple[bool, str]:
    """ログイン。連続5回失敗で10分ロック（DBに保存するので再読み込みでは解除されない）。"""
    nick = normalize_nickname(nickname)
    err = validate_nickname(nick) or validate_pin(pin)
    if err:
        return False, err
    if not is_available():
        return False, UNAVAILABLE_MSG
    wrong = "ニックネームまたはパスワードが違います。"
    try:
        table = get_client().table("nicknames")
        rows = table.select("*").eq("nickname", nick).limit(1).execute().data
        if not rows:
            return False, wrong
        row = rows[0]

        now = datetime.now(timezone.utc)
        try:
            locked_until = _parse_ts(row.get("locked_until"))
        except ValueError:  # 読み取れないときはロック扱い（安全側）
            return False, "現在ログインできません。しばらくしてからやり直してください。"
        if locked_until and locked_until > now:
            minutes = int((locked_until - now).total_seconds() // 60) + 1
            return False, f"失敗が続いたためロック中です。約{minutes}分後にやり直してください。"

        expected = _hash_pin(pin, row["salt"], _pepper())
        if hmac.compare_digest(expected, row["pass_hash"]):
            if row.get("failed_count") or row.get("locked_until"):
                table.update({"failed_count": 0, "locked_until": None}).eq("nickname", nick).execute()
            return True, "ログインしました。"

        fails = int(row.get("failed_count") or 0) + 1
        update = {"failed_count": fails}
        if fails >= MAX_FAILS:
            # 秒未満を切り捨てて保存し、返ってくる時刻の書式を安定させる
            until = (now + timedelta(minutes=LOCK_MINUTES)).replace(microsecond=0)
            update["locked_until"] = until.isoformat()
        table.update(update).eq("nickname", nick).execute()
        if fails >= MAX_FAILS:
            return False, f"{MAX_FAILS}回失敗したため{LOCK_MINUTES}分間ロックしました。"
        return False, f"{wrong}（あと{MAX_FAILS - fails}回でロック）"
    except Exception:
        return False, UNAVAILABLE_MSG

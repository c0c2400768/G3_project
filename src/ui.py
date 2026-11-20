"""画面の見た目（デザイン）を整える共通部品。機能は持たない。

- 全ページで `ui.apply_theme()` を1回呼ぶ（st.set_page_config の直後）。
- 上部の大きな見出しは `ui.hero()`、ページ上部の小さな見出しは `ui.page_header()`、
  カードの見出しは `ui.section()` を使う。
- 配色は .streamlit/config.toml のライト／ダーク設定に従い、ここの CSS は文字色を継承するので
  どちらのモードでも読める。バナー（hero）だけは、どちらのモードでも濃い色の面にしてある。
"""
from __future__ import annotations

import base64
import html
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
HERO_IMAGE = ROOT / "assets" / "hero.jpg"
ACCENT = "#F2674F"

# アイコン（線画。Lucide 由来の単純な図形）。CSS のマスクとして使い、文字色や白で塗る
_ICONS = {
    "utensils": '<path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2"/><path d="M7 2v20"/>'
                '<path d="M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7"/>',
    "user": '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "list": '<line x1="8" x2="21" y1="6" y2="6"/><line x1="8" x2="21" y1="12" y2="12"/><line x1="8" x2="21" y1="18" y2="18"/>'
            '<line x1="3" x2="3.01" y1="6" y2="6"/><line x1="3" x2="3.01" y1="12" y2="12"/><line x1="3" x2="3.01" y1="18" y2="18"/>',
    "heart": '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>',
    "trend": '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
    "eye": '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
    "sliders": '<line x1="21" x2="14" y1="4" y2="4"/><line x1="10" x2="3" y1="4" y2="4"/>'
               '<line x1="21" x2="12" y1="12" y2="12"/><line x1="8" x2="3" y1="12" y2="12"/>'
               '<line x1="21" x2="16" y1="20" y2="20"/><line x1="12" x2="3" y1="20" y2="20"/>'
               '<line x1="14" x2="14" y1="2" y2="6"/><line x1="8" x2="8" y1="10" y2="14"/>'
               '<line x1="16" x2="16" y1="18" y2="22"/>',
}


def _mask_uri(inner: str) -> str:
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#000" '
           'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + inner + "</svg>")
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


_CSS = """
<style>
.block-container { max-width: 780px; padding-top: 4.5rem; }  /* 固定ヘッダー（Deploy の帯）に隠れない余白 */

/* アイコン（マスク）。色は周りの文字色に従う */
.ui-i { display: inline-block; width: 1.5rem; height: 1.5rem; background-color: currentColor;
        -webkit-mask: var(--m) center / contain no-repeat; mask: var(--m) center / contain no-repeat; }
__ICON_RULES__

/* バナー：ライト／ダークのどちらでも濃い面にする */
.ui-hero { display: flex; align-items: stretch; border-radius: 20px; overflow: hidden; margin: 0 0 1rem;
           color: #fff; background: linear-gradient(115deg, #4a2226 0%, #241a2e 52%, #101a2c 100%);
           box-shadow: 0 6px 24px rgba(0, 0, 0, .22); }
.ui-hero-body { flex: 1 1 auto; min-width: 0; padding: 1.6rem 1.7rem; }
.ui-hero-title { display: flex; align-items: center; gap: .9rem; }
.ui-badge { flex: 0 0 auto; width: 48px; height: 48px; border-radius: 14px; display: flex;
            align-items: center; justify-content: center;
            background: linear-gradient(145deg, #ff8a6b, #e8503a); box-shadow: 0 4px 12px rgba(232, 80, 58, .45); }
.ui-badge .ui-i { width: 1.7rem; height: 1.7rem; background-color: #fff; }
.ui-hero-h { margin: 0; font-size: 1.7rem; font-weight: 800; line-height: 1.25; color: #fff; }
.ui-hero-bar { width: 92px; height: 4px; border-radius: 2px; background: #ff7a63; margin: .7rem 0 .9rem 62px; }
.ui-hero-sub { margin: 0 0 .6rem; font-size: 1rem; line-height: 1.7; color: rgba(255, 255, 255, .92); }
.ui-hero-note { margin: 0; font-size: .85rem; line-height: 1.6; color: rgba(255, 255, 255, .72); }
.ui-hero-img { flex: 0 0 36%; background-size: cover; background-position: center;
               -webkit-mask-image: linear-gradient(to right, transparent 0, #000 45%);
               mask-image: linear-gradient(to right, transparent 0, #000 45%); }
.ui-hero-compact .ui-hero-body { padding: 1.1rem 1.4rem; }
.ui-hero-compact .ui-hero-h { font-size: 1.5rem; }
.ui-hero-compact .ui-badge { width: 40px; height: 40px; border-radius: 12px; }
.ui-hero-compact .ui-hero-bar { margin: .5rem 0 .6rem 54px; }
@media (max-width: 640px) {
  .ui-hero-img { display: none; }
  .ui-hero-body { padding: 1.2rem 1.1rem; }
  .ui-hero-h { font-size: 1.45rem; }
  .ui-hero-bar { margin-left: 0; }
}

/* カードの見出し（アイコン＋タイトル） */
.ui-section { display: flex; align-items: center; gap: .6rem; margin: .1rem 0 .5rem;
              font-size: 1.25rem; font-weight: 700; }
.ui-section .ui-ico { color: __ACCENT__; display: inline-flex; }

/* 主ボタン：コーラル色のグラデーション */
[data-testid^="stBaseButton-primary"] { background: linear-gradient(135deg, #ff8a6b, __ACCENT__); border: 0;
    color: #fff; font-weight: 700; border-radius: 14px; padding: .65rem 1rem;
    box-shadow: 0 4px 14px rgba(242, 103, 79, .35); }
[data-testid^="stBaseButton-primary"]:hover { filter: brightness(1.07); color: #fff; }

/* 数字つきバナー */
.ui-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: .6rem; margin-top: .9rem; }
.ui-stat { background: #2a3247; border-radius: 12px; padding: .6rem .8rem; }
.ui-stat-l { font-size: .72rem; color: #aab3c8; }
.ui-stat-v { font-size: 1.25rem; font-weight: 700; color: #fff; }
.ui-stat-hi { color: #ff9a85; }

/* 目安カード・機能カード（ライト／ダークどちらでも読める半透明の面） */
.ui-tint { background: rgba(128, 128, 128, .10); border-radius: 14px; padding: 1rem 1.1rem; }
.ui-pv-k { font-size: 2rem; font-weight: 700; line-height: 1.2; }
.ui-pv-k span { font-size: .85rem; font-weight: 400; opacity: .7; margin-left: .3rem; }
.ui-pv-slots { display: grid; grid-template-columns: repeat(3, 1fr); gap: .5rem; margin: .8rem 0; }
.ui-pv-s { background: rgba(128, 128, 128, .12); border-radius: 10px; padding: .45rem .6rem; font-size: .72rem; }
.ui-pv-s b { display: block; font-size: 1rem; }
.ui-pv-row { display: flex; justify-content: space-between; align-items: baseline; font-size: .85rem; }
.ui-pv-row b { font-size: 1.05rem; }
.ui-pv-note { margin: .8rem 0 0; padding-top: .7rem; border-top: 1px solid rgba(128, 128, 128, .25);
              font-size: .78rem; line-height: 1.6; opacity: .75; }
.ui-feats { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: .6rem; margin-top: .4rem; }
.ui-feat { display: flex; gap: .7rem; align-items: center; border: 1px solid rgba(128, 128, 128, .25);
           border-radius: 12px; padding: .7rem .9rem; }
.ui-feat .ui-i { width: 1.4rem; height: 1.4rem; color: __ACCENT__; flex: 0 0 auto; }
.ui-feat b { display: block; font-size: .9rem; }
.ui-feat span.s { font-size: .75rem; opacity: .7; }
</style>
"""


def _image_css() -> str:
    """バナー右側の写真（assets/hero.jpg）を CSS の背景にする。ファイルがなければ何も出さない。"""
    try:
        data = base64.b64encode(HERO_IMAGE.read_bytes()).decode()
    except OSError:
        return ""
    return f'<style>.ui-hero-img {{ background-image: url("data:image/jpeg;base64,{data}"); }}</style>'


@st.cache_data
def _theme_css() -> str:
    rules = "\n".join(f'.ui-i-{name} {{ --m: url("{_mask_uri(inner)}"); }}' for name, inner in _ICONS.items())
    return _CSS.replace("__ICON_RULES__", rules).replace("__ACCENT__", ACCENT) + _image_css()


def apply_theme() -> None:
    """共通の CSS を入れる。各ページで1回だけ呼ぶ。"""
    st.markdown(_theme_css(), unsafe_allow_html=True)


def hero(title: str, subtitle: str, note: str | None = None, image: bool = True, compact: bool = False) -> None:
    """ページ上部のバナー。HTML は1行にまとめる（空行や字下げがあると、Markdown が崩す）。"""
    note_html = f'<p class="ui-hero-note">ⓘ {html.escape(note)}</p>' if note else ""
    img_html = '<div class="ui-hero-img"></div>' if (image and HERO_IMAGE.exists()) else ""
    cls = "ui-hero ui-hero-compact" if compact else "ui-hero"
    st.markdown(
        f'<div class="{cls}"><div class="ui-hero-body"><div class="ui-hero-title">'
        f'<span class="ui-badge"><span class="ui-i ui-i-utensils"></span></span>'
        f'<div class="ui-hero-h" role="heading" aria-level="1">{html.escape(title)}</div></div>'
        f'<div class="ui-hero-bar"></div><p class="ui-hero-sub">{html.escape(subtitle)}</p>{note_html}'
        f"</div>{img_html}</div>",
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str) -> None:
    """トップ以外のページの見出し（写真なしの小さいバナー）。"""
    hero(title, subtitle, image=False, compact=True)


def section(title: str, icon: str) -> None:
    """カードの見出し。icon は "user" か "sliders"。"""
    st.markdown(
        f'<div class="ui-section"><span class="ui-ico"><span class="ui-i ui-i-{icon}"></span></span>'
        f"<span>{html.escape(title)}</span></div>",
        unsafe_allow_html=True,
    )


def hero_stats(title: str, subtitle: str, stats: list[tuple[str, str, bool]], note: str | None = None) -> None:
    """数字つきバナー。stats は (ラベル, 値, 強調するか) のリスト。"""
    chips = "".join(
        f'<div class="ui-stat"><div class="ui-stat-l">{html.escape(l)}</div>'
        f'<div class="ui-stat-v{" ui-stat-hi" if hi else ""}">{html.escape(v)}</div></div>'
        for l, v, hi in stats
    )
    note_html = f'<p class="ui-hero-note">ⓘ {html.escape(note)}</p>' if note else ""
    st.markdown(
        f'<div class="ui-hero ui-hero-compact"><div class="ui-hero-body"><div class="ui-hero-title">'
        f'<span class="ui-badge"><span class="ui-i ui-i-utensils"></span></span>'
        f'<div class="ui-hero-h" role="heading" aria-level="1">{html.escape(title)}</div></div>'
        f'<div class="ui-hero-bar"></div><p class="ui-hero-sub">{html.escape(subtitle)}</p>'
        f'<div class="ui-stats">{chips}</div>{note_html}</div></div>',
        unsafe_allow_html=True,
    )


def preview_card(kcal: int, slot_kcal: list[tuple[str, int]], per_meal: int, note: str) -> None:
    """入力しながら見える目安（目標kcal・朝昼夜のkcal・1食あたりの予算）。"""
    slots = "".join(f'<div class="ui-pv-s">{html.escape(n)}<b>{v:,}</b></div>' for n, v in slot_kcal)
    st.markdown(
        f'<div class="ui-tint"><div class="ui-pv-k">{kcal:,}<span>kcal / 日の目標</span></div>'
        f'<div class="ui-pv-slots">{slots}</div>'
        f'<div class="ui-pv-row"><span>1食あたりの予算</span><b>{per_meal:,}円</b></div>'
        f'<p class="ui-pv-note">{html.escape(note)}</p></div>',
        unsafe_allow_html=True,
    )


def feature_cards(items: list[tuple[str, str, str]]) -> None:
    """機能の案内カード。items は (アイコン名, 見出し, 補足) のリスト。"""
    cards = "".join(
        f'<div class="ui-feat"><span class="ui-i ui-i-{icon}"></span>'
        f'<div><b>{html.escape(t)}</b><span class="s">{html.escape(sub)}</span></div></div>'
        for icon, t, sub in items
    )
    st.markdown(f'<div class="ui-feats">{cards}</div>', unsafe_allow_html=True)

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
    "home": '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>',
    "chart": '<line x1="18" x2="18" y1="20" y2="10"/><line x1="12" x2="12" y1="20" y2="4"/><line x1="6" x2="6" y1="20" y2="14"/>',
    "book": '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
    "wallet": '<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/>'
              '<path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/>',
    "check": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    "activity": '<path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "minus": '<circle cx="12" cy="12" r="10"/><path d="M8 12h8"/>',
    "plus": '<circle cx="12" cy="12" r="10"/><path d="M8 12h8"/><path d="M12 8v8"/>',
    "help": '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
    "flame": '<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/>',
    "moon": '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    "bell": '<path d="M3 20a1 1 0 0 1-1-1v-1a1 1 0 0 1 1-1h18a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1Z"/><path d="M20 16a8 8 0 1 0-16 0"/><path d="M12 4v4"/><path d="M10 4h4"/>',
    "soup": '<path d="M12 21a9 9 0 0 0 9-9H3a9 9 0 0 0 9 9Z"/><path d="M7 21h10"/><path d="M19.5 12 22 6"/><path d="M16.25 3c.27.1.8.53.75 1.36-.06.83-.93 1.2-1 2.02-.05.78.34 1.24.73 1.62"/><path d="M11.25 3c.27.1.8.53.74 1.36-.05.83-.93 1.2-.98 2.02-.06.78.33 1.24.72 1.62"/><path d="M6.25 3c.27.1.8.53.75 1.36-.06.83-.93 1.2-1 2.02-.05.78.34 1.24.74 1.62"/>',
    "pot": '<path d="M2 12h20"/><path d="M20 12v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-8"/><path d="m4 8 16-4"/><path d="m8.86 6.78-.45-1.81a2 2 0 0 1 1.45-2.43l1.94-.48a2 2 0 0 1 2.43 1.46l.45 1.8"/>',
    "coins": '<circle cx="8" cy="8" r="6"/><path d="M18.09 10.37A6 6 0 1 1 10.34 18"/><path d="M7 6h1v4"/><path d="m16.71 13.88.7.71-2.82 2.82"/>',
}


def _mask_uri(inner: str) -> str:
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#000" '
           'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + inner + "</svg>")
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


_CSS = """
<style>
.block-container { max-width: none; padding: 4.5rem clamp(1rem, 3vw, 3.5rem) 3rem; }  /* 画面幅に追従。上は固定ヘッダー（Deploy の帯）に隠れない余白 */

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
.ui-feats { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: .6rem; margin: .4rem 0 1.2rem; }
.ui-feat { display: flex; gap: .7rem; align-items: center; border: 1px solid rgba(128, 128, 128, .25);
           border-radius: 12px; padding: .7rem .9rem; }
.ui-feat .ui-i { width: 1.4rem; height: 1.4rem; color: __ACCENT__; flex: 0 0 auto; }
.ui-feat b { display: block; font-size: .9rem; }
.ui-feat span.s { font-size: .75rem; opacity: .7; }

/* 結果のバナー（最安の金額を大きく見せる） */
.ui-result { display: flex; align-items: center; gap: 1rem; margin: .4rem 0 1rem; padding: 1.1rem 1.3rem;
             border-radius: 16px; border: 1px solid rgba(242, 103, 79, .35);
             background: linear-gradient(120deg, rgba(242, 103, 79, .16), rgba(242, 103, 79, .04)); }
.ui-result .ui-i { width: 2.2rem; height: 2.2rem; color: __ACCENT__; flex: 0 0 auto; }
.ui-result-l { font-size: 1rem; opacity: .8; }
.ui-result-v { font-size: 2.2rem; font-weight: 800; line-height: 1.2; color: __ACCENT__; }
.ui-result-v span { font-size: 1.1rem; margin-left: .2rem; }
.ui-result-s { font-size: .95rem; opacity: .8; }

/* 朝・昼・夜の献立カード */
.ui-meals { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: .7rem; margin: .6rem 0 1rem; }
.ui-meal { border: 1px solid rgba(128, 128, 128, .25); border-radius: 14px; padding: .9rem 1rem;
           background: rgba(128, 128, 128, .06); display: flex; flex-direction: column; gap: .45rem; }
.ui-meal-top { display: flex; justify-content: space-between; align-items: center; }
.ui-meal-slot { font-size: 1.05rem; font-weight: 800; color: __ACCENT__; }
.ui-chip { font-size: .8rem; font-weight: 700; padding: .15rem .6rem; border-radius: 999px; }
.ui-chip-cook { background: rgba(27, 175, 122, .16); color: #1baf7a; }
.ui-chip-out { background: rgba(70, 130, 230, .16); color: #4b8ef0; }
.ui-chip-none { background: rgba(128, 128, 128, .18); color: inherit; }
.ui-chip-est { background: rgba(230, 160, 40, .18); color: #c98a12; margin-left: .3rem; }
.ui-meal-name { font-size: 1.15rem; font-weight: 700; line-height: 1.4; }
.ui-meal-meta { display: flex; flex-wrap: wrap; gap: .3rem .9rem; font-size: .95rem; opacity: .8; }
.ui-meal-meta b { font-weight: 700; }

/* サイドバー：アイコンを上、ラベルを下に並べたナビ（上から ホーム／提案／好み登録／分析／自作レシピ） */
@media (min-width: 768px) {
  [data-testid="stSidebar"]:not([aria-expanded="false"]) { width: 92px !important; min-width: 92px !important; }
}
[data-testid="stSidebarNavItems"] { padding: .4rem .25rem; gap: .3rem; align-items: stretch; }
[data-testid="stSidebarNavLinkContainer"] { width: 100%; }
[data-testid="stSidebarNavLink"] { display: flex !important; flex-direction: column; align-items: center;
    width: 100%; box-sizing: border-box;
    justify-content: center; gap: .3rem; padding: .65rem .1rem !important; border-radius: 16px; text-align: center;
    text-decoration: none; transition: background .15s; }
[data-testid="stSidebarNavLink"]:hover { background: rgba(242, 103, 79, .10); }
[data-testid="stSidebarNavLink"]::before { content: ""; display: block; width: 1.7rem; height: 1.7rem;
    background-color: currentColor; opacity: .75;
    -webkit-mask: var(--nav-m) center / contain no-repeat; mask: var(--nav-m) center / contain no-repeat; }
[data-testid="stSidebarNavLink"] span { font-size: .74rem !important; line-height: 1.3; white-space: normal;
    word-break: keep-all; overflow-wrap: anywhere; }
[data-testid="stSidebarNavLink"][aria-current="page"] { background: rgba(242, 103, 79, .18); color: __ACCENT__; }
[data-testid="stSidebarNavLink"][aria-current="page"]::before { opacity: 1; }
[data-testid="stSidebarNavLink"][aria-current="page"] span { font-weight: 800; color: __ACCENT__; }
/* 1つ目は app.py（表示名が "app"）なので「ホーム」に差し替える */
[data-testid="stSidebarNavItems"] > :nth-child(1) [data-testid="stSidebarNavLink"] span { font-size: 0 !important; }
[data-testid="stSidebarNavItems"] > :nth-child(1) [data-testid="stSidebarNavLink"]::after { content: "ホーム";
    font-size: .74rem; line-height: 1.3; font-weight: inherit; white-space: nowrap; }
__NAV_ICON_RULES__

/* ---- トップ画面：条件入力（キー付きの要素だけに効かせ、他ページの見た目は変えない） ---- */
.ui-field { display: flex; align-items: center; gap: .6rem; margin: .9rem 0 .45rem; font-weight: 700; font-size: 1.1rem; }
.ui-field > .ui-i { width: 1.45rem; height: 1.45rem; color: __ACCENT__; }
.ui-field .ui-help { display: inline-flex; opacity: .55; cursor: help; }
.ui-field .ui-help .ui-i { width: 1.1rem; height: 1.1rem; }
.ui-steptag { display: inline-flex; align-items: center; gap: .4rem; min-width: 5.2rem; font-size: .9rem;
              opacity: .9; white-space: nowrap; }
.ui-steptag .ui-i { width: 1.25rem; height: 1.25rem; }
.ui-steptag-inc .ui-i { color: __ACCENT__; }
[class*="st-key-dec_"], [class*="st-key-inc_"] { flex: 1 1 0; min-width: 4rem; }
[class*="st-key-dec_"] button, [class*="st-key-inc_"] button { min-height: 2.4rem; padding: .1rem .3rem;
    border-radius: 999px; font-size: 1rem; font-weight: 600; width: 100%; }
[class*="st-key-dec_"] button p, [class*="st-key-inc_"] button p { font-size: 1rem; font-weight: 600; }
[class*="st-key-inc_"] button { color: __ACCENT__; border-color: rgba(242, 103, 79, .55); background: rgba(242, 103, 79, .06); }

/* 性別・身体活動レベルの選択ボタン（Streamlit は kind 属性で種類を分けている） */
:is(.st-key-sex_sel, .st-key-act_sel) [data-testid="stButtonGroup"] { gap: .6rem; overflow: visible; }
:is(.st-key-sex_sel, .st-key-act_sel) button[kind="segmented_control"], :is(.st-key-sex_sel, .st-key-act_sel) button[kind="segmented_controlActive"] {
    flex: 1 1 0; min-height: 3.2rem; position: relative; border-radius: 14px; overflow: visible; }
:is(.st-key-sex_sel, .st-key-act_sel) button[kind="segmented_control"] p, :is(.st-key-sex_sel, .st-key-act_sel) button[kind="segmented_controlActive"] p {
    font-size: 1.1rem; font-weight: 700; }
:is(.st-key-sex_sel, .st-key-act_sel) button[kind="segmented_controlActive"] { border-color: __ACCENT__;
    background: rgba(242, 103, 79, .10); color: __ACCENT__; }
:is(.st-key-sex_sel, .st-key-act_sel) button[kind="segmented_controlActive"]::after { content: "✓"; position: absolute;
    top: 50%; right: .9rem; transform: translateY(-50%); width: 1.35rem; height: 1.35rem; border-radius: 50%;
    background: __ACCENT__; color: #fff; font-size: .8rem; display: flex; align-items: center; justify-content: center; }
.st-key-confirm button { min-height: 3.3rem; font-size: 1.2rem; border-radius: 16px;
    background: linear-gradient(100deg, #ff8a6b, __ACCENT__ 55%, #d9412c); }
.st-key-confirm button p { font-size: 1.2rem; font-weight: 700; }

/* 金額・時間の入力欄：大きな数字を中央に出し、単位は右に。内蔵の＋−矢印はボタンがあるので隠す */
.st-key-budget_v input, .st-key-prep_v input { font-size: 2rem; font-weight: 800; text-align: center;
    padding: .5rem 2.8rem .5rem .5rem; height: auto; line-height: 1.2; }
.st-key-budget_v [data-testid="stNumberInputContainer"], .st-key-prep_v [data-testid="stNumberInputContainer"] {
    position: relative; border-radius: 14px; }
.st-key-budget_v [data-testid="stNumberInputContainer"]::after { content: "円"; }
.st-key-prep_v [data-testid="stNumberInputContainer"]::after { content: "分"; }
.st-key-budget_v [data-testid="stNumberInputContainer"]::after, .st-key-prep_v [data-testid="stNumberInputContainer"]::after {
    position: absolute; right: .9rem; top: 50%; transform: translateY(-50%); font-size: 1.05rem; opacity: .75;
    pointer-events: none; }
.st-key-budget_v [data-testid="stNumberInputStepUp"], .st-key-budget_v [data-testid="stNumberInputStepDown"],
.st-key-prep_v [data-testid="stNumberInputStepUp"], .st-key-prep_v [data-testid="stNumberInputStepDown"] { display: none; }

/* バナーの数字カード（アイコン付き）／目安カード（リッチ表示。左のカードと同じ高さにそろえる） */
.ui-stats + .ui-hero-note { margin-top: .8rem; }
.ui-stat-with { display: flex; align-items: center; gap: .8rem; }
.ui-stat-with > .ui-i { width: 2rem; height: 2rem; color: #fff; opacity: .9; flex: 0 0 auto; }
.ui-pv-head { display: flex; align-items: center; gap: .9rem; }
.ui-pv-badge { width: 50px; height: 50px; border-radius: 15px; background: rgba(242, 103, 79, .14); color: __ACCENT__;
               display: flex; align-items: center; justify-content: center; flex: 0 0 auto; }
.ui-pv-badge .ui-i { width: 1.8rem; height: 1.8rem; }
.ui-pv-sh { display: flex; align-items: center; gap: .5rem; margin-bottom: .25rem; }
.ui-pv-sh .ui-i { width: 1.3rem; height: 1.3rem; opacity: .8; }
.ui-pv-s small { font-size: .78rem; font-weight: 400; opacity: .8; }
.ui-pv-s b { white-space: nowrap; }
.ui-pv-row .ui-pv-lab { display: flex; align-items: center; gap: .5rem; font-weight: 700; }
.ui-pv-row .ui-pv-lab .ui-i { width: 1.5rem; height: 1.5rem; }
.ui-rich { display: flex; flex-direction: column; padding: 1.4rem 1.5rem; height: 100%; box-sizing: border-box; }
.ui-rich .ui-pv-k { font-size: 2.3rem; }
.ui-rich .ui-pv-k span { font-size: 1rem; }
.ui-rich .ui-pv-slots { margin: 1.2rem 0; gap: .7rem; }
.ui-rich .ui-pv-s { font-size: .95rem; padding: .65rem .7rem; border-radius: 12px; }
.ui-rich .ui-pv-s b { font-size: 1.2rem; }
.ui-rich .ui-pv-row { font-size: 1rem; padding-bottom: .9rem; }
.ui-rich .ui-pv-row b { font-size: 1.3rem; }
.ui-rich .ui-pv-note { font-size: .95rem; margin-top: auto; }
/* 目安カードのある列を、横に並んだ左の列と同じ高さまで伸ばす（途中の入れ物もすべて伸ばす） */
[data-testid="stHorizontalBlock"]:has(.ui-rich) { align-items: stretch !important; }
[data-testid="stHorizontalBlock"]:has(.ui-rich) > [data-testid="stColumn"]:has(.ui-rich) { align-self: stretch !important; }
[data-testid="stColumn"]:has(.ui-rich) *:has(.ui-rich), [data-testid="stColumn"] > .ui-rich { height: 100% !important; }
.ui-rich { min-height: 100%; }
</style>
"""

# 提案ページ用の CSS（larger_text() で入れる。提案ページだけに効く）
# 見やすさ優先：背景のグラデーションをやめて単色に、文字は薄くせず濃く・少し大きくする
_LARGE_CSS = """
<style>
/* 文字サイズ（全体を少し大きく） */
.block-container [data-testid="stMarkdownContainer"] p,
.block-container [data-testid="stMarkdownContainer"] li { font-size: 1.15rem; }
[data-testid="stMetricValue"] [data-testid="stMarkdownContainer"] p { font-size: inherit !important; }
[data-testid="stAlertContainer"] p { font-size: 1.12rem; }
[data-testid="stProgress"] p { font-size: 1.12rem; font-weight: 600; }
[data-testid="stExpander"] summary p { font-size: 1.15rem; font-weight: 700; }
[data-baseweb="tab"] p { font-size: 1.2rem; font-weight: 700; }

/* 注釈（caption）：薄い表示をやめる */
[data-testid="stCaptionContainer"] { opacity: 1 !important; }
.block-container [data-testid="stCaptionContainer"] p { font-size: 1.05rem; line-height: 1.7; }

/* 総コストなどの数字カード */
[data-testid="stMetric"] { background: rgba(128, 128, 128, .10); border: 1px solid rgba(128, 128, 128, .3);
                           border-radius: 14px; padding: .9rem 1.1rem; }
[data-testid="stMetricLabel"] p { font-size: 1.1rem !important; font-weight: 700; }
[data-testid="stMetricValue"] { font-size: 2.1rem; font-weight: 800; }

/* 上のバナー：グラデーションをやめて単色に。文字は白で濃く */
.ui-hero { background: #1f2535 !important; box-shadow: none; }
.ui-badge { background: __ACCENT__ !important; box-shadow: none; }
.ui-hero-sub { color: #fff !important; font-size: 1.12rem; }
.ui-hero-note { color: #fff !important; }
.ui-stat { background: #2e3649; }
.ui-stat-l { color: #e8ecf4 !important; font-size: 1rem; font-weight: 600; }
.ui-stat-v { font-size: 1.5rem; }

/* 最安の金額のカード：単色に、文字を濃く */
.ui-result { background: rgba(242, 103, 79, .10) !important; border-width: 2px; }
.ui-result-l { opacity: 1; font-size: 1.15rem; font-weight: 700; }
.ui-result-v { font-size: 2.6rem; }
.ui-result-v span { font-size: 1.25rem; }
.ui-result-s { opacity: 1; font-size: 1.08rem; }

/* 献立カード */
.ui-meal { background: rgba(128, 128, 128, .10); border-color: rgba(128, 128, 128, .35); }
.ui-meal-slot { font-size: 1.25rem; }
.ui-chip { font-size: .95rem; }
.ui-meal-name { font-size: 1.3rem; }
.ui-meal-meta { opacity: 1; font-size: 1.1rem; }

/* 見出し */
.ui-section { font-size: 1.5rem; margin-top: 1.4rem; }

/* グラフの文字：灰色をやめて本文と同じ濃い色に */
[data-testid="stPlotlyChart"] .main-svg text { fill: currentColor !important; }
</style>
"""


@st.cache_data
def _image_css() -> str:
    """バナー右側の写真（assets/hero.jpg）を CSS の背景にする。ファイルがなければ何も出さない。"""
    try:
        data = base64.b64encode(HERO_IMAGE.read_bytes()).decode()
    except OSError:
        return ""
    return f'<style>.ui-hero-img {{ background-image: url("data:image/jpeg;base64,{data}"); }}</style>'


def _theme_css() -> str:
    rules = "\n".join(f'.ui-i-{name} {{ --m: url("{_mask_uri(inner)}"); }}' for name, inner in _ICONS.items())
    nav = ["home", "utensils", "heart", "chart", "book"]  # サイドバーの並び順に対応
    nav_rules = "\n".join(
        f'[data-testid="stSidebarNavItems"] > :nth-child({i}) [data-testid="stSidebarNavLink"] '
        f'{{ --nav-m: url("{_mask_uri(_ICONS[name])}"); }}' for i, name in enumerate(nav, 1))
    return (_CSS.replace("__ICON_RULES__", rules).replace("__NAV_ICON_RULES__", nav_rules)
            .replace("__ACCENT__", ACCENT) + _image_css())


def apply_theme() -> None:
    """共通の CSS を入れる。各ページで1回だけ呼ぶ。"""
    st.markdown(_theme_css(), unsafe_allow_html=True)


def larger_text() -> None:
    """提案ページの見た目を見やすくする（背景を単色に、文字を濃く・大きく）。apply_theme の後に呼ぶ。"""
    st.markdown(_LARGE_CSS.replace("__ACCENT__", ACCENT), unsafe_allow_html=True)


def hero(title: str, subtitle: str, note: str | None = None, image: bool = True, compact: bool = False,
         icon: str = "utensils") -> None:
    """ページ上部のバナー。HTML は1行にまとめる（空行や字下げがあると、Markdown が崩す）。"""
    note_html = f'<p class="ui-hero-note">ⓘ {html.escape(note)}</p>' if note else ""
    img_html = '<div class="ui-hero-img"></div>' if (image and HERO_IMAGE.exists()) else ""
    cls = "ui-hero ui-hero-compact" if compact else "ui-hero"
    st.markdown(
        f'<div class="{cls}"><div class="ui-hero-body"><div class="ui-hero-title">'
        f'<span class="ui-badge"><span class="ui-i ui-i-{icon}"></span></span>'
        f'<div class="ui-hero-h" role="heading" aria-level="1">{html.escape(title)}</div></div>'
        f'<div class="ui-hero-bar"></div><p class="ui-hero-sub">{html.escape(subtitle)}</p>{note_html}'
        f"</div>{img_html}</div>",
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str, icon: str = "utensils") -> None:
    """トップ以外のページの見出し（写真なしの小さいバナー）。icon は _ICONS のキー。"""
    hero(title, subtitle, image=False, compact=True, icon=icon)


def section(title: str, icon: str) -> None:
    """カードの見出し。icon は _ICONS のキー（"user", "sliders", "wallet" など）。"""
    st.markdown(
        f'<div class="ui-section"><span class="ui-ico"><span class="ui-i ui-i-{icon}"></span></span>'
        f"<span>{html.escape(title)}</span></div>",
        unsafe_allow_html=True,
    )


def hero_stats(title: str, subtitle: str, stats: list[tuple], note: str | None = None) -> None:
    """数字つきバナー。stats は (ラベル, 値, 強調するか[, アイコン名]) のリスト。"""
    def _chip(item) -> str:
        l, v, hi, *rest = item
        text = (f'<div><div class="ui-stat-l">{html.escape(l)}</div>'
                f'<div class="ui-stat-v{" ui-stat-hi" if hi else ""}">{html.escape(v)}</div></div>')
        if rest and rest[0]:  # アイコン名があるときだけ、アイコン付きにする
            return f'<div class="ui-stat ui-stat-with"><span class="ui-i ui-i-{rest[0]}"></span>{text}</div>'
        return f'<div class="ui-stat">{text}</div>'

    chips = "".join(_chip(item) for item in stats)
    note_html = f'<p class="ui-hero-note">ⓘ {html.escape(note)}</p>' if note else ""
    st.markdown(
        f'<div class="ui-hero ui-hero-compact"><div class="ui-hero-body"><div class="ui-hero-title">'
        f'<span class="ui-badge"><span class="ui-i ui-i-utensils"></span></span>'
        f'<div class="ui-hero-h" role="heading" aria-level="1">{html.escape(title)}</div></div>'
        f'<div class="ui-hero-bar"></div><p class="ui-hero-sub">{html.escape(subtitle)}</p>'
        f'<div class="ui-stats">{chips}</div>{note_html}</div></div>',
        unsafe_allow_html=True,
    )


def preview_card(kcal: int, slot_kcal: list[tuple[str, int]], per_meal: int, note: str, rich: bool = False) -> None:
    """入力しながら見える目安（目標kcal・朝昼夜のkcal・1食あたりの予算）。rich=True でアイコン付き。"""
    if rich:
        icons = ["soup", "bell", "moon"]  # 朝・昼・夜
        slots = "".join(
            f'<div class="ui-pv-s"><div class="ui-pv-sh"><span class="ui-i ui-i-{icons[i % 3]}"></span>'
            f'<span>{html.escape(n)}</span></div><b>{v:,}<small> kcal</small></b></div>'
            for i, (n, v) in enumerate(slot_kcal)
        )
        st.markdown(
            f'<div class="ui-tint ui-rich"><div class="ui-pv-head"><span class="ui-pv-badge"><span class="ui-i ui-i-flame"></span></span>'
            f'<div class="ui-pv-k">{kcal:,}<span>kcal / 日の目標</span></div></div>'
            f'<div class="ui-pv-slots">{slots}</div>'
            f'<div class="ui-pv-row"><span class="ui-pv-lab"><span class="ui-i ui-i-utensils"></span>1食あたりの予算</span>'
            f'<b>{per_meal:,}円</b></div><p class="ui-pv-note">{html.escape(note)}</p></div>',
            unsafe_allow_html=True,
        )
        return
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


def result_banner(label: str, value: str, unit: str, sub: str) -> None:
    """結果の金額を大きく見せるバナー。"""
    st.markdown(
        f'<div class="ui-result"><span class="ui-i ui-i-check"></span><div>'
        f'<div class="ui-result-l">{html.escape(label)}</div>'
        f'<div class="ui-result-v">{html.escape(value)}<span>{html.escape(unit)}</span></div>'
        f'<div class="ui-result-s">{html.escape(sub)}</div></div></div>',
        unsafe_allow_html=True,
    )


_CHIP_CLASS = {"自炊": "ui-chip-cook", "外食": "ui-chip-out"}


def meal_cards(meals: list[dict]) -> None:
    """朝・昼・夜の献立カード。meals は slot, type, name, cost, prep, kcal（任意で est＝推定バッジの文字）を持つ dict のリスト。"""
    cards = "".join(
        f'<div class="ui-meal"><div class="ui-meal-top"><span class="ui-meal-slot">{html.escape(m["slot"])}</span>'
        f'<span><span class="ui-chip {_CHIP_CLASS.get(m["type"], "ui-chip-none")}">{html.escape(m["type"])}</span>'
        + (f'<span class="ui-chip ui-chip-est">{html.escape(m["est"])}</span>' if m.get("est") else "")
        + '</span></div>'
        f'<div class="ui-meal-name">{html.escape(m["name"])}</div>'
        f'<div class="ui-meal-meta"><span><b>{m["cost"]:,.0f}</b>円</span><span><b>{m["prep"]:.0f}</b>分</span>'
        f'<span><b>{m["kcal"]:,.0f}</b> kcal</span></div></div>'
        for m in meals
    )
    st.markdown(f'<div class="ui-meals">{cards}</div>', unsafe_allow_html=True)


def field_label(text: str, icon: str, help: str | None = None) -> None:
    """入力欄の見出し（アイコン＋文字。help があれば ? マークにカーソルを乗せると表示）。"""
    h = (f'<span class="ui-help" title="{html.escape(help, quote=True)}"><span class="ui-i ui-i-help"></span></span>'
         if help else "")
    st.markdown(
        f'<div class="ui-field"><span class="ui-i ui-i-{icon}"></span><span>{html.escape(text)}</span>{h}</div>',
        unsafe_allow_html=True,
    )


def step_tag(kind: str) -> None:
    """増減ボタンの行頭ラベル。kind は "dec"（減らす）か "inc"（増やす）。"""
    icon, text = ("minus", "減らす") if kind == "dec" else ("plus", "増やす")
    st.markdown(f'<span class="ui-steptag ui-steptag-{kind}"><span class="ui-i ui-i-{icon}"></span>{text}</span>',
                unsafe_allow_html=True)


# 好き度ページ専用の CSS（このページだけで呼ぶ）
_LIKES_CSS = """
<style>
.lk-prog { display: flex; align-items: flex-end; justify-content: space-between; gap: 1rem; margin: .4rem 0 1rem; }
.lk-prog-l small { display: block; font-size: .9rem; opacity: .7; }
.lk-prog-l b { font-size: 1.8rem; font-weight: 800; }
.lk-prog-l span { margin-left: .3rem; opacity: .75; }
.lk-prog-r { width: min(320px, 45%); text-align: right; }
.lk-pct { font-size: 1.35rem; font-weight: 800; }
.lk-bar { height: 8px; border-radius: 999px; background: rgba(128, 128, 128, .25); overflow: hidden; margin-top: .3rem; }
.lk-bar > i { display: block; height: 100%; border-radius: 999px; background: __ACCENT__; }
.lk-title { font-size: 1.4rem; font-weight: 800; padding-top: .3rem; }
.lk-name { display: flex; justify-content: space-between; align-items: flex-start; gap: .6rem;
           font-size: 1.15rem; font-weight: 800; line-height: 1.45; }
.lk-name .ui-i { width: 1.3rem; height: 1.3rem; color: #1baf7a; flex: 0 0 auto; margin-top: .15rem; }
.lk-meta { display: flex; align-items: center; flex-wrap: wrap; gap: .5rem; margin: .5rem 0 .4rem; font-size: .95rem; opacity: .9; }
.lk-chip { display: inline-flex; align-items: center; gap: .3rem; padding: .15rem .65rem; border-radius: 999px;
           background: rgba(128, 128, 128, .22); font-weight: 700; font-size: .85rem; }
.lk-chip .ui-i { width: 1rem; height: 1rem; }
.lk-label { font-size: .9rem; opacity: .7; margin-top: -.2rem; }
/* 黄色の上に濃い文字（白背景・ダーク背景のどちらでも読める。コントラスト比 約8.8:1） */
.lk-label.on { display: inline-block; background: #f5b301; color: #2b1d1a; opacity: 1; font-weight: 700;
               padding: .1rem .6rem; border-radius: 999px; }
[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 18px; }
</style>
"""

LIKE_LABELS = {1: "好まない", 2: "あまり好きではない", 3: "普通", 4: "好き", 5: "とても好き"}


def likes_css() -> None:
    st.markdown(_LIKES_CSS.replace("__ACCENT__", ACCENT), unsafe_allow_html=True)


def likes_progress(done: int, total: int) -> None:
    """評価の進捗（「1 / 4 品目」と割合のバー）。"""
    pct = int(done / total * 100) if total else 0
    st.markdown(
        f'<div class="lk-prog"><div class="lk-prog-l"><small>評価の進捗</small><b>{done} / {total}</b><span>品目</span></div>'
        f'<div class="lk-prog-r"><div class="lk-pct">{pct}%</div><div class="lk-bar"><i style="width:{pct}%"></i></div></div></div>',
        unsafe_allow_html=True,
    )


def like_card_head(name: str, kind: str, detail: str, done: bool) -> None:
    """料理カードの上半分（名前・区分・費用）。評価済みなら右上にチェックを出す。"""
    check = '<span class="ui-i ui-i-check"></span>' if done else ""
    st.markdown(
        f'<div class="lk-name"><span>{html.escape(name)}</span>{check}</div>'
        f'<div class="lk-meta"><span class="lk-chip"><span class="ui-i ui-i-utensils"></span>{html.escape(kind)}</span>'
        f'<span>{html.escape(detail)}</span></div>',
        unsafe_allow_html=True,
    )


def like_label(score: int | None) -> None:
    """星の下の文字（未評価／とても好き など）。"""
    if score:
        st.markdown(f'<div class="lk-label on">{LIKE_LABELS[score]}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="lk-label">未評価</div>', unsafe_allow_html=True)

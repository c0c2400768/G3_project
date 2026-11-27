"""最適化の関数（アプリから使う版）。

optimize.ipynb（assign_slots, optimize）と sensitivity.ipynb（build_nutrition_target,
nutrition_adequacy）の関数を、そのまま .py にしたもの。ノートブックは変えていない。
変更点は optimize の on_progress（進捗の通知）だけ。
上位5案の optimize_topn は、このファイルで新しく追加した。
"""
import numpy as np
import pandas as pd

SLOTS = ("morning", "lunch", "dinner")  # 食事の枠（朝・昼・夜の順）
EPS = 1e-9  # 小数の誤差で境界値を落とさないための微小値


def apply_cooking_overhead(meals_df, utility_yen, shop_min):
    """自炊の行に、光熱費（円/食）を費用へ、買い物時間（分/食）を準備時間へ足した表を返す。外食は変えない。

    何度呼んでも二重に足さないよう、足した値を utility_yen・shop_min 列に持ち、前の値を引いてから足し直す。
    ロス率を掛け直す apply_loss（sensitivity.ipynb）は utility_yen 列を足し戻すので、順番はどちらでもよい。
    """
    out = meals_df.copy()
    cooked = out["type"].eq("自炊")
    old_u = pd.to_numeric(out.get("utility_yen", 0), errors="coerce").fillna(0) if "utility_yen" in out else 0.0
    old_s = pd.to_numeric(out.get("shop_min", 0), errors="coerce").fillna(0) if "shop_min" in out else 0.0
    new_u = np.where(cooked, float(utility_yen), 0.0)
    new_s = np.where(cooked, float(shop_min), 0.0)
    out["cost_yen"] = out["cost_yen"].astype(float) - old_u + new_u
    out["prep_min"] = out["prep_min"].astype(float) - old_s + new_s
    out["utility_yen"] = new_u
    out["shop_min"] = new_s
    return out


def _parse_exclude(value): #形式の統一用関数
    """exclude_slots の1セル（例: "morning,lunch"）を集合にする。空欄は空集合。"""
    # 空欄は CSV では NaN になるので、空文字と合わせて「除外なし」にする
    if pd.isna(value) or str(value).strip() == "":
        return set()
    # カンマで分けて空白を除き、集合にする（後で in 判定しやすい）
    return {s.strip() for s in str(value).split(",") if s.strip()}


def assign_slots(meals_df, kcal_target, slot_ratio, slot_tol): #朝昼夜判断の関数
    """meals_df に can_morning / can_lunch / can_dinner 列（bool）を足して返す。

    kcal が「kcal_target × slot_ratio[枠]」の ±slot_tol（割合）に入り、
    かつ exclude_slots にその枠が含まれない場合に True。
    入力: meals_df（kcal 列は必須、exclude_slots 列は任意）、kcal_target（kcal/日）
    """
    out = meals_df.copy()  # 元の表は書き換えない

    # 手で除外する枠（行ごとの集合）。列がなければ全行「除外なし」
    if "exclude_slots" in out.columns:
        excluded = out["exclude_slots"].map(_parse_exclude)
    else:
        excluded = pd.Series([set()] * len(out), index=out.index)

    for slot in SLOTS:
        target = kcal_target * slot_ratio[slot]  # この枠の目標kcal
        # kcal が 目標±(slot_tol×目標) の範囲内か
        within = (out["kcal"] - target).abs() <= slot_tol * target + EPS
        # 範囲内 かつ 除外されていない（~ は反転、slot=slot はループ変数の固定）
        out[f"can_{slot}"] = within & ~excluded.map(lambda s, slot=slot: slot in s)
    return out


def _update_best(best, mask, primary, secondary, i, cand_j, cand_k): # 昼×夜の最良の組を更新する関数
    """mask を満たす組のうち (primary, secondary) が最小のものに best を更新する。

    best は (primary, secondary, (i, j, k)) または None。同点は先に見つけた方を残す。
    """
    # 条件を満たす組が1つもなければ、更新せず返す
    if not mask.any():
        return best
    # 条件を満たさない組は inf にして、最小値の対象から外す
    p = np.where(mask, primary, np.inf)
    # 第1キー（コストなど）の最小値
    p_min = p.min()
    # 第1キーが最小の組だけ残し、第2キーで比べる
    s = np.where(mask & (primary <= p_min + EPS), secondary, np.inf)
    # 最小の組の位置（昼の番号, 夜の番号）
    jj, kk = np.unravel_index(np.argmin(s), s.shape)
    s_min = s[jj, kk]
    # これまでより良ければ更新。同点なら更新しない（先に見つけた方を残す）
    if best is None or (p_min, s_min) < (best[0], best[1]):
        return (p_min, s_min, (i, cand_j[jj], cand_k[kk]))
    return best



def optimize(meals_df, budget_yen, max_prep_min, nutrition_target, aux_nutrients=(), on_progress=None): # 1日分の最適化関数
    """1日分（朝・昼・夜）の最小コストの組み合わせを全探索で選ぶ。

    入力
      meals_df: meals.csv の列 + can_morning / can_lunch / can_dinner 列（assign_slots の出力）。
                金額は円、時間は分、栄養は kcal / g / mg。
                recipe_id 列（任意）があれば、同じ recipe_id の食事は1日に2回選ばない。
      budget_yen: 1日の予算（円）。合計コストがこれ以下。
      max_prep_min: 1日の準備時間の合計の上限（分）。
      nutrition_target: 制約にする栄養 {列名: (下限, 上限)}。None は制限なし。
        例: {"kcal": (2000, 2400), "protein_g": (65, None)}
      aux_nutrients: 制約に入れず、合計だけ表示する栄養の列名のリスト（補助項目）。
      on_progress: 進捗を受け取る関数 f(割合)。朝の候補を1件調べるごとに呼ぶ（任意）。
    探索
      朝・昼・夜の候補から1食ずつ、3食とも別の食事になる組み合わせをすべて調べる。
      「別の食事」は recipe_id が違うこと（recipe_id 列がなければ meal_id が違うこと）。
      同じレシピの倍率違い（R101_x1.0 と R101_x1.3 など）は、1日に2回選ばない。
      同コストなら準備時間が短い方、それも同じなら meals_df の並びが早い方を選ぶ。
    戻り値（dict）
      feasible: bool
      selected: 選ばれた3食の DataFrame（slot 列つき）。解なしは None。
      total_cost: 合計コスト（円）。解なしは None。
      totals: 1日の合計（cost_yen, prep_min, 制約項目, 補助項目）。解なしは None。
      slot_counts: 枠ごとの候補数。
      reason: 解ありは None。解なしは次の dict
        slot_empty: 候補が0件の枠のリスト
        budget: 予算だけ外したときの最小コスト（円）。それでも解がなければ None
        prep_time: 準備時間の上限だけ外したときに必要な最小の準備時間（分）。同上
        nutrition: 栄養制約だけ外すと解が出るなら True
        multiple_constraints: どの1条件を外しても解が出ない（複数が同時に厳しい）なら True
    """
    # 行番号を0から振り直す（位置で参照するため）
    df = meals_df.reset_index(drop=True)
    # 制約にする栄養の列名
    keys = list(nutrition_target)
    # 列を NumPy 配列にする（一括計算のため）
    cost = df["cost_yen"].to_numpy(float)
    prep = df["prep_min"].to_numpy(float)
    # 栄養の配列（食事 × 栄養項目）
    nut = df[keys].to_numpy(float) if keys else np.zeros((len(df), 0))
    # 栄養の下限（None は -∞ ＝ 制限なし）
    lo = np.array(
        [-np.inf if nutrition_target[k][0] is None else nutrition_target[k][0] for k in keys]
    )
    # 栄養の上限（None は +∞ ＝ 制限なし）
    hi = np.array(
        [np.inf if nutrition_target[k][1] is None else nutrition_target[k][1] for k in keys]
    )

    # 「同じ食事」の判定キー。recipe_id 列があればそれ、なければ行番号（＝meal_id ごと）
    grp = df["recipe_id"].to_numpy() if "recipe_id" in df.columns else np.arange(len(df))
    # 枠ごとの候補の行番号
    cand = {s: np.flatnonzero(df[f"can_{s}"].to_numpy(bool)) for s in SLOTS}
    # 枠ごとの候補数
    slot_counts = {s: int(len(cand[s])) for s in SLOTS}
    # 候補が0件の枠
    slot_empty = [s for s in SLOTS if slot_counts[s] == 0]
    # 候補0件の枠があれば、探索せず「解なし」で返す
    if slot_empty:
        # 候補0件の枠がある場合の戻り値
        return {
            "feasible": False,
            "selected": None,
            "total_cost": None,
            "totals": None,
            "slot_counts": slot_counts,
            "reason": {
                "slot_empty": slot_empty,
                "budget": None,
                "prep_time": None,
                "nutrition": False,
                "multiple_constraints": False,
            },
        }

    # 昼と夜の候補（朝は下のループで1つずつ回す）
    cj, ck = cand["lunch"], cand["dinner"]
    # best_all=全条件 / no_budget=予算なし / no_prep=時間なし の最良
    best_all = best_no_budget = best_no_prep = None
    # 栄養だけが原因か（予算・時間だけなら解が出るか）
    nutrition_is_cause = False  # 栄養だけ外すと解が出るか（出れば True）

    # 朝のメニューを1つ固定し、昼×夜の全組をまとめて計算する
    for n_done, i in enumerate(cand["morning"]):
        # 進捗の通知（朝の候補を1つ調べるごと。0〜1の割合。on_progress を渡したときだけ）
        if on_progress is not None:
            on_progress(n_done / len(cand["morning"]))
        # 合計コストの表（行=昼、列=夜）
        c = cost[i] + cost[cj][:, None] + cost[ck][None, :]
        # 合計準備時間の表
        p = prep[i] + prep[cj][:, None] + prep[ck][None, :]
        # 合計栄養の表（昼 × 夜 × 栄養項目）
        tot = nut[i] + nut[cj][:, None, :] + nut[ck][None, :, :]
        # 3食がすべて別の食事か（recipe_id が違う。倍率違いの同じレシピは同じ扱い）
        gi, gj, gk = grp[i], grp[cj], grp[ck]
        distinct = (gj[:, None] != gi) & (gk[None, :] != gi) & (gj[:, None] != gk[None, :])
        # 予算以下か
        ok_b = c <= budget_yen + EPS
        # 準備時間が上限以下か
        ok_p = p <= max_prep_min + EPS
        # 栄養が全項目で下限〜上限に入るか
        ok_n = ((tot >= lo - EPS) & (tot <= hi + EPS)).all(axis=2)

        # 全条件を満たす組の中で、最小コスト（同点は準備時間が短い方）
        best_all = _update_best(best_all, distinct & ok_b & ok_p & ok_n, c, p, i, cj, ck)
        # 予算だけ外した最小コスト ＝ 必要な予算
        best_no_budget = _update_best(best_no_budget, distinct & ok_p & ok_n, c, p, i, cj, ck)
        # 時間だけ外した最小の準備時間 ＝ 必要な時間
        best_no_prep = _update_best(best_no_prep, distinct & ok_b & ok_n, p, c, i, cj, ck)
        # 予算と時間だけで成り立つ組があれば、栄養が原因
        if not nutrition_is_cause:
            nutrition_is_cause = bool((distinct & ok_b & ok_p).any())

    # 解なし：外した条件ごとの結果から理由を作る
    if best_all is None:
        # あと何円（それでも解がなければ None）
        r_budget = None if best_no_budget is None else float(best_no_budget[0])
        # あと何分（それでも解がなければ None）
        r_prep = None if best_no_prep is None else float(best_no_prep[0])
        # 解なしの戻り値（dict）
        return {
            "feasible": False,                 # 解なし
            "selected": None,                  # 選ばれた3食はなし
            "total_cost": None,                # 合計コストもなし
            "totals": None,                    # 1日の合計もなし
            "slot_counts": slot_counts,        # 枠ごとの候補数（原因の手がかり）
            "reason": {
                "slot_empty": [],                  # 候補0件の枠はなし（ここまで来た時点で全枠に候補あり）
                "budget": r_budget,                # 予算だけ外したときの最小コスト（円）。なければ None
                "prep_time": r_prep,               # 時間だけ外したときの最小の準備時間（分）。なければ None
                "nutrition": nutrition_is_cause,   # 栄養だけが原因なら True
                # 予算・時間・栄養のどれを1つ外しても解が出ない＝複数の条件が同時に厳しい
                "multiple_constraints": r_budget is None
                and r_prep is None
                and not nutrition_is_cause,
            },
        }

    # 解あり：選ばれた3食の行番号（朝・昼・夜）
    i, j, k = best_all[2]
    # 表示する列（基本列 + 制約の栄養）
    cols = ["meal_id", "name", "type", "cost_yen", "prep_min"] + keys
    # 補助の栄養項目を足す（重複は除く）
    cols += [a for a in aux_nutrients if a in df.columns and a not in keys]
    # 表に存在しない列は除く
    cols = [c_ for c_ in cols if c_ in df.columns]
    # 選ばれた3食の表
    selected = df.loc[[i, j, k], cols].copy()
    # 先頭に枠名（morning/lunch/dinner）の列を足す
    selected.insert(0, "slot", list(SLOTS))
    selected = selected.reset_index(drop=True)
    # 数値列を合計して1日の合計にする
    totals = selected.drop(columns=["slot", "meal_id", "name", "type"]).sum().to_dict()
    # 解ありの戻り値（dict）
    return {
        "feasible": True,                          # 解あり
        "selected": selected,                      # 選ばれた3食の表（slot 列つき）
        "total_cost": float(totals["cost_yen"]),   # 1日の合計コスト（円）。float にして numpy 型を避ける
        "totals": totals,                          # 1日の合計（コスト・準備時間・栄養）
        "slot_counts": slot_counts,                # 枠ごとの候補数（朝・昼・夜）
        "reason": None,                            # 解ありなので理由はなし
    }



def build_nutrition_target(kcal_target, energy_ratio, kcal_per_g, kcal_tol):
    """目標kcalから、optimize に渡す栄養制約 {列名: (下限, 上限)} を作る。

    入力
      kcal_target: 1日の目標kcal
      energy_ratio: 産熱栄養素の目標量（%エネルギーの範囲）{列名: (下限の割合, 上限の割合)} 例 {"protein_g": (0.13, 0.20)}
      kcal_per_g: 1gあたりのkcal {列名: 数値}（たんぱく質4・脂質9・炭水化物4）
      kcal_tol: kcal の許容幅（割合）。例 0.10 なら目標の±10%
    戻り値: {"kcal": (下限, 上限), 列名: (下限g, 上限g), ...}
    """
    # kcal は目標の ±kcal_tol
    target = {"kcal": (kcal_target * (1 - kcal_tol), kcal_target * (1 + kcal_tol))}
    for col, (lo, hi) in energy_ratio.items():
        per_g = kcal_per_g[col]  # 1gあたりのkcal
        # 「全体kcal × 割合 ÷ 1gあたりkcal」で、割合の範囲を g の範囲に直す
        target[col] = (kcal_target * lo / per_g, kcal_target * hi / per_g)
    return target


def _adequacy_row(nutrient, role, total, lower, upper):
    """充足度の表の1行を作る。"""
    # 基準との割合（%）。下限があれば下限に対して、なければ上限に対して。基準がなければ NaN
    ref = lower if lower is not None else upper
    ratio = np.nan if (ref is None or pd.isna(total)) else total / ref * 100
    # 判定
    if pd.isna(total):
        status = "データなし"      # 合計が出せない（その栄養の列がない）
    elif lower is None and upper is None:
        status = "基準未設定"      # 基準値が決まっていない
    elif lower is not None and total < lower - EPS:
        status = "不足"
    elif upper is not None and total > upper + EPS:
        status = "超過"
    else:
        status = "充足"
    return {"nutrient": nutrient, "role": role, "total": total, "lower": lower, "upper": upper,
            "ratio_pct": ratio, "status": status}


def nutrition_adequacy(totals, nutrition_target, aux_reference):
    """選ばれた1日の栄養合計が、基準に対してどうかを表にする。

    入力
      totals: optimize の戻り値の "totals"（列名 → 1日の合計）
      nutrition_target: 制約にした栄養 {列名: (下限, 上限)}（範囲内なら「充足」）
      aux_reference: 補助項目の基準 {列名: ("min", 値) または ("max", 値) または None}
        "min" は下限（食物繊維など。下回れば「不足」）、"max" は上限（食塩相当量など。超えれば「超過」）
        None は基準未設定
    戻り値（DataFrame、1栄養につき1行）
      nutrient, role（制約／補助）, total, lower, upper,
      ratio_pct（基準に対する割合。下限があれば下限に対して）, status（充足／不足／超過／基準未設定／データなし）
    """
    rows = []
    # 制約にした栄養（範囲で判定）
    for col, (lo, hi) in nutrition_target.items():
        rows.append(_adequacy_row(col, "制約", totals.get(col, np.nan), lo, hi))
    # 補助項目（下限か上限のどちらか1つで判定）
    for col, ref in aux_reference.items():
        if ref is None:
            lo, hi = None, None  # 基準未設定
        else:
            kind, value = ref
            if kind not in ("min", "max"):
                raise ValueError(f'基準の種類は "min" か "max": {col}={kind}')
            lo, hi = (value, None) if kind == "min" else (None, value)
        rows.append(_adequacy_row(col, "補助", totals.get(col, np.nan), lo, hi))
    return pd.DataFrame(rows)


# ---------- 上位5案（このファイルで追加） ----------
LIKE_NEUTRAL = 3  # 好き度の「普通」。未登録の食事はこの値として扱う


def _plan(df, idx, keys, aux_nutrients):
    """選ばれた3食の行番号 idx=(朝, 昼, 夜) から、optimize と同じ形の1案（dict）を作る。"""
    cols = ["meal_id", "name", "type", "cost_yen", "prep_min"] + keys
    cols += [a for a in aux_nutrients if a in df.columns and a not in keys]
    # 自作レシピの表示用の列（あれば付ける）
    cols += [c for c in ("owner", "ai_estimated", "recipe_id") if c in df.columns and c not in cols]
    cols = [c for c in cols if c in df.columns]
    selected = df.loc[list(idx), cols].copy()
    selected.insert(0, "slot", list(SLOTS))
    selected = selected.reset_index(drop=True)
    num = ["cost_yen", "prep_min"] + keys + [a for a in aux_nutrients if a in selected.columns and a not in keys]
    # 空欄（自作レシピの未入力の補助栄養）が1つでもあれば、その合計は NaN（0扱いにしない）
    totals = selected[num].sum(min_count=len(selected)).to_dict()
    return {"selected": selected, "total_cost": float(totals["cost_yen"]), "totals": totals}


def optimize_topn(meals_df, budget_yen, max_prep_min, nutrition_target, aux_nutrients=(),
                  likes=None, lam=0.0, n=5, min_diff=2, on_progress=None):
    """条件を満たす1日の組み合わせを、評価額の小さい順に最大 n 案選ぶ（全探索）。

    評価額 = 総コスト − lam × Σ(好き度 − 3)。好き度は {recipe_id: 1〜5}。未登録は3として扱う。
    lam=0 なら総コストの順（optimize と同じ最小コストが1案目になる）。
    すでに選んだ案と「2食以上違う」ものだけを採用する（min_diff=2）。
    同じ食事かどうかは recipe_id で見る（倍率違いは同じ食事）。評価額が同じなら
    総コスト・準備時間が小さい方を先にする。

    戻り値（dict）
      feasible: bool、plans: 案のリスト（評価額順。各案は selected, total_cost, totals, eval, like_sum）
      slot_counts: 枠ごとの候補数、reason: 解ありは None、解なしは optimize と同じ dict
    on_progress(割合) は、朝の候補を1件調べるごとに呼ぶ。
    """
    df = meals_df.reset_index(drop=True)
    keys = list(nutrition_target)
    cost = df["cost_yen"].to_numpy(float)
    prep = df["prep_min"].to_numpy(float)
    nut = df[keys].to_numpy(float) if keys else np.zeros((len(df), 0))
    lo = np.array([-np.inf if nutrition_target[k][0] is None else nutrition_target[k][0] for k in keys])
    hi = np.array([np.inf if nutrition_target[k][1] is None else nutrition_target[k][1] for k in keys])
    grp = (pd.factorize(df["recipe_id"])[0] if "recipe_id" in df.columns else np.arange(len(df)))
    # 好き度のずれ（好き度 − 3）。likes がなければ全部0
    if likes:
        dev = df["recipe_id"].map(lambda r: likes.get(r, LIKE_NEUTRAL) - LIKE_NEUTRAL).to_numpy(float)
    else:
        dev = np.zeros(len(df))

    cand = {s: np.flatnonzero(df[f"can_{s}"].to_numpy(bool)) for s in SLOTS}
    slot_counts = {s: int(len(cand[s])) for s in SLOTS}

    def _infeasible():
        # 解なしの理由は optimize に任せる（進捗は出さない。解なしのときだけ呼ぶ）
        r = optimize(df, budget_yen, max_prep_min, nutrition_target, aux_nutrients)
        return {"feasible": False, "plans": [], "slot_counts": slot_counts, "reason": r["reason"]}

    if any(slot_counts[s] == 0 for s in SLOTS):
        return _infeasible()

    cj, ck = cand["lunch"], cand["dinner"]
    nm = len(cand["morning"])
    # 朝ごとに残す件数。「すでに選んだ案と2食以上違う」の除外で落ちる案を見込んでも、
    # 上位 n 案が正確になる数（1案が除外するのは、2食以上同じ案＝高々 朝+昼+夜 の候補数ぶん）
    keep = (n - 1) * (nm + len(cj) + len(ck)) + n + 20
    chunks = []  # (評価額, コスト, 準備時間, 朝, 昼, 夜)

    for n_done, i in enumerate(cand["morning"]):
        if on_progress is not None:
            on_progress(n_done / nm)
        c = cost[i] + cost[cj][:, None] + cost[ck][None, :]
        p = prep[i] + prep[cj][:, None] + prep[ck][None, :]
        tot = nut[i] + nut[cj][:, None, :] + nut[ck][None, :, :]
        gi, gj, gk = grp[i], grp[cj], grp[ck]
        distinct = (gj[:, None] != gi) & (gk[None, :] != gi) & (gj[:, None] != gk[None, :])
        mask = (distinct & (c <= budget_yen + EPS) & (p <= max_prep_min + EPS)
                & ((tot >= lo - EPS) & (tot <= hi + EPS)).all(axis=2))
        m = int(mask.sum())
        if m == 0:
            continue
        like_sum = dev[i] + dev[cj][:, None] + dev[ck][None, :]
        ev = np.where(mask, c - lam * like_sum, np.inf).ravel()
        take = min(keep, m)
        idx = np.argpartition(ev, take - 1)[:take] if take < ev.size else np.arange(ev.size)
        idx = idx[np.isfinite(ev[idx])]
        jj, kk = np.unravel_index(idx, mask.shape)
        chunks.append((ev[idx], c.ravel()[idx], p.ravel()[idx], np.full(len(idx), i), cj[jj], ck[kk]))

    if not chunks:
        return _infeasible()

    ev, c_all, p_all, ii, jj, kk = (np.concatenate(x) for x in zip(*chunks))
    # 評価額 → 総コスト → 準備時間 → 並び順 の順で並べる（最後の2つは同点のときの安定化）
    order = np.lexsort((kk, jj, ii, p_all, c_all, ev))

    plans, chosen_sets = [], []
    for o in order:
        triple = (int(ii[o]), int(jj[o]), int(kk[o]))
        meals = {grp[triple[0]], grp[triple[1]], grp[triple[2]]}
        # すでに選んだ案のどれとも、min_diff 食以上違う案だけを採用する
        if all(len(SLOTS) - len(meals & t) >= min_diff for t in chosen_sets):
            plan = _plan(df, triple, keys, aux_nutrients)
            plan["eval"] = float(ev[o])
            plan["like_sum"] = float(dev[list(triple)].sum())
            plans.append(plan)
            chosen_sets.append(meals)
            if len(plans) == n:
                break
    return {"feasible": True, "plans": plans, "slot_counts": slot_counts, "reason": None}

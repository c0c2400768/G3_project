# チーム共通ルール（G3 学生の食事判断支援アプリ）

最終更新：2026-10-23 / 状態：叩き台（実データを見たら更新する）
置き場所：`docs/team_rules.md`

変更ルール：**このファイルを先に直してから、チャットで全員に知らせる。**

---

## 1. 担当（第3・4回）

| 担当者 | 第3回 | 第4回 | 主な担当ファイル |
|---|---|---|---|
| 岩間春弥（リーダー） | 最適化、感度分析 | 最適化、感度分析 | `src/optimize.ipynb`, `src/sensitivity.ipynb`, `src/config.py` |
| 王雲偉 | 外食データの取得法調査 | 調査結果から実施 | `src/prices_out.ipynb` など |
| 高居蒼大 | 価格データ | 栄養レシピ | `src/prices.ipynb`, `src/recipes.ipynb` |
| 北村和弥 | 分析法の確認（全探索） | 分析法調査（全探索） | （専用ファイルなし。`src/brute_force.ipynb` は2026-10-23に削除。最適化の実装は岩間） |

- 第3回終わりに、王さんの調査結果と北村さんの全探索の確認結果を共有する日を決める。
- 規模の見積もり：外食100件（仮）＋自炊30品（仮）で試算済み（第3節）。確定は王さん・高居さんの作業後に更新する。
- レシピは全員で数品ずつ分担し、書式は高居さんが統一・検算する。

---

## 2. データスキーマ

### 共通の単位（固定）
- 金額：円 / 重さ：g / 時間：分 / エネルギー：kcal
- 列名：英語の小文字スネークケース。日本語名は `name` 列に入れる。
- 欠損：空欄のままにする。分析時に除外する場合は画面に明記する。
- 仮定値（外食の準備時間、ロス率など）は `is_assumed` 列で区別する。

### `prices.csv`（食材・外食の価格）作成：高居／外食分は王
| 列 | 内容 |
|---|---|
| item_id | 品目ID |
| name | 品目名（日本語） |
| category | 食材 / 外食 |
| unit | 単位（g, 個 など） |
| price_yen | 価格（円） |
| month | 年月（YYYY-MM） |

### `recipes.csv`（自炊レシピ）作成：高居（全員で分担入力）
| 列 | 内容 |
|---|---|
| recipe_id | レシピID |
| name | 料理名 |
| ingredient | 食材名（`prices.csv` の name と対応） |
| amount_g | 使用量（g） |
| cook_min | 調理時間（分） |
| cleanup_min | 片付け時間（分） |

### `meals.csv`（1食テーブル）★最適化の唯一の入口
作成：高居＋王 / 使う人：岩間、北村
| 列 | 内容 |
|---|---|
| meal_id | 食事ID |
| name | 名前 |
| type | 外食 / 自炊 |
| base_cost_yen | ロス前の費用（自炊=食材費の合計、外食=価格）※案：ロス率の感度分析で `cost_yen` を再計算するため |
| cost_yen | 1食のコスト（自炊は `base_cost_yen ÷ (1−ロス率)`、外食は価格そのまま） |
| prep_min | 準備時間（自炊=調理+片付け、外食=移動+待ち） |
| kcal | エネルギー【制約】 |
| protein_g | たんぱく質【制約】 |
| fat_g | 脂質【制約】 |
| carb_g | 炭水化物【制約】 |
| fiber_g | 食物繊維【補助】 |
| salt_g | 食塩相当量【補助】 |
| calcium_mg | カルシウム【補助】 |
| iron_mg | 鉄【補助】 |
| vitamin_c_mg | ビタミンC【補助】 |
| exclude_slots | その食事を出さない枠（`morning` / `lunch` / `dinner`、複数はカンマ区切り）。空欄＝除外なし |
| is_assumed | 準備時間や栄養が推定・仮定なら true |

- 【制約】は最適化の制約に使う。【補助】は制約に入れず、結果の表示（基準に対する充足度）だけに使う。
- `exclude_slots` は最初から列を用意する。例外の食事にだけ値を入れる（例：ラーメンを朝に出さない）。

最初にリーダーが**ダミーの `meals.csv`（10行程度）**を置く。

---

## 3. 分析設計の決定事項と関数の入出力

### 決定事項（2026-10-16）
- 1日＝朝・昼・夜の3食。**3食とも別の食事**（同じ食事は1日に2回選ばない）。
- 探索は**全探索**（numpy で朝の候補ごとにまとめて計算）。外食の候補は100件で仮置き。
  - 規模の目安：自炊30品（仮）を足して130件なら、枠を分けない場合 C(130,3)=357,760 通り。枠ごとの候補に分けると上限は「朝の候補数×昼×夜」（重複を除くので実際はこれ以下）。
  - **実測（2026-10-16、ランダムデータ、全候補が3枠すべてに入る最悪ケース、1回の optimize）**：K=100で約0.09秒、K=130で約0.15秒、K=200で約0.6秒、K=300で約2.1秒。MILP（scipy の `milp`）は同条件で K=130 約0.06秒、K=300 約0.11秒で、どちらも同じ最小コストになった。測定環境は私の作業環境で、各自のPCでは異なる。
  - **全探索を選ぶ理由**：K=130 で足りる速さ／解なしのとき「予算を何円上げれば」を正確に返せる／仕組みを発表で説明しやすい／追加ライブラリが不要。
  - **MILP に切り替える目安**：枠ごとの候補が200件を超える、または感度分析（optimize を数百回呼ぶ）が1分を超えるとき。感度分析は同じ計算の繰り返しなので、`st.cache_data` などで結果を使い回すことも検討する。
  - 実際は枠の許容幅（±30%）で候補が絞られるので、上の実測より速くなる見込み（推測。実データで確認する）。
- 準備時間の上限：**1日の合計**。
- 栄養項目
  - 制約にする：エネルギー、たんぱく質、脂質、炭水化物。
  - 補助として表示する（制約に入れない）：食物繊維、食塩相当量、カルシウム、鉄、ビタミンC。基準に対する充足度を出し、食塩相当量は上限超過を警告する。
  - 基準値は食事摂取基準（2025年版）の公式資料で確認する：【未確認】。成分表に補助5項目の列があるかも確認する：【未確認】。
- 朝・昼・夜の枠
  - 食事の kcal が「1日の目標 kcal × 配分比」の ±`SLOT_TOL` に入る枠を、その食事の候補にする（複数の枠に入ってよい）。`SLOT_TOL = 0.30`。
  - 配分比 `SLOT_RATIO` は岩間が決める。決めた値と根拠は `docs/` に記録する。
  - `meals.csv` の `exclude_slots` で、例外の食事だけ手で除外する。
- 解なしのとき：予算・準備時間・栄養を1つずつ外して必要な値を返す（下記 `reason`）。

### データの流れ（案）
```
prices.csv + recipes.csv + nutrients.csv + config（ロス率など）
        ↓ build_meals()          担当：高居・王（案）
meals.csv
        ↓ assign_slots()         岩間
meals_df（can_morning / can_lunch / can_dinner 列つき）
        ↓ optimize()             岩間
selected, total_cost, feasible, reason
        ↓ sensitivity 系の関数    岩間（optimize を条件を変えて繰り返し呼ぶ。入出力は下の「感度分析・栄養基準の関数」）
節約額、損益分岐、ヒートマップ用の表、栄養制約あり/なしの差、OATの表
```
`nutrients.csv`（食材ごとの栄養。成分表から作る）の列定義は高居さんが作成後に追記する：【未決】

### `config.py`（案）
```python
SLOT_RATIO = {"morning": None, "lunch": None, "dinner": None}  # 岩間が決める（合計1）
SLOT_TOL = 0.30
CONSTRAINT_NUTRIENTS = ["kcal", "protein_g", "fat_g", "carb_g"]
AUX_NUTRIENTS = ["fiber_g", "salt_g", "calcium_mg", "iron_mg", "vitamin_c_mg"]
LOSS_RATE = None  # 【決める】感度分析で動かす範囲も別に持つ
```

### 関数

```python
# src/optimize.ipynb（関数として定義する。教授の指示により src 内は .ipynb）
def assign_slots(meals_df, kcal_target, slot_ratio, slot_tol):
    """
    meals_df に can_morning / can_lunch / can_dinner 列（bool）を足して返す。
    kcal が「kcal_target × slot_ratio[枠]」の ±slot_tol に入り、
    かつ exclude_slots にその枠が含まれない場合に True。
    """

def optimize(meals_df, budget_yen, max_prep_min, nutrition_target):
    """
    入力: meals_df は meals.csv の列 + can_* 列を持つ DataFrame（単位は上記の通り）
          budget_yen: 1日の予算（円）
          max_prep_min: 1日の準備時間の合計の上限（分）
          nutrition_target: 制約にする栄養の辞書。(下限, 上限) で渡し、None は制限なし
            例: {"kcal": (2000, 2400), "protein_g": (65, None), ...}
    探索: 朝・昼・夜の候補から1食ずつ、3食とも別の食事になる組み合わせを全探索し、
          予算・準備時間・栄養の制約を満たすうち総コスト最小のものを選ぶ。
    戻り値: dict
        {"feasible": bool,
         "selected": DataFrame（slot, meal_id, name, type, cost_yen, prep_min, 栄養）,
         "total_cost": 円,
         "totals": 1日の栄養合計（制約項目と補助項目）,
         "reason": None（解あり）、または解なしの理由 dict}
    解なしの reason:
        {"budget": 予算だけ外したときの最小コスト（解が出ない場合は None）,
         "prep_time": 時間だけ外したときの案の準備時間（同上）,
         "nutrition": 栄養だけ外すと解が出る場合 True,
         "slot_empty": 候補が0件の枠のリスト}
    """
```

- 引数は DataFrame と数値・辞書だけ。**`st.`（Streamlit）は `app.py` 以外で呼ばない。**
- 解なしは例外ではなく `feasible=False` と `reason` で返す。
- 関数には docstring で入力の列名と単位を書く。
- 各ノートブックは「上から順に実行して最後まで通る」状態にする。関数の定義セルと、ダミーデータでの動作確認セルを分ける（後で `.py` に移すとき、定義セルだけ取り出せる）。
- 共通の仮定値は `src/config.py`（値だけの `.py`）に置く。ノートブックから `import config` で読む。
- **フェーズ（教授の意図：分析フェーズだけ `.ipynb`）**
  - 第3〜6回（企画・データ分析）：`src/` 内は `.ipynb` で作る。
  - 第7回（設計）以降：各自が自分のノートブックの関数定義セルを `.py` に書き出し、`src/` に置く。`app.py` はその `.py` を `import` する。移行は各自が自分の担当ファイルで行う（案）。
  - 移行時に困らないよう、関数定義セルには `st.` を書かず、セル間で変数を共有しない（引数と戻り値だけで渡す）。

### 感度分析・栄養基準の関数（`src/sensitivity.ipynb`、2026-10-23 追加）

`optimize()` を条件を変えて繰り返し呼ぶ側。`optimize.ipynb` の関数定義セルだけを読み込んで使う（第7回に `.py` へ移したら `from optimize import ...` に置き換える）。引数と戻り値だけで渡し、`st.` は使わない。

```python
# --- 表を作り直す（元の表は書き換えない） ---
def apply_loss(meals_df, loss_rate): ...        # 自炊の cost_yen を base_cost_yen ÷ (1−ロス率) にする。外食は変えない
def apply_cook_time(meals_df, factor): ...      # 自炊の prep_min を factor 倍にする。外食は変えない

# --- 外食のみ・節約額 ---
def eatout_baseline(meals_slot, budget_yen, nutrition_target, aux_nutrients=()): ...
    # 外食だけで組んだ最小コスト。準備時間は制約なし。戻り値は optimize と同じ dict
def savings(best, baseline, days_week=7, days_month=30): ...
    # 戻り値 dict: feasible, eatout_cost, best_cost, per_day, per_week, per_month（円）。どちらかが解なしなら feasible=False

# --- 損益分岐・ヒートマップ ---
def breakeven_curve(meals_slot, budget_yen, prep_grid, nutrition_target): ...
    # 戻り値 DataFrame: max_prep_min, feasible, total_cost, prep_used, n_cooked, meal_ids, eatout_cost
def switch_points(curve): ...
    # 戻り値 dict: first_feasible_prep, crossover_prep（外食のみより安くなり始める上限）, switch_preps（組み合わせが入れ替わる上限のリスト）
def loss_prep_grid(meals_slot, budget_yen, prep_grid, loss_grid, nutrition_target): ...
    # 戻り値 DataFrame: loss_rate, max_prep_min, feasible, total_cost, saving_per_day, n_cooked

# --- 栄養制約の差・OAT感度分析 ---
def nutrition_cost_gap(meals_slot, budget_yen, max_prep_min, nutrition_target): ...
    # 戻り値 dict: with_nutrition, without_nutrition（optimize の戻り値）, cost_with, cost_without, gap_yen
def oat_sensitivity(meals_slot, budget_yen, nutrition_target, base, grids): ...
    # base = {"max_prep_min", "loss_rate", "cook_factor"}、grids = 動かす値の辞書
    # 戻り値 DataFrame: parameter, value, feasible, total_cost, base_cost, change_yen, saving_per_day, n_cooked, meal_ids

# --- 栄養の基準値（制約と充足度） ---
def build_nutrition_target(kcal_target, energy_ratio, kcal_per_g, kcal_tol): ...
    # 目標kcalと%エネルギーの範囲から、optimize に渡す {列名: (下限, 上限)} を作る
def nutrition_adequacy(totals, nutrition_target, aux_reference): ...
    # 戻り値 DataFrame: nutrient, role（制約/補助）, total, lower, upper, ratio_pct, status（充足/不足/超過/基準未設定/データなし）

# --- 可視化（Plotly の Figure を返す） ---
def plot_breakeven(curve, switches=None): ...
def plot_heatmap(grid, value="saving_per_day"): ...
def plot_savings(sv): ...
```

決めたこと
- **外食のみの基準**は、準備時間を制約にしない（損益分岐の水平線を上限によらず一定にするため）。外食だけでは条件を満たせないときは NaN にして、グラフには出さない。
- **損益分岐**は2つ出す：①外食のみより安くなり始める準備時間の上限、②選ばれる3食の組み合わせが入れ替わる上限。値は `prep_grid` の刻みの値。
- **OAT**は、基準の条件から1つずつ動かす（他は基準のまま）。動かすのは準備時間の上限・ロス率・調理時間の倍率。
- **meals.csv に必要な列**：`type`（「外食」「自炊」）、`base_cost_yen`、`cost_yen`、`prep_min`。`build_meals()` が `cost_yen` を作るときのロス率（`config.LOSS_RATE`）を、OAT の `base["loss_rate"]` に渡す。
- **栄養制約の作り方**：kcal は目標の±`KCAL_TOL`、たんぱく質・脂質・炭水化物は%エネルギーの範囲を g に直す（`config.ENERGY_RATIO`、1gあたりのkcalは `config.KCAL_PER_G`）。補助5項目の基準は `config.AUX_REFERENCE`（未確認のうちは None＝「基準未設定」と表示する）。
- **目標kcal**は `config.KCAL_TABLE`（食事摂取基準2025年版・18〜29歳の表。性別×身体活動レベルで選ぶ）。基礎代謝×身体活動レベルの計算式は、時間の余裕が出来次第の追加項目。

`config.py` に追加した値：`KCAL_TABLE`, `ENERGY_RATIO`, `KCAL_PER_G`, `KCAL_TOL`, `AUX_REFERENCE`, `LOSS_GRID`, `PREP_GRID`, `COOK_FACTOR_GRID`（`LOSS_GRID`・`PREP_GRID`・`COOK_FACTOR_GRID`・`KCAL_TOL` は仮案で根拠なし）。

---

## 4. コード規約

- Python のバージョンを揃える（Community Cloud で選べるバージョンは公式で確認：【未確認】）。
- フォーマッタは Black。VS Code の保存時整形を全員 ON にする。
- 命名：関数・変数は `snake_case`、定数は `UPPER_CASE`。
- 仮定値（ロス率、準備時間、調理時間の範囲）は `src/config.py` に集約し、コードに直書きしない。
- `requirements.txt` はバージョン固定（例：`pandas==2.2.3`）。追加時はチャットで一言伝える。

---

## 5. 作業・公開の運用（VS Code Live Share）

- ブランチ運用・PR レビューは行わない。作業は Live Share で行う。
- 同じファイルを同時に編集しない。**担当ファイルを分ける**（第1節の表）。共有ファイル（`requirements.txt`、`docs/team_rules.md`、`src/config.py`）を変えるときは、先にチャットで一言伝える。
- Live Share のファイルは**ホストの PC 上にある**。ホストを固定する：【決める】
- GitHub への commit / push は**ホストが担当**し、区切りごとに行う（Community Cloud への公開に GitHub が必要なため）。
- 作業が終わったら、**ゲストが書いた内容がホストの PC に保存されているか**を確認してから終了する。

### フォルダ構成
```
data/            加工済みデータ（ライセンス確認後）
data/raw/        生データ（コミットしない）
docs/            このファイル、出典メモ、決定事項
src/             各担当の分析ノートブック（.ipynb）と config.py
app.py           Streamlit（後で統合）
requirements.txt
.gitignore
```

### .gitignore に入れるもの
`.streamlit/secrets.toml`、`data/raw/`、`.venv/`、`__pycache__/`

### 秘密情報
- e-Stat の appId などは `.streamlit/secrets.toml`（ローカル）と Community Cloud の Secrets に置く。**GitHub に書かない。**一度コミットすると履歴に残る。
- **ノートブックは push 前に出力を消す**（VS Code の「Clear All Outputs」）。出力には生データの表や、appId を表示したセルの結果が残り、`data/raw/` を除外しても GitHub に出てしまう。
- ノートブックの中に appId などを直接書かない。

---

## 6. 出典・ライセンス

- 画面と資料に出典と「加工して作成」を明記する（e-Stat、日本食品標準成分表、食事摂取基準）。
- 成分表などの利用条件は公式ページで確認する：【未確認】
- 外食データを別ソースで補う場合は、取得元とライセンスを先に確認する。
- アンケートで個人情報を取らない。

---

## 7. 最初の1回でやること（リーダー）

1. リポジトリ作成、フォルダ構成、`.gitignore`
2. このファイルを `docs/` に置く
3. ダミーの `meals.csv` を置く
4. 全員で15分、ルールを読んで不明点を解消する

---

## 8. 未決事項

- [ ] 外食の候補100件が実際にそろうか（小売物価統計は約20品目。補強方法は王さんの調査後に決定）
- [ ] 自炊レシピの品数（仮に30品で試算。高居さんの作業後に確定）
- [ ] 準備時間・ロス率・調理時間の現実的な範囲と根拠
- [ ] `SLOT_RATIO`（配分比）の値と根拠（岩間）
- [ ] 食事摂取基準（2025年版）の基準値と、成分表に補助5項目の列があるかの確認
- [ ] 外食の枠ごとの候補数（実データで確認。朝の外食が少ない可能性）
- [ ] `nutrients.csv` の列定義、`build_meals()` の担当（`sensitivity` 系の入出力は上の節で決定済み）
- [ ] 炭水化物の%エネルギー範囲（`ENERGY_RATIO`。2025年版で未確認）、`KCAL_TOL`、`LOSS_GRID`・`PREP_GRID`・`COOK_FACTOR_GRID` の範囲と根拠（仮案）
- [ ] Python のバージョン
- [ ] Live Share のホスト（push 担当）
- [ ] 第7回の `.ipynb` → `.py` 移行の進め方（各自が自分の分を移す案でよいか）

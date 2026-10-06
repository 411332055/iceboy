# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas"]
# ///
"""
把 data/ 裡的三個 CSV 整理成網頁可以直接載入的 docs/data.js。

用法：
  uv run work/build_data.py

docs/data.js 定義一個全域變數 BI_DATA，用 <script src="data.js"> 載入，
不需要伺服器（直接雙擊 index.html 就能用）。

為了讓檔案小一點，資料用「字典 + 索引」的方式存：
  BI_DATA.semesters / colleges / degrees / genders / reasons 是字典
  BI_DATA.depts       = [{name, college, aliases}]  （college 是 colleges 的索引）
  BI_DATA.enrollment  = [[學期, 學院, 系所, 學位別, 性別, 在學人數], ...]
  BI_DATA.leave       = [[學期, 學院, 系所, 學位別, 性別, 休學原因, 學期間休學, 學期底休學狀態], ...]
  每一列的前幾欄都是對應字典的索引。
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "docs" / "data.js"

DEGREES = ["學士", "碩士", "博士"]
GENDERS = ["女", "男"]


def main():
    enr = pd.read_csv(DATA / "enrollment.csv", encoding="utf-8-sig")
    lea = pd.read_csv(DATA / "leave.csv", encoding="utf-8-sig")
    mp = pd.read_csv(DATA / "dept_mapping.csv", encoding="utf-8-sig").fillna({"aliases": ""})

    semesters = sorted(set(enr.semester) | set(lea.semester), key=lambda s: tuple(map(int, s.split("-"))))
    colleges = list(dict.fromkeys(mp.college))
    depts = list(mp.dept)
    reasons = (lea[["reason", "reason_group"]].drop_duplicates()
               .sort_values(["reason_group", "reason"], ascending=[False, True]))  # 自請休學在前

    # 每個系所都要在對照表裡，學院也要一致
    for name, df in (("enrollment", enr), ("leave", lea)):
        pairs = df[["dept", "college"]].drop_duplicates()
        bad = pairs.merge(mp[["dept", "college"]], how="left", on="dept", suffixes=("", "_map"))
        bad = bad[bad.college != bad.college_map]
        assert bad.empty, f"{name} 有系所不在對照表或學院不一致：\n{bad}"

    idx = lambda values: {v: i for i, v in enumerate(values)}
    i_sem, i_col, i_dept = idx(semesters), idx(colleges), idx(depts)
    i_deg, i_gen, i_rea = idx(DEGREES), idx(GENDERS), idx(reasons.reason)

    # 先加總：去掉網頁用不到的 dept_raw、program_raw、identity
    keys = ["semester", "college", "dept", "degree", "gender"]
    e = enr.groupby(keys, as_index=False)["count"].sum()
    l = lea.groupby(keys + ["reason"], as_index=False)[["new_leave", "on_leave_end"]].sum()
    l = l[(l.new_leave > 0) | (l.on_leave_end > 0)]

    def encode(r):
        return [i_sem[r.semester], i_col[r.college], i_dept[r.dept], i_deg[r.degree], i_gen[r.gender]]

    data = {
        "semesters": semesters,
        "colleges": colleges,
        "depts": [{"name": r.dept, "college": i_col[r.college],
                   "aliases": [a for a in r.aliases.split(";") if a]} for r in mp.itertuples()],
        "degrees": DEGREES,
        "genders": GENDERS,
        "reasons": [{"name": r.reason, "group": r.reason_group} for r in reasons.itertuples()],
        "enrollmentFields": ["semester", "college", "dept", "degree", "gender", "count"],
        "enrollment": [encode(r) + [int(r.count)] for r in e.itertuples()],
        "leaveFields": ["semester", "college", "dept", "degree", "gender", "reason", "new_leave", "on_leave_end"],
        "leave": [encode(r) + [i_rea[r.reason], int(r.new_leave), int(r.on_leave_end)] for r in l.itertuples()],
    }

    # 核對：加總前後人數不變
    assert sum(r[-1] for r in data["enrollment"]) == enr["count"].sum()
    assert sum(r[-2] for r in data["leave"]) == lea.new_leave.sum()
    assert sum(r[-1] for r in data["leave"]) == lea.on_leave_end.sum()
    total_1141 = sum(r[-1] for r in data["enrollment"] if semesters[r[0]] == "114-1")
    assert total_1141 == 10035, f"114-1 在學人數合計 {total_1141}，應為 10035"

    OUT.parent.mkdir(exist_ok=True)
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    OUT.write_text("// 由 work/build_data.py 從 data/*.csv 產生，請勿手動修改\n"
                   f"window.BI_DATA = {body};\n", encoding="utf-8")

    print(f"→ {OUT.relative_to(ROOT)}：{OUT.stat().st_size / 1024:.1f} KB")
    print(f"  學期 {len(semesters)} 個：{semesters[0]} ~ {semesters[-1]}")
    print(f"  學院 {len(colleges)} 個、系所 {len(depts)} 個、休學原因 {len(reasons)} 種")
    print(f"  在學人數 {len(data['enrollment'])} 列（原 {len(enr)} 列）")
    print(f"  休學人數 {len(data['leave'])} 列（原 {len(lea)} 列）")
    print(f"  ✅ 114-1 在學人數合計 {total_1141}")


if __name__ == "__main__":
    main()

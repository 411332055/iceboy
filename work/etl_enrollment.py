# /// script
# requires-python = ">=3.10"
# dependencies = ["xlrd", "pandas"]
# ///
"""
把 114-1 在學學生人數統計表（.xls）轉成整齊的 CSV。

用法：
  uv run work/etl_enrollment.py
輸出：
  work/enrollment_114-1.csv（UTF-8 with BOM）
欄位：college, dept_raw, program_raw, gender, count
"""
import re
from pathlib import Path

import pandas as pd
import xlrd

ROOT = Path(__file__).resolve().parent.parent
SRC = next((ROOT / "東華大學統計資料" / "在學人數統計表").glob("114-1*.xls"))
OUT = ROOT / "work" / "enrollment_114-1.csv"

# 報表欄位位置（第 2、3 列是表頭）
COL_SECTION, COL_COLLEGE, COL_DEPT, COL_GROUP = 0, 1, 2, 3
COL_FEMALE, COL_MALE = 5, 6  # 「總計」底下的女、男

# 區段標題（第 0 欄的「xxx 合計N」）對應到學制
SECTIONS = {"博士班": "博士班", "碩士班": "碩士班", "碩專班": "碩士在職專班", "學士班": "學士班"}


def text(v) -> str:
    return str(v).strip()


def fill_merged(sh: xlrd.sheet.Sheet, col: int) -> list[str]:
    """回傳某一欄每列的值：合併儲存格只有第一格有字，把它填到整個合併範圍。"""
    vals = [text(sh.cell_value(r, col)) for r in range(sh.nrows)]
    for r0, r1, c0, c1 in sh.merged_cells:
        if c0 <= col < c1:
            for r in range(r0 + 1, r1):
                vals[r] = vals[r0]
    return vals


def main():
    book = xlrd.open_workbook(SRC, formatting_info=True)  # formatting_info 才讀得到合併儲存格
    sh = book.sheet_by_index(0)
    colleges = fill_merged(sh, COL_COLLEGE)
    depts = fill_merged(sh, COL_DEPT)

    rows, program, college, dept = [], None, None, None
    for r in range(3, sh.nrows):
        head = re.sub(r"\s+", "", str(sh.cell_value(r, COL_SECTION)))
        if head.startswith("備註"):
            break  # 下方是備註，結束
        if "合計" in head or "總計" in head:
            program = next((p for k, p in SECTIONS.items() if head.startswith(k)), None)
            college = dept = None  # 新的學制區段，學院與系所重新開始
            continue
        if program is None or not text(sh.cell_value(r, COL_GROUP)):
            continue
        college = colleges[r] or college
        dept = depts[r] or dept
        group = text(sh.cell_value(r, COL_GROUP))
        # 報表漏合併：「應用物理博士班一般組」的系所格是空的，又不在合併範圍內，
        # 往上沿用會被算成材料系；應用物理的各組都屬於物理學系
        if not depts[r] and group.startswith("應用物理"):
            dept = "物理學系"
        for gender, col in (("女", COL_FEMALE), ("男", COL_MALE)):
            v = sh.cell_value(r, col)
            rows.append(dict(college=college, dept_raw=dept, program_raw=program,
                             gender=gender, count=int(v) if v != "" else 0))

    df = pd.DataFrame(rows)
    df["college"] = df["college"].map(lambda s: re.sub(r"[（(].*?[)）]", "", s).strip())
    # 同一系所、同一學制下的多個分組加總成一列
    df = (df.groupby(["college", "dept_raw", "program_raw", "gender"], sort=False, as_index=False)["count"].sum())
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"{SRC.name} → {OUT.relative_to(ROOT)}：{len(df)} 列，總人數 {df['count'].sum()}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Inspect old headerless XLSX lab files so the PHM team can confirm which column is the result value.

Usage:
    python tools/inspect_old_lab_schema.py raw/old_a1c.xlsx
"""
from __future__ import annotations

import argparse
import re
import statistics
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import List, Iterator

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def parse_float(value):
    if value is None:
        return None
    s = str(value).strip().replace(",", "")
    m = re.search(r"[-+]?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None


def load_shared_strings(z):
    ss=[]
    if "xl/sharedStrings.xml" not in z.namelist():
        return ss
    root=ET.fromstring(z.read("xl/sharedStrings.xml"))
    for si in root.findall(NS+"si"):
        ss.append("".join(t.text or "" for t in si.iter(NS+"t")))
    return ss


def iter_xlsx_rows(path: Path) -> Iterator[List[str]]:
    with zipfile.ZipFile(path) as z:
        ss=load_shared_strings(z)
        sheet="xl/worksheets/sheet1.xml"
        if sheet not in z.namelist():
            sheet=sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml"))[0]
        with z.open(sheet) as f:
            for event, elem in ET.iterparse(f, events=("end",)):
                if elem.tag != NS+"row":
                    continue
                vals=[]; last=0
                for c in elem.findall(NS+"c"):
                    ref=c.attrib.get("r","")
                    m=re.match(r"([A-Z]+)",ref)
                    col=0
                    if m:
                        for ch in m.group(1): col=col*26+ord(ch)-64
                    while last < col-1:
                        vals.append(""); last+=1
                    value=""
                    v=c.find(NS+"v")
                    if v is not None and v.text is not None:
                        value=v.text
                    if c.attrib.get("t")=="s" and value:
                        value=ss[int(value)]
                    vals.append(value); last=col
                yield vals
                elem.clear()


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--rows", type=int, default=20000)
    args=ap.parse_args()
    path=Path(args.file)
    cols=[]
    total=0
    for i,row in enumerate(iter_xlsx_rows(path)):
        if i == 0 and all(not str(x).strip() for x in row):
            continue
        total+=1
        while len(cols)<len(row): cols.append([])
        for j,val in enumerate(row):
            if str(val).strip(): cols[j].append(str(val).strip())
        if total>=args.rows: break
    print(f"File: {path}")
    print(f"Rows inspected: {total:,}")
    for i,values in enumerate(cols):
        if not values:
            print(f"col {i}: empty")
            continue
        nums=[parse_float(v) for v in values]
        nums=[n for n in nums if n is not None]
        common=Counter(values).most_common(5)
        if nums:
            print(f"col {i}: filled={len(values):,}, unique={len(set(values)):,}, min={min(nums):.2f}, median={statistics.median(nums):.2f}, max={max(nums):.2f}, examples={common}")
        else:
            print(f"col {i}: filled={len(values):,}, unique={len(set(values)):,}, examples={common}")

if __name__ == "__main__":
    main()

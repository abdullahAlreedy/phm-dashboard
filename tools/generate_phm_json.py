#!/usr/bin/env python3
"""
Generate a safe Population Health Management dashboard JSON from local FAMCO exports.

Security model:
- Raw CSV/XLSX files stay inside ./raw on your local computer.
- The output JSON uses masked patient IDs only.
- Do not upload raw files to GitHub.
- Review output JSON before publishing it publicly.

Usage:
    python tools/generate_phm_json.py --config tools/config_rules.json

Optional:
    python tools/generate_phm_json.py --raw-dir /path/to/raw --output data/phm_dashboard_safe.json
    PHM_ID_SALT="your-long-secret" python tools/generate_phm_json.py
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import hmac
import json
import math
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RISK_ORDER = {"Red": 0, "Yellow": 1, "Green": 2}

# -----------------------------
# Generic parsing helpers
# -----------------------------

def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def norm_id(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip().replace("\ufeff", "")
    if not s or s.upper() in {"NULL", "N/A", "NONE", "NAN"}:
        return None
    if re.fullmatch(r"\d+\.0", s):
        s = s[:-2]
    return s


def parse_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    s = str(value).strip().replace(",", "")
    if not s or s.upper() in {"NULL", "N/A", "NONE", "NAN"}:
        return None
    # Examples: "<5", ">400", "7.2 %", "67.3"
    m = re.search(r"[-+]?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def excel_date_to_date(value: Any) -> Optional[dt.date]:
    n = parse_float(value)
    if n is None:
        return None
    # Excel serial date origin used by Excel for Windows.
    if 20000 <= n <= 60000:
        try:
            return (dt.datetime(1899, 12, 30) + dt.timedelta(days=n)).date()
        except Exception:
            return None
    return None


def parse_date(value: Any) -> Optional[dt.date]:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    excel_dt = excel_date_to_date(value)
    if excel_dt:
        return excel_dt
    s = str(value).strip()
    if not s or s.upper() in {"NULL", "N/A", "NONE", "NAN"}:
        return None
    # Date of Birth/Age format: 01/01/1961 (64Y)
    s = s.split("(")[0].strip()
    s = s.replace("T", " ")
    for fmt in (
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
    ):
        try:
            return dt.datetime.strptime(s[:26], fmt).date()
        except ValueError:
            pass
    m = re.search(r"(\d{4}-\d{2}-\d{2})", s)
    if m:
        try:
            return dt.datetime.strptime(m.group(1), "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def days_between(later: dt.date, earlier: Optional[dt.date]) -> Optional[int]:
    if not earlier:
        return None
    return (later - earlier).days


def fmt_date(value: Optional[dt.date]) -> Optional[str]:
    return value.isoformat() if value else None


def parse_bp(bp: Any) -> Tuple[Optional[int], Optional[int]]:
    if bp is None:
        return None, None
    s = str(bp).strip()
    if not s or s.upper() in {"NULL", "N/A", "NONE", "NAN"}:
        return None, None
    m = re.search(r"(\d{2,3})\s*/\s*(\d{2,3})", s)
    if not m:
        return None, None
    sys_bp, dia_bp = int(m.group(1)), int(m.group(2))
    if not (50 <= sys_bp <= 260 and 30 <= dia_bp <= 160):
        return None, None
    return sys_bp, dia_bp


def masked_patient_id(raw_id: str, salt: str) -> str:
    digest = hmac.new(salt.encode("utf-8"), raw_id.encode("utf-8"), hashlib.sha256).hexdigest()
    return "PHM-" + digest[:10].upper()


def safe_int(value: Any) -> Optional[int]:
    n = parse_float(value)
    return int(n) if n is not None and not math.isnan(n) else None


def latest(existing: Optional[Dict[str, Any]], value: Optional[float], date_value: Optional[dt.date]) -> Optional[Dict[str, Any]]:
    if value is None:
        return existing
    if existing is None:
        return {"value": value, "date": date_value}
    old_date = existing.get("date")
    if date_value and (old_date is None or date_value >= old_date):
        return {"value": value, "date": date_value}
    if old_date is None and date_value is None:
        return {"value": value, "date": date_value}
    return existing


def csv_dict_rows(path: Path) -> Iterator[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield {str(k).replace("\ufeff", "").strip(): (v if v is not None else "") for k, v in row.items()}


# -----------------------------
# Minimal XLSX reader, no external packages
# -----------------------------

def _load_shared_strings(z: zipfile.ZipFile) -> List[str]:
    ss: List[str] = []
    if "xl/sharedStrings.xml" not in z.namelist():
        return ss
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    for si in root.findall(NS + "si"):
        texts = []
        for t in si.iter(NS + "t"):
            texts.append(t.text or "")
        ss.append("".join(texts))
    return ss


def _first_sheet_path(z: zipfile.ZipFile) -> str:
    # Most exports use sheet1.xml. Keep a fallback for unusual workbooks.
    if "xl/worksheets/sheet1.xml" in z.namelist():
        return "xl/worksheets/sheet1.xml"
    candidates = sorted([name for name in z.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")])
    if not candidates:
        raise FileNotFoundError("No worksheet XML found in XLSX")
    return candidates[0]


def iter_xlsx_rows(path: Path) -> Iterator[List[str]]:
    with zipfile.ZipFile(path) as z:
        shared = _load_shared_strings(z)
        sheet_path = _first_sheet_path(z)
        with z.open(sheet_path) as f:
            for event, elem in ET.iterparse(f, events=("end",)):
                if elem.tag != NS + "row":
                    continue
                row_vals: List[str] = []
                last_col = 0
                for c in elem.findall(NS + "c"):
                    ref = c.attrib.get("r", "")
                    m = re.match(r"([A-Z]+)", ref)
                    col = 0
                    if m:
                        for ch in m.group(1):
                            col = col * 26 + ord(ch) - 64
                    while last_col < col - 1:
                        row_vals.append("")
                        last_col += 1
                    cell_type = c.attrib.get("t")
                    v = c.find(NS + "v")
                    value = "" if v is None or v.text is None else v.text
                    if cell_type == "s" and value != "":
                        try:
                            value = shared[int(value)]
                        except Exception:
                            pass
                    elif cell_type == "inlineStr":
                        texts = [t.text or "" for t in c.iter(NS + "t")]
                        value = "".join(texts)
                    row_vals.append(value)
                    last_col = col
                yield row_vals
                elem.clear()


def xlsx_dict_rows(path: Path) -> Iterator[Dict[str, str]]:
    rows = iter_xlsx_rows(path)
    try:
        header = next(rows)
    except StopIteration:
        return
    clean_header = [str(h).replace("\ufeff", "").strip() for h in header]
    for row in rows:
        out: Dict[str, str] = {}
        for idx, name in enumerate(clean_header):
            if not name:
                continue
            out[name] = row[idx] if idx < len(row) else ""
        yield out


# -----------------------------
# PHM build engine
# -----------------------------

def new_patient() -> Dict[str, Any]:
    return {
        "birth_date": None,
        "age": None,
        "gender": None,
        "evidence": set(),
        "diagnosis_diabetes": False,
        "labs": {},
        "fbs_high_dates": set(),
        "last_bp": None,
        "high_bp_count": 0,
        "bmi": None,
        "bmi_date": None,
        "last_appointment": None,
        "missed_12m": 0,
        "urgent_12m": 0,
        "admission_recent": 0,
    }


def patient_store() -> defaultdict:
    return defaultdict(new_patient)


def update_demo(patient: Dict[str, Any], birth_date: Optional[dt.date] = None, age: Optional[int] = None, gender: Optional[str] = None, as_of: Optional[dt.date] = None) -> None:
    if birth_date and not patient.get("birth_date"):
        patient["birth_date"] = birth_date
    if gender and not patient.get("gender"):
        patient["gender"] = gender
    if age is not None and not patient.get("age"):
        patient["age"] = age
    if patient.get("age") is None and patient.get("birth_date") and as_of:
        bd = patient["birth_date"]
        patient["age"] = as_of.year - bd.year - ((as_of.month, as_of.day) < (bd.month, bd.day))


def resolve_path(raw_dir: Path, filename: Optional[str]) -> Optional[Path]:
    if not filename:
        return None
    p = Path(filename)
    if p.is_absolute():
        return p
    return raw_dir / filename


def process_appointments(path: Path, patients: defaultdict, as_of: dt.date, source_rows: Dict[str, int]) -> set:
    active_ids = set()
    if not path.exists():
        return active_ids
    for row in csv_dict_rows(path):
        source_rows["appointment"] += 1
        pid = norm_id(row.get("URN"))
        if not pid:
            continue
        active_ids.add(pid)
        p = patients[pid]
        update_demo(p, parse_date(row.get("DOB")), safe_int(row.get("Age Year")), row.get("Gender"), as_of)
        appt_date = parse_date(row.get("Appointment Date")) or parse_date(row.get("Booked Date"))
        if appt_date and (p["last_appointment"] is None or appt_date > p["last_appointment"]):
            p["last_appointment"] = appt_date
        status = (row.get("Appointment Status") or "").strip().lower()
        if appt_date and 0 <= (as_of - appt_date).days <= 365 and "not attended" in status:
            p["missed_12m"] += 1
    return active_ids


def process_diagnoses(path: Path, patients: defaultdict, as_of: dt.date, config: Dict[str, Any], source_rows: Dict[str, int]) -> None:
    if not path.exists():
        return
    prefixes = tuple(config["diabetes_rules"]["diagnosis_code_prefixes"])
    text_re = re.compile(config["diabetes_rules"]["diagnosis_text_regex"], re.I)
    for row in csv_dict_rows(path):
        source_rows["diagnosis"] += 1
        pid = norm_id(row.get("Patient No"))
        if not pid:
            continue
        p = patients[pid]
        update_demo(p, parse_date(row.get("Birth Date")), safe_int(row.get("Age")), row.get("Gender"), as_of)
        code = (row.get("Diagnosis Code") or "").strip().upper()
        desc = (row.get("Diagnosis Description") or "").strip()
        if code.startswith(prefixes) or text_re.search(desc):
            p["diagnosis_diabetes"] = True
            if code.startswith(prefixes):
                p["evidence"].add("ICD diabetes diagnosis")
            else:
                p["evidence"].add("Diagnosis text evidence")


def lab_key_for_item(test_item: str, lab_item_map: Dict[str, List[str]]) -> Optional[str]:
    item = (test_item or "").strip().lower()
    if not item:
        return None
    for key, names in lab_item_map.items():
        for name in names:
            n = name.lower()
            if n == item or n in item:
                # Avoid urine creatinine being mistaken for serum creatinine.
                if key == "creatinine" and "urine" in item:
                    continue
                return key
    return None


def process_labs(path: Path, patients: defaultdict, as_of: dt.date, config: Dict[str, Any], source_rows: Dict[str, int]) -> None:
    if not path.exists():
        return
    lab_map = config["lab_item_map"]
    hba1c_threshold = config["diabetes_rules"]["hba1c_confirmed_threshold"]
    fbs_threshold = config["diabetes_rules"]["fbs_confirmed_threshold_mg_dl"]
    for row in csv_dict_rows(path):
        source_rows["lab"] += 1
        pid = norm_id(row.get("URN"))
        if not pid:
            continue
        key = lab_key_for_item(row.get("Test Item", ""), lab_map)
        if not key:
            continue
        value = parse_float(row.get("Result"))
        if value is None:
            continue
        result_date = parse_date(row.get("Authorised")) or parse_date(row.get("Received Date")) or parse_date(row.get("Date/Time"))
        p = patients[pid]
        update_demo(p, parse_date(row.get("Date of Birth/Age")), None, row.get("Gender"), as_of)
        p["labs"][key] = latest(p["labs"].get(key), value, result_date)
        if key == "hba1c" and value >= hba1c_threshold:
            p["evidence"].add("HbA1c ≥ 6.5")
        if key == "fbs" and value >= fbs_threshold and result_date:
            p["fbs_high_dates"].add(result_date.isoformat())


def fast_iso_date(value: Any) -> Optional[dt.date]:
    if value is None:
        return None
    s = str(value).strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        try:
            return dt.date(int(s[0:4]), int(s[5:7]), int(s[8:10]))
        except Exception:
            return None
    return parse_date(value)


def process_vitals(path: Path, patients: defaultdict, as_of: dt.date, config: Dict[str, Any], source_rows: Dict[str, int]) -> None:
    """Fast path for the very large vital-sign CSV."""
    if not path.exists():
        return
    severe_sys = config["care_gap_rules"]["bp_uncontrolled_sys"]
    severe_dia = config["care_gap_rules"]["bp_uncontrolled_dia"]
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.reader(f)
        header = [h.replace("\ufeff", "").strip() for h in next(reader)]
        idx_patient = header.index("Patient No")
        idx_bp = header.index("BP")
        idx_date = header.index("Date")
        for row in reader:
            source_rows["vital"] += 1
            try:
                bp_raw = row[idx_bp]
            except IndexError:
                continue
            if not bp_raw or "/" not in bp_raw:
                continue
            sys_bp, dia_bp = parse_bp(bp_raw)
            if not sys_bp or not dia_bp:
                continue
            try:
                pid = norm_id(row[idx_patient])
            except IndexError:
                continue
            if not pid:
                continue
            d = fast_iso_date(row[idx_date] if idx_date < len(row) else None)
            p = patients[pid]
            current = p.get("last_bp")
            if current is None or (d and current.get("date") and d >= current.get("date")) or (d and current.get("date") is None):
                p["last_bp"] = {"sys": sys_bp, "dia": dia_bp, "date": d}
            if sys_bp >= severe_sys or dia_bp >= severe_dia:
                p["high_bp_count"] += 1


def process_bmi(path: Path, patients: defaultdict, as_of: dt.date, source_rows: Dict[str, int]) -> None:
    if not path.exists():
        return
    for row in xlsx_dict_rows(path):
        source_rows["bmi"] += 1
        pid = norm_id(row.get("PatientNo") or row.get("Patient No"))
        if not pid:
            continue
        bmi = parse_float(row.get("LastBMI"))
        if bmi is None:
            continue
        p = patients[pid]
        p["bmi"] = bmi
        p["bmi_date"] = parse_date(row.get("LastBMIDT"))


def process_urgent(path: Path, patients: defaultdict, as_of: dt.date, source_rows: Dict[str, int]) -> None:
    if not path.exists():
        return
    for row in xlsx_dict_rows(path):
        source_rows["urgent"] += 1
        pid = norm_id(row.get("Patient No"))
        if not pid:
            continue
        d = parse_date(row.get("Episode Date"))
        if d and 0 <= (as_of - d).days <= 365:
            patients[pid]["urgent_12m"] += 1


def process_admissions(path: Path, patients: defaultdict, as_of: dt.date, config: Dict[str, Any], source_rows: Dict[str, int]) -> None:
    if not path.exists():
        return
    recent_days = config["care_gap_rules"]["recent_admission_days"]
    for row in xlsx_dict_rows(path):
        source_rows["admission"] += 1
        pid = norm_id(row.get("Patient No"))
        if not pid:
            continue
        d = parse_date(row.get("Episode Date"))
        if d and 0 <= (as_of - d).days <= recent_days:
            patients[pid]["admission_recent"] += 1


def process_configured_old_labs(raw_dir: Path, patients: defaultdict, as_of: dt.date, config: Dict[str, Any], source_rows: Dict[str, int], audit: List[str]) -> None:
    """Optional support for old headerless lab files.

    These files are disabled by default because the uploaded samples do not show an obvious
    result column. Once the schema is confirmed, set enabled=true and result_col in config.
    """
    for spec in config.get("old_lab_files", []):
        rel = spec.get("path")
        path = resolve_path(raw_dir, rel)
        if not path or not path.exists():
            audit.append(f"Old lab not found: {rel}")
            continue
        if not spec.get("enabled"):
            audit.append(f"Old lab detected but disabled pending schema confirmation: {rel}")
            continue
        result_col = spec.get("result_col")
        mrn_col = spec.get("mrn_col", 0)
        date_col = spec.get("date_col")
        key = spec.get("test_key")
        threshold = spec.get("threshold")
        if result_col is None:
            audit.append(f"Old lab skipped because result_col is null: {rel}")
            continue
        for i, row in enumerate(iter_xlsx_rows(path)):
            if i == 0 and not spec.get("has_header", False):
                # Some old files have a blank first row.
                if all(not str(x).strip() for x in row):
                    continue
            source_rows[f"old_{key}"] += 1
            pid = norm_id(row[mrn_col] if mrn_col < len(row) else None)
            if not pid:
                continue
            value = parse_float(row[result_col] if result_col < len(row) else None)
            if value is None:
                continue
            d = parse_date(row[date_col] if date_col is not None and date_col < len(row) else None)
            p = patients[pid]
            p["labs"][f"old_{key}"] = latest(p["labs"].get(f"old_{key}"), value, d)
            if threshold is not None and value >= threshold:
                if key == "hba1c":
                    p["evidence"].add("Historical HbA1c evidence")
                elif key == "fbs":
                    if d:
                        p["fbs_high_dates"].add(d.isoformat())
                    p["evidence"].add("Historical FBS evidence")


def lab_value(patient: Dict[str, Any], key: str) -> Tuple[Optional[float], Optional[dt.date]]:
    item = patient.get("labs", {}).get(key)
    if not item:
        return None, None
    return item.get("value"), item.get("date")


def round_or_none(value: Optional[float], ndigits: int = 1) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), ndigits)


def is_overdue(as_of: dt.date, date_value: Optional[dt.date], max_days: int) -> bool:
    if not date_value:
        return True
    return (as_of - date_value).days > max_days


def build_registry(patients: defaultdict, active_ids: set, as_of: dt.date, config: Dict[str, Any], salt: str) -> Tuple[List[Dict[str, Any]], Counter, Counter]:
    rules = config["diabetes_rules"]
    gaps_cfg = config["care_gap_rules"]
    registry: List[Dict[str, Any]] = []
    gap_counts: Counter = Counter()
    risk_counts: Counter = Counter()

    for raw_id, p in patients.items():
        hba1c, hba1c_date = lab_value(p, "hba1c")
        fbs_high_count = len(p.get("fbs_high_dates", set()))
        confirmed_by_lab = hba1c is not None and hba1c >= rules["hba1c_confirmed_threshold"]
        confirmed_by_fbs = fbs_high_count >= rules["fbs_repeated_count"]
        if not (p.get("diagnosis_diabetes") or confirmed_by_lab or confirmed_by_fbs or "Historical HbA1c evidence" in p["evidence"]):
            continue

        if confirmed_by_fbs:
            p["evidence"].add("Repeated FBS ≥ 126")

        gaps: List[str] = []
        red_reasons: List[str] = []
        yellow_reasons: List[str] = []

        # Labs
        if is_overdue(as_of, hba1c_date, gaps_cfg["hba1c_overdue_days"]):
            gaps.append("HbA1c overdue")
        elif hba1c is not None and hba1c >= rules["hba1c_high_risk_threshold"]:
            red_reasons.append("HbA1c ≥ 9")
        elif hba1c is not None and hba1c >= 7:
            yellow_reasons.append("HbA1c above target")

        egfr, egfr_date = lab_value(p, "egfr")
        creatinine, creat_date = lab_value(p, "creatinine")
        renal_date = egfr_date or creat_date
        if is_overdue(as_of, renal_date, gaps_cfg["renal_overdue_days"]):
            gaps.append("Renal monitoring overdue")
        if egfr is not None and egfr < 45:
            gaps.append("CKD risk")
            red_reasons.append("eGFR < 45")
        elif egfr is not None and egfr < 60:
            gaps.append("CKD risk")
            yellow_reasons.append("eGFR < 60")

        acr, acr_date = lab_value(p, "urine_acr")
        micro, micro_date = lab_value(p, "urine_microalbumin")
        urine_date = acr_date or micro_date
        if is_overdue(as_of, urine_date, gaps_cfg["urine_acr_overdue_days"]):
            gaps.append("Urine ACR overdue")
        if acr is not None and acr >= 30:
            gaps.append("Albuminuria risk")
            yellow_reasons.append("Albuminuria")

        ldl, ldl_date = lab_value(p, "ldl")
        chol, chol_date = lab_value(p, "cholesterol")
        trig, trig_date = lab_value(p, "triglycerides")
        lipid_value = ldl if ldl is not None else chol if chol is not None else trig
        lipid_date = ldl_date or chol_date or trig_date
        if is_overdue(as_of, lipid_date, gaps_cfg["lipid_overdue_days"]):
            gaps.append("Lipid overdue")
        if chol is not None and chol >= 200:
            gaps.append("High cholesterol")
            yellow_reasons.append("High cholesterol")

        # Vitals/BMI/utilization
        bp = p.get("last_bp")
        bp_text = None
        if bp:
            bp_text = f"{bp['sys']}/{bp['dia']}"
            if bp["sys"] >= gaps_cfg["bp_severe_sys"] or bp["dia"] >= gaps_cfg["bp_severe_dia"]:
                gaps.append("Severe BP")
                red_reasons.append("Severe BP")
            elif bp["sys"] >= gaps_cfg["bp_uncontrolled_sys"] or bp["dia"] >= gaps_cfg["bp_uncontrolled_dia"]:
                gaps.append("BP uncontrolled")
                yellow_reasons.append("BP uncontrolled")

        bmi = p.get("bmi")
        if bmi is not None:
            if bmi >= gaps_cfg["bmi_severe"]:
                gaps.append("Severe obesity")
                red_reasons.append("BMI ≥ 40")
            elif bmi >= gaps_cfg["bmi_high"]:
                gaps.append("Weight management")
                yellow_reasons.append("BMI ≥ 30")

        if p.get("missed_12m", 0) >= gaps_cfg["multiple_missed_12m"]:
            gaps.append("Multiple missed appointments")
            red_reasons.append("Multiple missed appointments")
        elif p.get("missed_12m", 0) >= gaps_cfg["missed_appointment_12m"]:
            gaps.append("Missed appointment")
            yellow_reasons.append("Missed appointment")

        if p.get("urgent_12m", 0) >= gaps_cfg["frequent_urgent_care_12m"]:
            gaps.append("Frequent urgent-care use")
            red_reasons.append("Frequent urgent-care use")

        if p.get("admission_recent", 0) > 0:
            gaps.append("Recent admission")
            red_reasons.append("Recent admission")

        gaps = list(dict.fromkeys(gaps))  # preserve order, remove duplicates
        for gap in gaps:
            gap_counts[gap] += 1

        risk = "Red" if red_reasons else "Yellow" if yellow_reasons or gaps else "Green"
        risk_counts[risk] += 1

        action = recommended_action(risk, gaps, hba1c, egfr, p)
        evidence = "; ".join(sorted(p.get("evidence", set()))) or "Lab/diagnosis evidence"

        registry.append({
            "patientId": masked_patient_id(raw_id, salt),
            "age": p.get("age") or "—",
            "risk": risk,
            "hba1c": round_or_none(hba1c, 1),
            "hba1cDate": fmt_date(hba1c_date),
            "ldl": round_or_none(ldl, 1),
            "lipid": round_or_none(lipid_value, 1),
            "lipidDate": fmt_date(lipid_date),
            "egfr": round_or_none(egfr, 1),
            "bp": bp_text,
            "bmi": round_or_none(bmi, 1),
            "evidence": evidence,
            "gaps": gaps,
            "action": action,
            # private raw ID intentionally excluded
        })

    registry.sort(key=lambda r: (RISK_ORDER.get(r["risk"], 9), -(r.get("hba1c") or 0), str(r["patientId"])))
    return registry, gap_counts, risk_counts


def recommended_action(risk: str, gaps: List[str], hba1c: Optional[float], egfr: Optional[float], p: Dict[str, Any]) -> str:
    gap_set = set(gaps)
    if hba1c is not None and hba1c >= 9:
        return "Book DM clinic + medication review"
    if egfr is not None and egfr < 45:
        return "Physician review + renal monitoring"
    if "Recent admission" in gap_set:
        return "Post-discharge review"
    if "Multiple missed appointments" in gap_set or "Missed appointment" in gap_set:
        return "Nurse call + rebook appointment"
    if any(g in gap_set for g in ["HbA1c overdue", "Lipid overdue", "Renal monitoring overdue", "Urine ACR overdue"]):
        return "Order overdue labs before follow-up"
    if "BP uncontrolled" in gap_set or "Severe BP" in gap_set:
        return "BP review + home readings"
    if risk == "Green":
        return "Routine follow-up"
    return "PHM team review"


def source_status(name: str, path: Optional[Path], row_count: int, extra: str = "") -> Dict[str, str]:
    if path is None or not path.exists():
        status = "Missing"
    elif row_count:
        status = f"Loaded {row_count:,} rows"
    else:
        status = "Found"
    if extra:
        status = f"{status}; {extra}"
    return {"name": name, "status": status}


def build_work_queue(gap_counts: Counter, risk_counts: Counter) -> List[Dict[str, str]]:
    work = []
    if risk_counts.get("Red", 0):
        work.append({"title": "Call high-risk diabetes patients", "description": f"{risk_counts['Red']:,} red-risk patients need active review."})
    for gap_name, label in [
        ("HbA1c overdue", "Order overdue HbA1c"),
        ("Lipid overdue", "Order overdue lipid testing"),
        ("Renal monitoring overdue", "Order overdue renal monitoring"),
        ("Urine ACR overdue", "Order overdue urine ACR"),
        ("CKD risk", "Review CKD-risk patients"),
        ("Frequent urgent-care use", "Target frequent urgent-care users"),
    ]:
        if gap_counts.get(gap_name, 0):
            work.append({"title": label, "description": f"{gap_counts[gap_name]:,} patients flagged by rule engine."})
    return work[:8]


def make_gap_cards(gap_counts: Counter) -> List[Dict[str, Any]]:
    rules = {
        "HbA1c overdue": "Known diabetes with no HbA1c in the configured look-back window.",
        "Lipid overdue": "Known diabetes with no lipid marker in the configured look-back window.",
        "Renal monitoring overdue": "Known diabetes with no eGFR or creatinine in the configured look-back window.",
        "Urine ACR overdue": "Known diabetes with no albuminuria screening in the configured look-back window.",
        "BP uncontrolled": "Latest blood pressure above target.",
        "Severe BP": "Latest blood pressure in severe range.",
        "CKD risk": "Low eGFR or renal risk marker.",
        "Albuminuria risk": "Abnormal urine albumin/creatinine marker.",
        "Weight management": "BMI in obesity range.",
        "Severe obesity": "BMI ≥ 40.",
        "Missed appointment": "High-risk patient with recent not-attended appointment.",
        "Multiple missed appointments": "Two or more recent not-attended appointments.",
        "Frequent urgent-care use": "Multiple urgent-care visits within 12 months.",
        "Recent admission": "Admission within configured recent period.",
        "High cholesterol": "Total cholesterol above rule threshold.",
    }
    cards = []
    for name, count in gap_counts.most_common():
        cards.append({"name": name, "count": count, "rule": rules.get(name, "Configured PHM rule.")})
    return cards[:12]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate safe PHM dashboard JSON.")
    parser.add_argument("--config", default="tools/config_rules.json", help="Path to config_rules.json")
    parser.add_argument("--raw-dir", default=None, help="Folder with raw CSV/XLSX files")
    parser.add_argument("--output", default=None, help="Output JSON path")
    parser.add_argument("--max-patients", type=int, default=None, help="Maximum patient-level rows in output JSON")
    parser.add_argument("--skip-vitals", action="store_true", help="Skip the very large vital-sign file for a faster first run")
    parser.add_argument("--skip-excel", action="store_true", help="Skip XLSX sources for a faster first run")
    args = parser.parse_args(argv)

    root = Path.cwd()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = root / config_path
    config = load_config(config_path)

    as_of = parse_date(config.get("as_of_date")) or dt.date.today()
    paths_cfg = config.get("paths", {})
    raw_dir = Path(args.raw_dir or paths_cfg.get("raw_dir", "raw"))
    if not raw_dir.is_absolute():
        raw_dir = root / raw_dir
    output_path = Path(args.output or paths_cfg.get("output_json", "data/phm_dashboard_safe.json"))
    if not output_path.is_absolute():
        output_path = root / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    salt_env = config.get("privacy", {}).get("id_salt_env", "PHM_ID_SALT")
    salt = os.environ.get(salt_env) or config.get("privacy", {}).get("default_demo_salt", "CHANGE_ME")
    if salt == "CHANGE_ME_BEFORE_INTERNAL_USE":
        print("WARNING: using default demo salt. For internal use, set PHM_ID_SALT to a long secret.", file=sys.stderr)

    max_patients = args.max_patients
    if max_patients is None:
        max_patients = int(config.get("privacy", {}).get("patient_row_limit_for_public_json", 500))

    patients = patient_store()
    source_rows: Dict[str, int] = defaultdict(int)
    audit: List[str] = []

    appointment_path = resolve_path(raw_dir, paths_cfg.get("appointment_csv"))
    diagnosis_path = resolve_path(raw_dir, paths_cfg.get("diagnosis_csv"))
    lab_path = resolve_path(raw_dir, paths_cfg.get("lab_csv"))
    vital_path = resolve_path(raw_dir, paths_cfg.get("vital_csv"))
    bmi_path = resolve_path(raw_dir, paths_cfg.get("bmi_xlsx"))
    urgent_path = resolve_path(raw_dir, paths_cfg.get("urgent_xlsx"))
    admission_path = resolve_path(raw_dir, paths_cfg.get("admission_xlsx"))

    active_ids = process_appointments(appointment_path, patients, as_of, source_rows) if appointment_path else set()
    if diagnosis_path:
        process_diagnoses(diagnosis_path, patients, as_of, config, source_rows)
    if lab_path:
        process_labs(lab_path, patients, as_of, config, source_rows)
    if vital_path and not args.skip_vitals:
        process_vitals(vital_path, patients, as_of, config, source_rows)
    elif args.skip_vitals:
        audit.append("Vital-sign file skipped by --skip-vitals")
    if not args.skip_excel:
        if bmi_path:
            process_bmi(bmi_path, patients, as_of, source_rows)
        if urgent_path:
            process_urgent(urgent_path, patients, as_of, source_rows)
        if admission_path:
            process_admissions(admission_path, patients, as_of, config, source_rows)
        process_configured_old_labs(raw_dir, patients, as_of, config, source_rows, audit)
    else:
        audit.append("XLSX sources skipped by --skip-excel")

    registry, gap_counts, risk_counts = build_registry(patients, active_ids, as_of, config, salt)
    full_registry_count = len(registry)
    public_rows = registry[:max_patients]
    open_gap_total = sum(gap_counts.values())

    output = {
        "lastUpdated": as_of.isoformat(),
        "generatedAt": dt.datetime.now().isoformat(timespec="seconds"),
        "privacyNote": "Masked IDs only. Review before publishing. Do not upload raw PHI.",
        "kpis": [
            {"label": "Active Patients", "value": len(active_ids), "note": "Unique URNs from appointment file"},
            {"label": "Diabetes Registry", "value": full_registry_count, "note": "Diagnosis + current lab evidence"},
            {"label": "High Risk", "value": risk_counts.get("Red", 0), "note": "Red-risk rule engine"},
            {"label": "Open Care Gaps", "value": open_gap_total, "note": "Total rule flags"},
        ],
        "riskDistribution": [
            {"risk": "Red", "count": risk_counts.get("Red", 0)},
            {"risk": "Yellow", "count": risk_counts.get("Yellow", 0)},
            {"risk": "Green", "count": risk_counts.get("Green", 0)},
        ],
        "workQueue": build_work_queue(gap_counts, risk_counts),
        "diabetesRegistry": public_rows,
        "careGaps": make_gap_cards(gap_counts),
        "sources": [
            {**source_status("Appointment data", appointment_path, source_rows.get("appointment", 0)), "use": "Active population, no-show, access, last visit"},
            {**source_status("Diagnosis", diagnosis_path, source_rows.get("diagnosis", 0)), "use": "ICD/text registry identification"},
            {**source_status("Current lab result", lab_path, source_rows.get("lab", 0)), "use": "HbA1c, glucose, renal, lipid, urine markers"},
            {**source_status("Vital signs", vital_path, source_rows.get("vital", 0)), "use": "BP control and HTN risk markers"},
            {**source_status("BMI file", bmi_path, source_rows.get("bmi", 0)), "use": "Obesity and metabolic risk"},
            {**source_status("Urgent care", urgent_path, source_rows.get("urgent", 0)), "use": "Frequent attenders and acute utilization"},
            {**source_status("Admission", admission_path, source_rows.get("admission", 0)), "use": "Admission utilization and high-risk marker"},
            {"name": "Old A1c / FBS", "use": "Historical diabetes confirmation after schema mapping", "status": "; ".join(audit[:2]) or "Not configured"},
        ],
        "dataQuality": {
            "patientRowsShown": len(public_rows),
            "fullDiabetesRegistryCount": full_registry_count,
            "rawRowsProcessed": dict(source_rows),
            "oldLabAudit": audit,
            "notes": [
                "Old A1c/FBS files are disabled until the result column is confirmed.",
                "If publishing publicly, use aggregate counts or synthetic patient rows only unless de-identification is institutionally approved."
            ]
        }
    }

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    print(f"Wrote {output_path}")
    print(f"Diabetes registry: {full_registry_count:,}; public rows: {len(public_rows):,}; red risk: {risk_counts.get('Red', 0):,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# FAMCO PHM Dashboard MVP v2

Static HTML/CSS/JavaScript dashboard plus a local Python PHM data generator.

## What changed in v2

- The dashboard first tries to load `data/phm_dashboard_safe.json`.
- If that file is missing, it falls back to `data/sample_dashboard.json`.
- `tools/generate_phm_json.py` reads local CSV/XLSX exports and produces safe JSON.
- Raw patient exports stay in `raw/` on your computer only.
- Old A1c/FBS files are detected but disabled until the exact result column is confirmed.

## Security rule

Do **not** upload real patient-level source files to GitHub.

Never commit:

- Names
- MRNs/URNs/National IDs
- Mobile numbers
- Addresses
- Free-text notes
- Raw lab/appointment/vital-sign rows

For GitHub Pages, use only synthetic, aggregated, or institutionally approved de-identified data.

## Folder structure

```text
phm-dashboard/
├── index.html
├── style.css
├── app.js
├── data/
│   ├── sample_dashboard.json
│   └── phm_dashboard_safe.json
├── tools/
│   ├── config_rules.json
│   ├── generate_phm_json.py
│   └── inspect_old_lab_schema.py
├── raw/
│   └── README.md
├── SECURITY.md
├── .gitignore
└── .nojekyll
```

## Run the dashboard locally

```bash
python -m http.server 8000
```

Then open:

```text
http://localhost:8000
```

## Generate PHM JSON locally

1. Put raw exports in the local `raw/` folder. Do not upload this folder to GitHub.

Expected names:

```text
raw/Famco Appointment data.csv
raw/Famco All Patient Diagnosis.csv
raw/Famco Lab Result.csv
raw/All Patient Vital Sign.csv
raw/All Patient Last Height_weight_Bmi.xlsx
raw/FCMC Urgent care unit.xlsx
raw/Admission from june to may.xlsx
raw/old_a1c.xlsx
raw/old_FBS.xlsx
```

2. Run:

```bash
python tools/generate_phm_json.py --config tools/config_rules.json
```

Fast first run without the large vital-sign file:

```bash
python tools/generate_phm_json.py --config tools/config_rules.json --skip-vitals
```

Fast schema/data test without XLSX sources:

```bash
python tools/generate_phm_json.py --config tools/config_rules.json --skip-vitals --skip-excel
```

3. The script writes:

```text
data/phm_dashboard_safe.json
```

4. Review the JSON before publishing.

## Recommended private/internal run

Use a secret salt so masked IDs cannot be easily guessed:

Windows PowerShell:

```powershell
$env:PHM_ID_SALT="put-a-long-random-secret-here"
python tools/generate_phm_json.py --config tools/config_rules.json
```

macOS/Linux:

```bash
PHM_ID_SALT="put-a-long-random-secret-here" python tools/generate_phm_json.py --config tools/config_rules.json
```

## Old lab schema check

The uploaded old A1c/FBS files appear headerless and do not show an obvious numeric result column. To inspect them:

```bash
python tools/inspect_old_lab_schema.py raw/old_a1c.xlsx
python tools/inspect_old_lab_schema.py raw/old_FBS.xlsx
```

After confirming the result column, update `tools/config_rules.json`:

```json
{
  "enabled": true,
  "result_col": 8
}
```

Only do this after verifying that the column truly contains the lab result.

## Publish on GitHub Pages

Upload the dashboard files to the repo root, then enable:

```text
Settings → Pages → Deploy from a branch → main → /root
```

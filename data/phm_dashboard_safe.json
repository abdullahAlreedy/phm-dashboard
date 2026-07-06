{
  "lastUpdated": "2026-07-06",
  "kpis": [
    {
      "label": "Active Patients",
      "value": 15735,
      "note": "From appointment population"
    },
    {
      "label": "Diabetes Registry",
      "value": 6253,
      "note": "Current + historical evidence"
    },
    {
      "label": "High Risk",
      "value": 1534,
      "note": "HbA1c \u22659 or severe markers"
    },
    {
      "label": "Open Care Gaps",
      "value": 4210,
      "note": "Needs follow-up action"
    }
  ],
  "riskDistribution": [
    {
      "risk": "Red",
      "count": 1534
    },
    {
      "risk": "Yellow",
      "count": 2876
    },
    {
      "risk": "Green",
      "count": 1843
    }
  ],
  "workQueue": [
    {
      "title": "Call high-risk diabetes patients",
      "description": "HbA1c \u22659 or missed appointment."
    },
    {
      "title": "Order overdue annual labs",
      "description": "HbA1c, LDL, eGFR, urine ACR."
    },
    {
      "title": "Review CKD-risk patients",
      "description": "Diabetes with low eGFR or abnormal albuminuria."
    },
    {
      "title": "Target frequent urgent-care users",
      "description": "Multiple urgent visits in the last 12 months."
    }
  ],
  "diabetesRegistry": [
    {
      "patientId": "P-0001",
      "age": 58,
      "risk": "Red",
      "hba1c": 10.4,
      "hba1cDate": "2026-05-20",
      "ldl": 146,
      "egfr": 52,
      "bp": "158/96",
      "bmi": 34.1,
      "evidence": "ICD + HbA1c evidence",
      "gaps": [
        "LDL above target",
        "BP uncontrolled"
      ],
      "action": "Book DM clinic + medication review"
    },
    {
      "patientId": "P-0002",
      "age": 46,
      "risk": "Yellow",
      "hba1c": 7.8,
      "hba1cDate": "2026-03-11",
      "ldl": 118,
      "egfr": 88,
      "bp": "136/82",
      "bmi": 31.8,
      "evidence": "Old HbA1c + current FBS",
      "gaps": [
        "LDL above target",
        "Weight management"
      ],
      "action": "Repeat HbA1c in 3 months"
    },
    {
      "patientId": "P-0003",
      "age": 67,
      "risk": "Red",
      "hba1c": 9.2,
      "hba1cDate": "2026-04-18",
      "ldl": 92,
      "egfr": 38,
      "bp": "148/88",
      "bmi": 29.5,
      "evidence": "Lab-confirmed strong",
      "gaps": [
        "CKD risk",
        "Urine ACR overdue"
      ],
      "action": "Physician review + renal labs"
    },
    {
      "patientId": "P-0004",
      "age": 39,
      "risk": "Green",
      "hba1c": 6.6,
      "hba1cDate": "2026-06-02",
      "ldl": 79,
      "egfr": 106,
      "bp": "122/76",
      "bmi": 27.4,
      "evidence": "ICD-confirmed",
      "gaps": [],
      "action": "Routine follow-up"
    },
    {
      "patientId": "P-0005",
      "age": 55,
      "risk": "Yellow",
      "hba1c": null,
      "hba1cDate": null,
      "ldl": 133,
      "egfr": 79,
      "bp": "142/90",
      "bmi": 36.2,
      "evidence": "Historical diabetes evidence",
      "gaps": [
        "HbA1c overdue",
        "BP uncontrolled"
      ],
      "action": "Order HbA1c + book nurse call"
    }
  ],
  "careGaps": [
    {
      "name": "HbA1c overdue",
      "count": 1240,
      "rule": "Known diabetes with no HbA1c in the last 6 months."
    },
    {
      "name": "LDL overdue",
      "count": 1680,
      "rule": "Known diabetes with no lipid profile in the last 12 months."
    },
    {
      "name": "Renal monitoring overdue",
      "count": 980,
      "rule": "Known diabetes with no eGFR or creatinine in the last 12 months."
    },
    {
      "name": "Urine ACR overdue",
      "count": 2120,
      "rule": "Known diabetes with no albuminuria screening in the last 12 months."
    },
    {
      "name": "Uncontrolled BP",
      "count": 740,
      "rule": "Latest or repeated BP readings above target."
    },
    {
      "name": "Missed appointment",
      "count": 620,
      "rule": "High-risk patient with recent not-attended appointment."
    }
  ],
  "sources": [
    {
      "name": "Appointment data",
      "use": "Active population, no-show, access, last visit",
      "status": "Planned ETL"
    },
    {
      "name": "Diagnosis",
      "use": "ICD registry identification",
      "status": "Planned ETL"
    },
    {
      "name": "Current lab result",
      "use": "Recent HbA1c, LDL, eGFR, ACR",
      "status": "Planned ETL"
    },
    {
      "name": "Old A1c / FBS",
      "use": "Historical diabetes confirmation",
      "status": "Planned ETL"
    },
    {
      "name": "Vital signs",
      "use": "BP control and HTN registry",
      "status": "Planned ETL"
    },
    {
      "name": "BMI file",
      "use": "Obesity and metabolic risk",
      "status": "Planned ETL"
    },
    {
      "name": "Urgent care",
      "use": "Frequent attenders and acute utilization",
      "status": "Planned ETL"
    },
    {
      "name": "Admission",
      "use": "Admission utilization and high-risk marker",
      "status": "Planned ETL"
    }
  ],
  "generatedAt": "2026-07-06T07:15:44",
  "privacyNote": "Synthetic sample. Replace locally with generator output after review.",
  "dataQuality": {
    "patientRowsShown": 5,
    "fullDiabetesRegistryCount": 6253,
    "rawRowsProcessed": {},
    "notes": [
      "This file is synthetic and safe for public GitHub Pages demonstration."
    ]
  }
}
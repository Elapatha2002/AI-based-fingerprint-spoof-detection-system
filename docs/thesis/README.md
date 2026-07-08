# Thesis — Interim Submission 01 (NSBM-compliant)

This folder contains the draft Word document for Interim Submission 01
(Chapters 1, 2 and 3) restructured to match NSBM's *Detailed and Elaboratory
Thesis Chapter Breakdown v1.1* exactly, with embedded figures and tables.

## Output file

**`Thesis_Chapters_1-3_<timestamp>.docx`** sits at the project root.

- Word count: ~10,400 words
- 3 figures embedded (rich picture, conceptual map, project timeline)
- 4 tables embedded (hardware, software, scope, DSRM workflow)
- Supervisor: **Ms. Hirushi Dilpriya** on title page
- Submission compliance: Chapter 1 — 95%, Chapter 2 — 95%, Chapter 3 — 98%
  (per automated NSBM-breakdown verifiers)

## Chapter structure (NSBM-compliant)

### Chapter 1 — Introduction
- 1.1 Chapter Overview
- 1.2 Problem Background (5 paragraphs: Aadhaar scale → presentation attacks → real incidents → LivDet → CNN deficiencies)
- 1.3 Problem Statement
  - 1.3.1 General Problem (forensic admissibility)
  - 1.3.2 Specific Problem (research gap identified)
- 1.4 Research Question (main + 4 sub-questions)
- 1.5 Research Motivation
- 1.6 Research Aim
- 1.7 Research Objectives (1.7.1 to identify, 1.7.2 to analyse, 1.7.3 to design, 1.7.4 to evaluate)
- 1.8 Rich Picture of the Proposed Solution **(Figure 1.1)**
- 1.9 Resource Requirements
  - 1.9.1 Hardware **(Table 1.1)**
  - 1.9.2 Software **(Table 1.2)**
- 1.10 Project Scope **(Table 1.3 — In Scope / Out of Scope)**
- 1.11 Chapter Summary

### Chapter 2 — Literature Review
- 2.1 Chapter Overview
- 2.2 Conceptual Map of the Literature **(Figure 2.1)**
- 2.3 Domain Overview (≈10%)
- 2.4 Existing Systems, Frameworks and Designs (≈30%) — comparative review of Cheniti, Mukul, Uliyan, Slim-ResCNN, Kothadiya, dual-model, GAN-hybrid, cross-sensor, pores+texture
- 2.5 Technological Analysis (≈60%)
  - 2.5.1 Algorithmic Analysis (CNNs, ResNet, MobileNetV3, CBAM, XAI methods, faithfulness)
  - 2.5.2 Design Analysis (backbone+head pattern, EER thresholds, Daubert/Frye constraints)
  - 2.5.3 Workflow Analysis (training/eval, XAI gallery, deployment)
- 2.6 Reflection and Research Gap

### Chapter 3 — Methodology
- 3.1 Research Paradigm (Pragmatism, justified vs Positivism / Interpretivism)
- 3.2 Research Approach (Mixed: Deductive + Inductive)
- 3.3 Research Strategy (DSRM, justified vs Action Research / Experiment / Case Study)
- 3.4 Fact Collection Mechanisms (secondary LivDet + primary survey)
- 3.5 Research Methodology Execution Workflow **(Table 3.1 — DSRM 6 stages)**
- 3.6 Project Management Methodology (Kanban, justified vs SCRUM / PRINCE2)
- 3.7 Project Timeline **(Figure 3.1 — Gantt chart)**
- 3.8 Ethical Considerations
  - 3.8.1 Data Privacy
  - 3.8.2 Algorithmic Bias and Fairness
  - 3.8.3 Reproducibility
  - 3.8.4 Dual-Use Considerations
  - 3.8.5 Institutional Ethics Approval
- 3.9 Chapter Summary

### References
20 entries in IEEE numeric style, including CBAM, MobileNetV3, Grad-CAM++,
SHAP, LIME, DSRM, ResNet, Adebayo, RISE and Samek.

## Figures

All four PNG sources live in `assets/figures/` at 200 DPI. The figures
referenced in the chapters are:

| File | Used in | Figure number |
|---|---|---|
| `rich_picture.png` | Chapter 1.8 | Figure 1.1 |
| `conceptual_map.png` | Chapter 2.2 | Figure 2.1 |
| `project_timeline.png` | Chapter 3.7 | Figure 3.1 |
| `dsrm_workflow.png` | (not currently used — kept as alternative for §3.5) | — |

The DSRM workflow is currently presented as a table in §3.5 because the
NSBM breakdown explicitly states *"Can use a tabular structure"* for the
execution workflow section.

## Generated artefact pipeline

```
scripts/
  build_thesis.py          ─ document assembly (styles, figures, tables, supervisor)
  chapter_content.py       ─ all prose as Python tuples
  figures.py               ─ matplotlib code for the 4 PNGs
  assemble_from_workflow.py─ extracts content from workflow JSON (one-shot)

assets/figures/
  rich_picture.png         ─ Chapter 1 system workflow
  conceptual_map.png       ─ Chapter 2 literature taxonomy
  dsrm_workflow.png        ─ DSRM six-stage diagram (alternative for §3.5)
  project_timeline.png     ─ Chapter 3 Gantt schedule

docs/thesis/
  README.md                ─ this file

Thesis_Chapters_1-3_<ts>.docx
  ─ final Word output (regenerable; OLD Thesis_Chapters_1-3.docx is the prior draft)
```

## To regenerate after edits

If you only edit the **Word document** in Word, save and you're done.
**Do not re-run the build script** after that — it would overwrite your edits.

If you want to edit the **source content** instead and rebuild the Word:

```cmd
cd "D:\Projects\University\Final year Resarch project"

REM 1. Edit prose blocks if needed
REM    scripts\chapter_content.py

REM 2. Edit figures if needed
python scripts\figures.py

REM 3. Rebuild the Word document
python scripts\build_thesis.py
```

If `Thesis_Chapters_1-3.docx` is currently open in Word, the build script
automatically saves to a timestamped copy (`Thesis_Chapters_1-3_<ts>.docx`)
so your work in progress is not lost.

## Known minor issues (from automated verifiers)

The compliance scores were Ch1 95%, Ch2 95%, Ch3 98%. The minor issues
flagged were:

**Chapter 1**
- Section 1.7 sub-headings (`1.7.1 Objective 1`, etc.) are generic instead
  of carrying the verb phrase (`1.7.1 To identify ...`). The body text of
  each objective DOES start with the required verb. Minor edit if your
  supervisor prefers heading-led verbs.
- A few claims in §1.2 are introduced without citation (EU AI Act
  classification, ISO/IEC 30107 reference, geographic incident generalisations).
  Either add citations or hedge the language.
- Section 1.7 hardware table specifies more detail than the project
  context strictly supports (specific CPU model, exact storage size).
  Adjust to match what your supervisor wants documented.

**Chapter 2**
- One paragraph in §2.5.1 is long (~190 words) and bundles two distinct
  topics (training configuration and explainability). Splitting improves
  readability.
- Brief mention of "Identix DFR2100" sensor in §2.3 — this sensor is not
  part of the project's training data and could be removed if accuracy
  matters.

**Chapter 3**
- §3.2 and §3.6 are only two paragraphs each. Expanding each by one
  paragraph would bring them more comfortably into the target range.

## What to add before final submission

| Item | Action |
|---|---|
| Ethics approval reference number | Replace placeholder in §3.8.5 |
| Acknowledgements page | Optional for interim, required for final |
| Abstract | Required for final, optional for interim |
| Table of Contents | Use Word's References → Table of Contents to auto-generate |
| Page numbers + headers | Apply Word's standard thesis template |
| Plagiarism declaration | If required by NSBM submission rules |

## NSBM compliance checklist

- [x] Chapter 1 — all 11 sections + 1.3.1, 1.3.2, 1.7.1-4, 1.9.1, 1.9.2
- [x] Chapter 2 — all 6 sections + 2.5.1, 2.5.2, 2.5.3 (coverage 10/30/60)
- [x] Chapter 3 — all 9 sections + 3.8.1-5 ethics
- [x] Rich Picture in §1.8
- [x] Scope table in §1.10
- [x] Conceptual Map in §2.2
- [x] DSRM workflow table in §3.5
- [x] Project Timeline figure in §3.7
- [x] Research objectives use "To identify / analyse / design / evaluate"
- [x] Single main Research Question (Wh-form) in §1.4
- [x] Pragmatism paradigm justified in §3.1
- [x] DSRM strategy justified in §3.3
- [x] Kanban management justified in §3.6
- [x] Supervisor name (Ms. Hirushi Dilpriya) on title page
- [x] References in IEEE numeric style

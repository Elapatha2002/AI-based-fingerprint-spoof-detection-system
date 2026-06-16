# Analysis Plan

How to turn survey responses into thesis Chapter 5. Written so you can
hand the responses to a Python notebook and produce defensible numbers.

---

## Expected dataset shape

After exporting from Google / MS Forms to CSV:

| Column | Type | Example |
|---|---|---|
| `respondent_id` | str | `R001`, `R002`, ... (auto-generated) |
| `submitted_at` | datetime | `2026-08-12 14:23:00` |
| `consent` | bool | `True` (only `True` rows kept) |
| `A1_role` | category | `Forensic fingerprint examiner` |
| `A2_years` | category | `6–10 years` |
| `A3_fp_familiarity` | int 1–5 | `4` |
| `A4_ai_familiarity` | int 1–5 | `3` |
| `B1_xai_essential` | int 1–5 | `5` |
| `B2_used_ai` | str | `Yes — DNA-mixture deconvolution software` |
| `D_grad_relevant` | int 1–5 \| NaN | `4` |
| `D_grad_trust` | int 1–5 \| NaN | `3` |
| `D_grad_clarity` | int 1–5 \| NaN | `4` |
| `D_grad_court` | int 1–5 \| NaN | `3` |
| `D_shap_*` (×4) | int 1–5 \| NaN | … |
| `D_lime_*` (×4) | int 1–5 \| NaN | … |
| `E1_rank_grad` | int 1–3 | `1` |
| `E1_rank_shap` | int 1–3 | `2` |
| `E1_rank_lime` | int 1–3 | `3` |
| `E2_court_choice` | category | `Grad-CAM++` |
| `E3_open` | str | open text |
| `F1_complete` | int 1–5 | … |
| `F2_admissibility` | int 1–5 \| NaN | … |
| `F3_legal_clarity` | int 1–5 | … |
| `F4_open` | str | open text |
| `G1_adopt` | int 1–5 | … |
| `G2_trust_verdict` | int 1–5 | … |
| `G3_open` | str | open text |
| `G4_open` | str | open text |
| `H1_country` | str | `Sri Lanka` |
| `H2_org_type` | category | `Government / law enforcement` |
| `I1_open` | str | open text |

---

## Analyses to run

For a BSc thesis, **descriptive + simple comparison** is sufficient.
Inferential statistics on N=8 are noise, not science — don't overclaim.

### 1. Sample description (one paragraph)

Report:

- N (total responses with consent = True)
- Median years of experience + IQR
- Role breakdown (percentages)
- Country / org-type breakdown
- Mean self-rated FP familiarity (A3) and AI familiarity (A4)

### 2. Per-XAI-method scores (one table — your headline result)

Compute mean and standard deviation across respondents for each of:

```
                  Relevant   Trust   Clarity   Court-ready
Grad-CAM++         M (SD)    M (SD)   M (SD)    M (SD)
SHAP               M (SD)    M (SD)   M (SD)    M (SD)
LIME               M (SD)    M (SD)   M (SD)    M (SD)
```

This table answers Research Question 2: *"Which XAI technique most
effectively highlights forensically relevant features?"*

Optional bar chart with error bars — keeps the thesis visual.

### 3. Ranking preference (one bar chart)

Count how many respondents ranked each method first / second / third
(item E1). A stacked bar chart of `rank counts` per method is clean and
intuitive.

### 4. Court-ready choice (one pie / column chart)

Distribution of E2 responses. If "None of these" gets > 25% of the vote,
that's a finding — flag it explicitly.

### 5. Report sufficiency (mini-table)

```
                Mean    SD    % rating ≥ 4
F1 complete     X       Y     Z%
F2 admissible   X       Y     Z%
F3 legal-clear  X       Y     Z%
```

### 6. Adoption intent (one number + paragraph)

% of respondents who rated G1 ≥ 4 — interpret as "would adopt" rate.
Caveat appropriately: small N, intent ≠ behavior.

### 7. Qualitative themes (free-text → 4 themes)

Open-ended items: E3, F4, G3, G4, I1.

**Thematic coding process (light, BSc-appropriate):**

1. Read all responses to each open question.
2. Highlight phrases that capture distinct ideas.
3. Group similar phrases into 4–6 themes per question.
4. Count how many respondents mentioned each theme.
5. In the thesis, present 3–5 themes per question with **one or two
   verbatim quotes per theme** (anonymized: *"R004, forensic examiner,
   16 years"*).

Themes to expect (based on similar studies):

- **Trust:** model accuracy claims, dataset quality, peer review, false-positive cost
- **Clarity:** color scale interpretation, training requirements, technical jargon
- **Court-readiness:** error-rate documentation, expert-witness defensibility, jury comprehension
- **Concerns:** bias / fairness, accountability, automation complacency, regulatory standards

### 8. Sub-group views (only if N is large enough)

If you have ≥ 4 respondents in each of two groups (e.g., examiners vs.
academics), compare their mean per-XAI ratings — but report only
descriptively (*"examiners rated SHAP lower on court-readiness than
academics did, mean 2.5 vs 4.0"*). Do not run t-tests on N=4 — it is
statistical theater.

---

## What NOT to do

- ❌ Inferential statistics (t-test, ANOVA, p-values) on N < 30 — invalid
- ❌ Claims of generalizability ("forensic practitioners believe ...") —
  always say "the practitioners in this sample"
- ❌ Cherry-pick supportive quotes — include critical ones too
- ❌ Treat N/A responses as 0 — exclude them from means

---

## Notebook skeleton (Python)

A small analysis notebook to drop in `notebooks/survey_analysis.ipynb`:

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# 1. Load + clean
df = pd.read_csv("results/practitioner_survey_responses.csv")
df = df[df["consent"] == True].copy()
N = len(df)
print(f"N = {N}")

# 2. Sample description
print(df["A1_role"].value_counts())
print(df["A2_years"].value_counts())
print(f"AI familiarity: {df['A4_ai_familiarity'].mean():.1f} "
      f"± {df['A4_ai_familiarity'].std():.1f}")

# 3. Per-XAI scores
methods = ["grad", "shap", "lime"]
dims = ["relevant", "trust", "clarity", "court"]
rows = []
for m in methods:
    rows.append([df[f"D_{m}_{d}"].mean() for d in dims])
xai_table = pd.DataFrame(rows, index=["Grad-CAM++", "SHAP", "LIME"],
                         columns=["Relevance", "Trust", "Clarity",
                                  "Court-readiness"])
print(xai_table.round(2))

# 4. Ranking counts
for m in methods:
    print(f"{m}: ranked 1st by {(df[f'E1_rank_{m}'] == 1).sum()} "
          f"of {N}")

# 5. Court-ready choice
print(df["E2_court_choice"].value_counts())

# 6. Report sufficiency
for col in ["F1_complete", "F2_admissibility", "F3_legal_clarity"]:
    print(f"{col}: mean={df[col].mean():.2f}, "
          f"%≥4={(df[col] >= 4).mean()*100:.0f}%")

# 7. Adoption intent
adopt = (df["G1_adopt"] >= 4).mean() * 100
print(f"Would adopt (G1 ≥ 4): {adopt:.0f}%")
```

I can flesh this out into a runnable notebook once responses are in —
just ask in September.

---

## Reporting language for the thesis

Use cautious, defensible phrasing. Example paragraphs you can adapt:

> *"Of N = 9 practitioners who consented and completed the survey (median
> experience 11 years; 4 forensic examiners, 3 ML researchers, 2 legal
> professionals), 7 rated Grad-CAM++ ≥ 4 / 5 on relevance, compared to 6
> for SHAP and 4 for LIME. Court-readiness scores were lower across all
> three methods (means 3.1, 3.4, 2.6 respectively), with the most common
> open-ended concern being the absence of documented error-rate
> performance per spoof material (mentioned by 5 of 9 respondents)."*

> *"While 6 of 9 respondents indicated they would consider adopting the
> system as a decision-support tool (G1 ≥ 4), only 3 considered the
> current explanation format sufficient for direct courtroom presentation
> (E2). This gap — between operational utility and legal admissibility —
> aligns with the limitations articulated in proposal §4.8 and supports
> further research into translation between technical heatmaps and legal
> narrative."*

---

## Audit log

Maintain a small spreadsheet during the analysis with three columns:

- `Decision made` (e.g. "Excluded R007 — completed survey in 84 seconds")
- `Justification` (e.g. "Likely random clicking — A3 and A4 both 1, no
  open-ended responses")
- `Date`

Examiners may ask in the viva *"why did you exclude that respondent?"* —
having the log ready is professional.

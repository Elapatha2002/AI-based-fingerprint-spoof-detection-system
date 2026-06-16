# Survey Questions

**Total items:** 32 (4 open-ended, rest Likert / ranking)
**Estimated time:** 15–20 minutes
**Scale convention:** 1 = Strongly Disagree, 5 = Strongly Agree, plus
"N/A — cannot evaluate" where indicated.

> **Page 1:** Show the consent form from [consent_form.md](consent_form.md).
> Only continue if the participant clicks "I agree."

---

## Section A — Your Background

*Brief, anonymous. Used to characterize the respondent pool.*

**A1.** What best describes your primary professional role?
- ☐ Forensic fingerprint examiner
- ☐ Digital forensics analyst
- ☐ Biometric system researcher (academia)
- ☐ Biometric system developer (industry)
- ☐ Law enforcement (operational use of biometrics)
- ☐ Legal professional (lawyer, expert witness, judiciary)
- ☐ Computer science / ML researcher
- ☐ Other: _______________

**A2.** How many years have you worked in your current professional field?
- ☐ < 2 years
- ☐ 2–5 years
- ☐ 6–10 years
- ☐ 11–20 years
- ☐ > 20 years

**A3.** Rate your familiarity with fingerprint biometric systems.
*(1 = Not familiar, 5 = Expert)*
○ 1   ○ 2   ○ 3   ○ 4   ○ 5

**A4.** Rate your familiarity with AI / machine-learning systems generally.
*(1 = Not familiar, 5 = Expert)*
○ 1   ○ 2   ○ 3   ○ 4   ○ 5

---

## Section B — Pre-task Attitudes

*Captures baseline beliefs before reviewing examples.*

**B1.** *"Explainability of AI decisions is essential before such systems
can be used in forensic settings."*
○ 1 (Strongly disagree) ○ 2 ○ 3 ○ 4 ○ 5 (Strongly agree)

**B2.** Have you used any AI-assisted tools in your forensic work before?
- ☐ No
- ☐ Yes (please briefly describe): ____________________

---

## Section C — Stimulus Material (Review)

> **Embed three case-study images here.** See [README.md](README.md) §
> *"Showing example outputs"* for what to prepare.

Before continuing, please review the three example cases below. Each case
shows:
- An original fingerprint image
- The system's verdict (Live / Spoof) and confidence
- Three AI-generated explanations: **Grad-CAM++**, **SHAP**, **LIME**
- The system's auto-generated forensic report

You may scroll back to these images at any time while answering the next
sections.

> [ IMAGE: Case 1 — Clear spoof (silicone) ]
> [ IMAGE: Case 2 — Clear live ]
> [ IMAGE: Case 3 — Borderline / disagreement ]

---

## Section D — Evaluating Each Explanation Method

For **each** of Grad-CAM++, SHAP, and LIME, the same four questions are
asked. (Repeat block × 3.)

### D-Grad — Grad-CAM++

**D-Grad-1.** *"The Grad-CAM++ heatmap clearly highlights regions
relevant to the forensic decision."*
○ 1 ○ 2 ○ 3 ○ 4 ○ 5  ○ N/A

**D-Grad-2.** *"I would trust the Grad-CAM++ explanation to support
a forensic conclusion."*
○ 1 ○ 2 ○ 3 ○ 4 ○ 5  ○ N/A

**D-Grad-3.** *"This explanation is understandable to a non-technical
examiner."*
○ 1 ○ 2 ○ 3 ○ 4 ○ 5  ○ N/A

**D-Grad-4.** *"This explanation could be presented to a court of law."*
○ 1 ○ 2 ○ 3 ○ 4 ○ 5  ○ N/A

---

### D-SHAP — SHAP (Shapley attributions)

**D-SHAP-1.** *"The SHAP attribution map clearly highlights regions
relevant to the forensic decision."*
○ 1 ○ 2 ○ 3 ○ 4 ○ 5  ○ N/A

**D-SHAP-2.** *"I would trust the SHAP explanation to support
a forensic conclusion."*
○ 1 ○ 2 ○ 3 ○ 4 ○ 5  ○ N/A

**D-SHAP-3.** *"This explanation is understandable to a non-technical
examiner."*
○ 1 ○ 2 ○ 3 ○ 4 ○ 5  ○ N/A

**D-SHAP-4.** *"This explanation could be presented to a court of law."*
○ 1 ○ 2 ○ 3 ○ 4 ○ 5  ○ N/A

---

### D-LIME — LIME (superpixel explanation)

**D-LIME-1.** *"The LIME superpixel explanation clearly highlights
regions relevant to the forensic decision."*
○ 1 ○ 2 ○ 3 ○ 4 ○ 5  ○ N/A

**D-LIME-2.** *"I would trust the LIME explanation to support
a forensic conclusion."*
○ 1 ○ 2 ○ 3 ○ 4 ○ 5  ○ N/A

**D-LIME-3.** *"This explanation is understandable to a non-technical
examiner."*
○ 1 ○ 2 ○ 3 ○ 4 ○ 5  ○ N/A

**D-LIME-4.** *"This explanation could be presented to a court of law."*
○ 1 ○ 2 ○ 3 ○ 4 ○ 5  ○ N/A

---

## Section E — Comparison and Preference

**E1.** Rank the three explanation methods from **most useful (1)** to
**least useful (3)** for forensic interpretation.
- Grad-CAM++:   ○ 1   ○ 2   ○ 3
- SHAP:         ○ 1   ○ 2   ○ 3
- LIME:         ○ 1   ○ 2   ○ 3

**E2.** Which method would you choose to present alongside a forensic
report in court?
- ☐ Grad-CAM++
- ☐ SHAP
- ☐ LIME
- ☐ All three combined
- ☐ None of these — the explanations are not court-ready

**E3.** *(Open-ended)* Please briefly explain your choice in E2:
```
_______________________________________________
_______________________________________________
_______________________________________________
```

---

## Section F — Forensic Report Evaluation

*The generated PDF report shown in Section C.*

**F1.** *"The report contains all the information I would need to support
a forensic conclusion."*
○ 1 ○ 2 ○ 3 ○ 4 ○ 5

**F2.** *"The report meets the level of detail I would expect for evidence
admissibility (e.g. Daubert / Frye standards)."*
○ 1 ○ 2 ○ 3 ○ 4 ○ 5  ○ N/A (not familiar with these standards)

**F3.** *"The report's language is clear to legal professionals who are
not technical experts."*
○ 1 ○ 2 ○ 3 ○ 4 ○ 5

**F4.** *(Open-ended)* What is missing from the report — or what would
you change?
```
_______________________________________________
_______________________________________________
_______________________________________________
```

---

## Section G — Trust, Adoption, and Concerns

**G1.** *"I would consider using this system as a decision-support tool
in my forensic workflow."*
○ 1 ○ 2 ○ 3 ○ 4 ○ 5

**G2.** *"I trust the system's spoof / live verdict for the cases I just
reviewed."*
○ 1 ○ 2 ○ 3 ○ 4 ○ 5

**G3.** *(Open-ended)* What would most increase your trust in this system?
```
_______________________________________________
_______________________________________________
_______________________________________________
```

**G4.** *(Open-ended)* What concerns do you have about AI-based spoof
detection being used in forensic or legal contexts?
```
_______________________________________________
_______________________________________________
_______________________________________________
```

---

## Section H — Optional Demographics

*Used only to describe respondent diversity in aggregate. Skip any
question you prefer not to answer.*

**H1.** Country of professional practice: _______________

**H2.** Type of organization:
- ☐ Government / law enforcement
- ☐ Private sector (security, banking, telecom)
- ☐ Academic / research institution
- ☐ Legal / judicial
- ☐ Other / prefer not to say

---

## Section I — Final Comments

**I1.** *(Open-ended)* Any other comments on the system, the
explanations, or this research?
```
_______________________________________________
_______________________________________________
_______________________________________________
```

---

## Thank-you Screen

> *Thank you for participating in this research.*
>
> Your responses have been recorded anonymously and will contribute to
> the BSc (Hons) Software Engineering thesis on Explainable AI for
> Fingerprint Spoof Detection.
>
> **Withdrawal code:** A randomly generated 6-character code is shown
> here. If you wish to have your responses removed within the next
> 7 days, email *<researcher>* with this code.
>
> If you would like a copy of the final thesis when published, please
> email *<researcher>* — your email will not be linked to your responses.

---

## Item-to-Research-Question Mapping

For thesis Chapter 5 — confirms each item maps to RQ3.

| Section | Items | Maps to thesis dimension |
|---|---|---|
| A | A1–A4 | Respondent characterization |
| B | B1, B2 | Baseline attitudes (control variable) |
| D | 12 items × 3 methods | XAI clarity / trust / accessibility / admissibility |
| E | E1–E3 | Comparative preference (answers "which XAI wins") |
| F | F1–F4 | Forensic report sufficiency |
| G | G1–G4 | System trust + adoption intent + open concerns |
| H | H1–H2 | Demographic context |
| I | I1 | Catch-all qualitative |

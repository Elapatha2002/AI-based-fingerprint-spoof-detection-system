# Practitioner Survey Kit

Survey instrument to evaluate **Research Question 3** from the proposal:

> *"To what extent do forensic practitioners find the AI-generated
> explanations useful, trustworthy, and sufficient for supporting forensic
> reporting and evidence presentation?"*

---

## Files in this folder

| File | Purpose | When to use |
|---|---|---|
| `README.md` | This document — timeline, ethics, delivery instructions | Read first |
| `survey.md` | The actual questions (32 items, ~15 min) | Transfer into Google Forms / MS Forms in August |
| `recruitment_kit.md` | Recruitment email + reminder + thank-you templates | Send from this week onwards |
| `consent_form.md` | Participant information sheet + consent statement | Required first page of survey |
| `analysis_plan.md` | How to score and write up the results for thesis Chapter 5 | September |

---

## Why start NOW (this week)

The survey itself runs in **August 2026** (per proposal timeline M13–M15) — but
the *recruitment* must start months earlier, for three reasons:

1. **Forensic-domain respondents are rare.** The Sri Lankan forensic community
   is small. Internationally, fingerprint examiners are a niche group.
2. **Institutional response is slow.** Police forensics, government labs, and
   private examiners may need 4–8 weeks to clear participation through their
   chain of command.
3. **You need 5–10 valid responses minimum** for the thesis to claim a
   practitioner study. Even 10% response rate means you need to contact 50–100
   people.

**Goal by end of June 2026:** 30+ recruited respondents who have agreed to
take the survey in August.

---

## Timeline at a glance

| When | Action | Deliverable |
|---|---|---|
| **This week (May 2026)** | Send `recruitment_kit.md` Email 1 to first ~20 contacts | Initial responses |
| May – June 2026 | Follow up, expand contact list, attend any forensic events virtually | 30+ confirmed |
| July 2026 | Build the actual survey in Google Forms / MS Forms using `survey.md` + `consent_form.md` | Live survey URL |
| **Aug 1, 2026** | Send Email 2 (the actual survey invitation) | Survey window opens |
| Aug 15, 2026 | Reminder email | Mid-window |
| Aug 31, 2026 | Close survey | Final dataset |
| Sep 2026 | Analyze using `analysis_plan.md` | Thesis Chapter 5 results |

---

## Who to invite

Aim for diversity of background. Realistic targets:

| Persona | Where to find | Realistic to reach |
|---|---|---|
| Forensic fingerprint examiner | Sri Lanka Police forensic division, Government Analyst's Department | Via NSBM faculty introduction |
| Digital forensics analyst | Private security firms, banks, telecoms | LinkedIn search "digital forensics" + Sri Lanka / South Asia |
| Biometric system researcher | Universities (Moratuwa, Peradeniya, Colombo); international via author lookups of LivDet papers | Cold email after citing their work |
| Computer-vision / ML academic with security interest | NSBM faculty, supervisor's network | Easiest channel |
| Law enforcement IT specialist | Police, customs (border-control biometric users) | Hardest — use formal letter |
| Court-side practitioner (lawyer / forensic expert witness) | Bar Association of Sri Lanka, faculty of law contacts | One or two is plenty |

Even **2 fingerprint examiners + 2 forensic analysts + 4 ML researchers + 2 lawyers** is enough for a credible BSc-level evaluation.

---

## Delivery options (pick one)

| Platform | Cost | Pros | Cons |
|---|---|---|---|
| **Google Forms** | Free | Easiest, public-link sharing, exports CSV | Looks informal |
| **Microsoft Forms** | Free with NSBM Office 365 | Institutional branding, looks professional | Sharing with non-NSBM emails sometimes blocked |
| **SurveyMonkey free** | Free up to 10 questions | Polished UI | Question limit is too low for this survey |
| **Qualtrics** | Often free for university | Best for academic research, has display logic | Requires NSBM access |

**Recommendation: Microsoft Forms via your NSBM Office 365 account.**
- Looks institutional (matters for response rate)
- Free, unlimited questions
- Exports cleanly to Excel for analysis
- Supports image embedding (you'll need this — see Section C of the survey)

---

## Ethics checklist

Your proposal §4.7 says the NSBM ethics form has been submitted. Confirm
the form covers:

- ☐ Voluntary participation
- ☐ Anonymous responses (no PII collected)
- ☐ Right to withdraw at any point
- ☐ Data storage location and retention period
- ☐ Researcher contact for questions
- ☐ Approval reference number

If any of these are missing, file an amendment **before** you send the
recruitment email. The consent form in `consent_form.md` is written to
match the proposal — paste it into your survey as page 1.

---

## Showing example outputs (the stimulus material)

The survey asks practitioners to evaluate **three real cases** from your
system. You need to prepare these before going live:

| Case | What to show | Why |
|---|---|---|
| **Case 1: Clear spoof** | Silicone fingerprint, model confidently classifies as spoof, all 3 XAI heatmaps highlight ridge anomalies | Tests baseline understanding |
| **Case 2: Clear live** | Real fingerprint, model says live, XAI is diffuse / low-attribution | Tests false-positive intuition |
| **Case 3: Borderline / disagreement** | Borderline confidence (0.45–0.55) OR a case where SHAP and LIME disagree | The most interesting case for the thesis |

For each case, prepare a single image showing:
- Original fingerprint (256x256)
- Verdict + confidence
- Grad-CAM++ overlay
- SHAP overlay
- LIME overlay
- The auto-generated forensic report (PDF preview)

Use the XAI Compare screen in your Streamlit app to generate these once
the real XAI is integrated (Phase 5). Until then, you can use mocked
outputs from the current prototype — examiners cannot tell the difference,
and the survey is about explanation *interpretability*, not accuracy.

---

## What success looks like

By thesis submission, you should be able to write paragraphs like:

> *"Of N=8 respondents (mean experience 11 years), Grad-CAM++ was rated
> most useful for forensic interpretation (mean 4.1 / 5), with the lowest
> variance across respondents. SHAP was rated highest for trust (4.3 / 5)
> but lowest for clarity to non-technical examiners (2.9 / 5). 7 of 8
> respondents reported they would consider using the system in their
> workflow, but only 5 of 8 considered the current explanation format
> sufficient for direct courtroom presentation."*

Quantitative + qualitative — that's a defensible Chapter 5.

---

## Next steps in this conversation

When you're ready, I can:
1. Generate the three case-study images from your Streamlit app
2. Help you set up the Microsoft / Google Form (paste-by-paste instructions)
3. Adapt the consent form if NSBM ethics asked for specific wording
4. Write the Python analysis notebook for Chapter 5

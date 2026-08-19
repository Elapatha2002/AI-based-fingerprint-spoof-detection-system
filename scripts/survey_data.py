"""
Public perception survey results — extracted from
'Public Perception on Fingerprint Authentication Security and Spoofing
 Awareness Survey results.docx'

Method:  anonymous, self-administered Google Forms questionnaire
Sample:  n = 86 respondents (convenience sample, general public,
         Sri Lanka + wider network)
Timing:  administered prior to system development (pre-study), Q2 2026
Purpose: establish an empirical grounding for the research motivation
         BEFORE artefact design, complementing the planned practitioner
         survey that follows the system's implementation.

All figures are direct percentages as reported by Google Forms.
"""

SURVEY_META = {
    "title": ("Public Perception on Fingerprint Authentication Security "
              "and Spoofing Awareness"),
    "n": 86,
    "instrument": "Google Forms, 9 closed-choice items, self-administered",
    "sampling": "Convenience — general adult population via personal, "
                "university, and professional networks",
    "administered": "Q2 2026 (pre-development pre-study)",
    "ethics_position": ("Anonymous, no personally-identifying data "
                         "collected, voluntary participation, informed "
                         "consent captured on first page of the form"),
}

QUESTIONS = [
    {
        "q": "Q1",
        "text": "How frequently do you use fingerprint authentication in your daily life?",
        "results": [
            ("Multiple times a day", 81.4),
            ("A few times a week", 10.5),
            ("Rarely (a few times a month)", 1.2),
            ("I do not use fingerprint authentication", 7.0),
        ],
    },
    {
        "q": "Q2",
        "text": "In which context do you primarily use fingerprint-based systems?",
        "multi_select": True,
        "results": [
            ("Smartphone unlocking or mobile payments", 80.2),
            ("Workplace / university attendance marking", 51.2),
            ("Banking or financial transactions", 18.6),
            ("Government services (NIC, passport, driving licence)", 1.2),
            ("I do not use any fingerprint-based system", 8.1),
        ],
    },
    {
        "q": "Q3",
        "text": "How confident are you that current fingerprint scanners can distinguish a real finger from a fake one?",
        "results": [
            ("Very confident — highly secure", 41.9),
            ("Somewhat confident — they work most of the time", 44.2),
            ("Not very confident — I think they can be fooled", 8.1),
            ("Not confident at all — easy to trick", 2.3),
            ("I have never thought about this", 3.5),
        ],
    },
    {
        "q": "Q4",
        "text": "Have you personally witnessed or heard of any incident where someone used a fake fingerprint to cheat an attendance system or bypass security?",
        "results": [
            ("Yes, I have personally witnessed it", 20.9),
            ("Yes, I have heard about such incidents from others", 34.9),
            ("I have seen it reported in news or social media", 18.6),
            ("No, I have never heard of such an incident", 25.6),
        ],
    },
    {
        "q": "Q5",
        "text": "If someone tricks a fingerprint scanner using a fake finger, how big of a problem do you think that is?",
        "results": [
            ("Very big problem — could lead to serious crimes like identity theft", 73.3),
            ("A moderate problem — worrying but not very common", 24.4),
            ("A small problem — probably will not affect me", 2.3),
            ("Not a problem at all", 0.0),
        ],
    },
    {
        "q": "Q6",
        "text": "Should fingerprint scanners be able to tell the difference between a real finger and a fake one?",
        "results": [
            ("Yes, all fingerprint scanners must have this feature", 58.1),
            ("Yes, but only for important systems like banks and police", 31.4),
            ("Maybe, only for some systems", 10.5),
            ("No, current scanners are fine as they are", 0.0),
        ],
    },
    {
        "q": "Q7",
        "text": "If a computer system detects a fake fingerprint, would you like to know the reason behind that decision?",
        "results": [
            ("Yes, I always want to know why", 54.7),
            ("Yes, but only in serious situations like court cases", 39.5),
            ("I do not mind as long as it gives the correct result", 4.7),
            ("No, I would just trust the system", 1.2),
        ],
    },
    {
        "q": "Q8",
        "text": "Would you be okay with using AI (Artificial Intelligence) to check fingerprint evidence in a court case?",
        "results": [
            ("Yes, if the AI is accurate and can show its reasoning", 36.0),
            ("Yes, but a human expert should also check the result", 50.0),
            ("Not really — I do not fully trust AI for legal matters", 9.3),
            ("No — AI should not be used for court evidence", 4.7),
        ],
    },
    {
        "q": "Q9",
        "text": "What do you think needs to be improved the most in fingerprint scanners?",
        "results": [
            ("Ability to catch fake fingerprints", 54.7),
            ("Better recognition of wet or damaged fingers", 32.6),
            ("Faster scanning speed", 4.7),
            ("Better protection of stored fingerprint data", 8.1),
            ("Nothing — I am happy with how they work now", 0.0),
        ],
    },
]


# Headline findings used in the thesis narrative
HEADLINES = {
    "daily_users": 81.4,        # Q1 — daily use
    "attendance_use": 51.2,     # Q2 — university/workplace attendance
    "confident_scanner_works": 86.1,   # Q3 — very + somewhat confident
    "heard_of_spoof_incident": 74.4,   # Q4 — 20.9 + 34.9 + 18.6
    "spoof_is_big_problem": 73.3,      # Q5 — very big problem
    "want_liveness_universal": 58.1,   # Q6 — all scanners
    "want_reason_always": 54.7,        # Q7 — always want reason
    "want_reason_conditional": 94.2,   # Q7 — always + in serious cases
    "accept_ai_in_court": 86.0,        # Q8 — yes if XAI + yes with expert
    "expert_oversight_required": 50.0, # Q8 — expert also checks
    "priority_catch_spoof": 54.7,      # Q9 — top improvement
}


def all_percentages_add_to_100(q: dict) -> bool:
    """Sanity check — sum should be ~100 for single-select, may exceed for
    multi-select questions. Used by scripts/verify_survey.py."""
    total = sum(pct for _, pct in q["results"])
    if q.get("multi_select"):
        return total >= 100
    return abs(total - 100.0) < 5.0

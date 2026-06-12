"""Forensic-lab dark mode CSS injection."""
import streamlit as st

TOKENS = {
    "bg_base": "#0B0F14",
    "bg_surface": "#141B23",
    "bg_elevated": "#1C2530",
    "border_subtle": "#2A3441",
    "border_strong": "#3D4A5C",
    "text_primary": "#E6EDF3",
    "text_secondary": "#8B949E",
    "text_muted": "#6E7681",
    "accent_live": "#3FB950",
    "accent_spoof": "#F85149",
    "accent_warn": "#D29922",
    "accent_info": "#58A6FF",
    "accent_neutral": "#A371F7",
}

CSS = """
<style>
:root {
  --bg-base: #0B0F14;
  --bg-surface: #141B23;
  --bg-elevated: #1C2530;
  --border-subtle: #2A3441;
  --border-strong: #3D4A5C;
  --text-primary: #E6EDF3;
  --text-secondary: #8B949E;
  --text-muted: #6E7681;
  --accent-live: #3FB950;
  --accent-spoof: #F85149;
  --accent-warn: #D29922;
  --accent-info: #58A6FF;
  --accent-neutral: #A371F7;
}

/* Hide Streamlit default chrome */
#MainMenu {visibility: hidden;}
header[data-testid="stHeader"] {display: none;}
footer {visibility: hidden;}
section[data-testid="stSidebar"] {display: none;}

/* App background */
.stApp {
  background: var(--bg-base);
  color: var(--text-primary);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, sans-serif;
}

.block-container {
  padding-top: 5rem !important;
  padding-bottom: 4rem !important;
  max-width: 1400px;
}

/* Top nav bar */
.fsd-nav {
  position: fixed;
  top: 0; left: 0; right: 0;
  height: 56px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  padding: 0 32px;
  z-index: 1000;
  font-size: 14px;
}
.fsd-nav-logo {
  font-weight: 700;
  font-size: 16px;
  color: var(--text-primary);
  margin-right: 40px;
  font-family: ui-monospace, "JetBrains Mono", monospace;
}
.fsd-nav-link {
  color: var(--text-secondary);
  text-decoration: none;
  margin-right: 24px;
  padding: 4px 0;
  cursor: pointer;
}
.fsd-nav-link.active {
  color: var(--accent-info);
  border-bottom: 2px solid var(--accent-info);
}
.fsd-nav-spacer { flex: 1; }
.fsd-nav-version {
  color: var(--text-muted);
  font-family: ui-monospace, monospace;
  font-size: 12px;
}

/* Status bar */
.fsd-status {
  position: fixed;
  bottom: 0; left: 0; right: 0;
  height: 32px;
  background: var(--bg-surface);
  border-top: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  padding: 0 32px;
  z-index: 1000;
  font-family: ui-monospace, "JetBrains Mono", monospace;
  font-size: 11px;
  color: var(--text-muted);
}

/* Page title */
.fsd-page-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}
.fsd-page-subtitle {
  color: var(--text-secondary);
  font-size: 14px;
  margin-bottom: 24px;
}

/* Cards */
.fsd-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
}
.fsd-card-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.6px;
  margin-bottom: 8px;
}
.fsd-card-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  font-family: ui-monospace, monospace;
}
.fsd-card-sub {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}

/* Verdict cards */
.fsd-verdict {
  border-radius: 8px;
  padding: 20px;
  text-align: center;
  border: 2px solid var(--border-subtle);
  background: var(--bg-surface);
  margin-bottom: 12px;
}
.fsd-verdict.live { border-color: var(--accent-live); }
.fsd-verdict.spoof { border-color: var(--accent-spoof); }
.fsd-verdict.warn { border-color: var(--accent-warn); }
.fsd-verdict-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.6px;
  margin-bottom: 8px;
}
.fsd-verdict-value {
  font-size: 32px;
  font-weight: 700;
  font-family: ui-monospace, monospace;
  margin-bottom: 4px;
}
.fsd-verdict.live .fsd-verdict-value { color: var(--accent-live); }
.fsd-verdict.spoof .fsd-verdict-value { color: var(--accent-spoof); }
.fsd-verdict.warn .fsd-verdict-value { color: var(--accent-warn); }
.fsd-verdict-sub {
  font-size: 13px;
  color: var(--text-secondary);
  font-family: ui-monospace, monospace;
}

/* Pills / badges */
.fsd-pill {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
  font-family: ui-monospace, monospace;
}
.fsd-pill.live { background: rgba(63,185,80,0.15); color: var(--accent-live); }
.fsd-pill.spoof { background: rgba(248,81,73,0.15); color: var(--accent-spoof); }
.fsd-pill.warn { background: rgba(210,153,34,0.15); color: var(--accent-warn); }
.fsd-pill.info { background: rgba(88,166,255,0.15); color: var(--accent-info); }
.fsd-pill.muted { background: rgba(110,118,129,0.15); color: var(--text-muted); }

/* Streamlit element overrides */
div[data-testid="stMetric"] {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 16px;
}
div[data-testid="stMetricLabel"] {
  color: var(--text-secondary) !important;
  font-size: 11px !important;
  text-transform: uppercase;
  letter-spacing: 0.6px;
}
div[data-testid="stMetricValue"] {
  color: var(--text-primary) !important;
  font-family: ui-monospace, monospace !important;
}

/* Buttons */
.stButton > button {
  background: var(--bg-elevated);
  color: var(--text-primary);
  border: 1px solid var(--border-strong);
  border-radius: 6px;
  font-weight: 500;
  transition: all 0.15s;
}
.stButton > button:hover {
  background: var(--border-strong);
  border-color: var(--accent-info);
}
.stButton > button[kind="primary"] {
  background: var(--accent-info);
  color: var(--bg-base);
  border-color: var(--accent-info);
  font-weight: 600;
}
.stButton > button[kind="primary"]:hover {
  background: #4493e0;
  color: var(--bg-base);
}

/* File uploader */
[data-testid="stFileUploader"] section {
  background: var(--bg-surface);
  border: 2px dashed var(--border-strong);
  border-radius: 8px;
  padding: 32px;
}
[data-testid="stFileUploader"] section:hover {
  border-color: var(--accent-info);
}

/* Text inputs */
[data-baseweb="input"] input, [data-baseweb="textarea"] textarea {
  background: var(--bg-surface) !important;
  color: var(--text-primary) !important;
  border-color: var(--border-subtle) !important;
}

/* Tables */
[data-testid="stDataFrame"] {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
}

/* Tabs */
[data-baseweb="tab-list"] {
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-subtle);
}
[data-baseweb="tab"] {
  color: var(--text-secondary);
  font-weight: 500;
}
[data-baseweb="tab"][aria-selected="true"] {
  color: var(--accent-info);
}

/* Progress bar */
[data-testid="stProgress"] > div > div > div > div {
  background: var(--accent-info);
}

/* Section divider */
.fsd-divider {
  border-top: 1px solid var(--border-subtle);
  margin: 24px 0;
}

/* Code blocks for technical data */
.fsd-mono {
  font-family: ui-monospace, "JetBrains Mono", monospace;
  font-size: 12px;
  color: var(--text-secondary);
}

/* Section header */
.fsd-section-h {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  text-transform: uppercase;
  letter-spacing: 0.8px;
  margin: 16px 0 12px 0;
}

/* Hero */
.fsd-hero {
  text-align: center;
  padding: 48px 0 32px 0;
}
.fsd-hero-title {
  font-size: 36px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 12px;
  line-height: 1.2;
}
.fsd-hero-sub {
  font-size: 16px;
  color: var(--text-secondary);
  max-width: 640px;
  margin: 0 auto;
  line-height: 1.5;
}

/* Feature card */
.fsd-feature {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 24px;
  height: 100%;
}
.fsd-feature-icon {
  font-size: 24px;
  margin-bottom: 12px;
}
.fsd-feature-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}
.fsd-feature-text {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

/* Banner */
.fsd-banner {
  padding: 12px 16px;
  border-radius: 6px;
  font-size: 13px;
  margin-bottom: 16px;
  border-left: 3px solid;
}
.fsd-banner.warn {
  background: rgba(210,153,34,0.1);
  border-left-color: var(--accent-warn);
  color: var(--text-primary);
}
.fsd-banner.info {
  background: rgba(88,166,255,0.1);
  border-left-color: var(--accent-info);
  color: var(--text-primary);
}
.fsd-banner.error {
  background: rgba(248,81,73,0.1);
  border-left-color: var(--accent-spoof);
  color: var(--text-primary);
}
</style>
"""


def apply_theme():
    """Inject the dark mode CSS. Call once at the top of every page."""
    st.markdown(CSS, unsafe_allow_html=True)

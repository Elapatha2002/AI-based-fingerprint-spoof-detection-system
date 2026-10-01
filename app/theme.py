"""Forensic-lab dark mode CSS injection."""
import streamlit as st

TOKENS = {
    "bg_base": "#0B0F14",
    "bg_surface": "#141B23",
    "bg_elevated": "#1C2530",
    "border_subtle": "#2A3441",
    "border_strong": "#3D4A5C",
    "text_primary": "#E6EDF3",
    "text_secondary": "#B6C2D0",
    "text_muted": "#93A1B2",
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
  --text-secondary: #B6C2D0;
  --text-muted: #93A1B2;
  --accent-live: #3FB950;
  --accent-spoof: #F85149;
  --accent-warn: #D29922;
  --accent-info: #58A6FF;
  --accent-neutral: #A371F7;

  /* Spacing scale — 4-point grid */
  --space-1: 4px;  --space-2: 8px;  --space-3: 12px;
  --space-4: 16px; --space-6: 24px; --space-8: 32px;
  --space-12: 48px; --space-16: 64px;

  /* Elevation */
  --elev-1: 0 1px 2px rgba(0,0,0,0.3);
  --elev-2: 0 4px 12px rgba(0,0,0,0.4);
  --elev-3: 0 8px 32px rgba(0,0,0,0.5);

  /* Radius */
  --radius-sm: 4px;  --radius-md: 6px;
  --radius-lg: 8px;  --radius-xl: 12px;

  /* Motion */
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --duration-fast: 120ms;
  --duration-base: 200ms;
}

/* ──────────────────────── Persistent case strip ──────────────────────── */
.fsd-case-strip {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  padding: 12px 20px;
  background: linear-gradient(180deg, #141B23 0%, #11171E 100%);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  margin-bottom: var(--space-4);
  font-family: ui-monospace, "JetBrains Mono", monospace;
  box-shadow: var(--elev-1);
}
.fsd-case-id {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: 0.3px;
}
.fsd-case-divider {
  width: 1px; height: 30px; background: var(--border-subtle);
}
.fsd-case-meta { display: flex; flex-direction: column; gap: 2px; }
.fsd-case-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: var(--text-muted);
}
.fsd-case-value {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
}
.fsd-case-meta-spacer { flex: 1; }

/* ──────────────────────── Confidence gauge ────────────────────────── */
.fsd-gauge {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  padding: var(--space-6) var(--space-4) var(--space-4) var(--space-4);
  margin-bottom: var(--space-3);
}
.fsd-gauge-track {
  position: relative;
  height: 26px;
  background: linear-gradient(90deg,
    rgba(63,185,80,0.16) 0%,
    rgba(210,153,34,0.16) 50%,
    rgba(248,81,73,0.16) 100%);
  border-radius: 13px;
  overflow: visible;
}
.fsd-gauge-uncertainty {
  position: absolute;
  top: 0; bottom: 0;
  background: rgba(210,153,34,0.16);
  border-left: 1px dashed var(--accent-warn);
  border-right: 1px dashed var(--accent-warn);
  pointer-events: none;
}
.fsd-gauge-fill {
  height: 100%;
  border-radius: 13px;
  opacity: 0.50;
  transition: width 0.4s var(--ease-out);
}
.fsd-gauge-marker {
  position: absolute;
  top: -4px; bottom: -4px;
  width: 2px;
}
.fsd-gauge-marker-default { background: var(--text-muted); }
.fsd-gauge-marker-eer { background: var(--accent-info); }
.fsd-gauge-marker-label {
  position: absolute;
  top: -22px;
  left: 50%; transform: translateX(-50%);
  font-size: 9px;
  color: var(--text-muted);
  white-space: nowrap;
  font-family: ui-monospace, monospace;
  letter-spacing: 0.4px;
}
.fsd-gauge-needle {
  position: absolute;
  top: -10px;
  width: 4px; height: 46px;
  background: var(--text-primary);
  border-radius: 2px;
  transform: translateX(-2px);
  box-shadow: 0 0 8px rgba(255,255,255,0.45);
  transition: left 0.4s var(--ease-out);
}
.fsd-gauge-scale {
  display: flex; justify-content: space-between;
  font-size: 10px; color: var(--text-muted);
  margin-top: var(--space-4); letter-spacing: 0.6px;
  text-transform: uppercase;
}
.fsd-gauge-readout {
  text-align: center;
  font-family: ui-monospace, monospace;
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-subtle);
}
.fsd-gauge-note {
  margin-top: var(--space-2);
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.45;
  text-align: center;
}

/* ──────────────────────── Verdict hero treatment ────────────────────── */
.fsd-verdict.spoof {
  border-color: var(--accent-spoof);
  box-shadow: 0 0 24px rgba(248,81,73,0.22);
  animation: spoof-pulse 2.5s var(--ease-out) 1;
}
.fsd-verdict.live {
  border-color: var(--accent-live);
  box-shadow: 0 0 24px rgba(63,185,80,0.18);
}
.fsd-verdict-hero .fsd-verdict-value {
  font-size: 44px;
  line-height: 1.1;
}
@keyframes spoof-pulse {
  0%, 100% { box-shadow: 0 0 24px rgba(248,81,73,0.22); }
  50%      { box-shadow: 0 0 32px rgba(248,81,73,0.40); }
}

/* ──────────────────────── Tech strip (tertiary info) ────────────────── */
.fsd-tech-strip {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  font-family: ui-monospace, monospace;
  font-size: 11px;
  color: var(--text-muted);
  padding: var(--space-2) var(--space-3);
  background: rgba(255,255,255,0.02);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-subtle);
}
.fsd-tech-strip span.sep { color: var(--border-strong); }

/* ──────────────────────── Chips (status bar v2) ──────────────────────── */
.fsd-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-family: ui-monospace, monospace;
  border: 1px solid var(--border-subtle);
  background: rgba(255,255,255,0.02);
}
.fsd-chip-info    { color: var(--accent-info);    border-color: rgba(88,166,255,0.30); }
.fsd-chip-success { color: var(--accent-live);    border-color: rgba(63,185,80,0.30); }
.fsd-chip-warn    { color: var(--accent-warn);    border-color: rgba(210,153,34,0.30); }
.fsd-chip-spoof   { color: var(--accent-spoof);   border-color: rgba(248,81,73,0.30); }
.fsd-chip-muted   { color: var(--text-muted);     border-color: var(--border-subtle); }

/* Override the v1 status bar for the v2 layout */
.fsd-status {
  height: 36px !important;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0 24px;
}
.fsd-status-spacer { flex: 1; }

/* ──────────────────────── XAI interpretation panel ──────────────────── */
.fsd-interpretation {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-left: 4px solid var(--accent-info);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  margin-top: var(--space-4);
}
.fsd-interp-title {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
  font-weight: 600;
}
.fsd-interp-body {
  color: var(--text-primary);
  line-height: 1.6;
  margin-bottom: var(--space-3);
  font-size: 13px;
}
.fsd-interp-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-subtle);
}
.fsd-interp-method {
  font-size: 11px;
  font-weight: 700;
  color: var(--accent-info);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 2px;
}
.fsd-interp-desc {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
}

/* ──────────────────────── Audit drawer + log ────────────────────────── */
.fsd-audit-log {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  padding: var(--space-3);
  font-family: ui-monospace, monospace;
  font-size: 12px;
  max-height: 320px;
  overflow-y: auto;
}
.fsd-audit-row {
  display: grid;
  grid-template-columns: 130px 110px 1fr;
  gap: var(--space-3);
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--border-subtle);
  align-items: baseline;
}
.fsd-audit-row:last-child { border-bottom: none; }
.fsd-audit-ts    { color: var(--text-muted);     font-size: 11px; }
.fsd-audit-actor { color: var(--accent-info);    font-size: 11px; }
.fsd-audit-action{ color: var(--text-primary);   font-size: 12px; }

/* Skeleton loader */
.fsd-skeleton {
  background: linear-gradient(90deg, #141B23 0%, #1C2530 50%, #141B23 100%);
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.5s infinite;
  border-radius: var(--radius-sm);
}
.fsd-skeleton-heatmap { width: 100%; aspect-ratio: 1; }
@keyframes skeleton-shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* Focus rings */
.stButton > button:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px var(--accent-info), 0 0 12px rgba(88,166,255,0.30);
}

/* ──────────────────────── Primary buttons: glow + lift ─────────────────
   Affects "Start Analysis" hero CTA + "Generate PDF" + any other primary
   action across the app. Subtle enough not to be distracting. */
.stButton > button[kind="primary"] {
  background: var(--accent-info) !important;
  color: var(--bg-base) !important;
  border: 1px solid var(--accent-info) !important;
  font-weight: 600 !important;
  font-size: 14px !important;
  padding: 10px 22px !important;
  letter-spacing: 0.3px;
  box-shadow: 0 4px 14px rgba(88,166,255,0.30),
              inset 0 1px 0 rgba(255,255,255,0.18) !important;
  transition: transform var(--duration-fast) var(--ease-out),
              box-shadow var(--duration-base) var(--ease-out),
              background var(--duration-fast) var(--ease-out) !important;
}
.stButton > button[kind="primary"]:hover {
  background: #6BB5FF !important;
  color: var(--bg-base) !important;
  border-color: #6BB5FF !important;
  box-shadow: 0 6px 24px rgba(88,166,255,0.50),
              inset 0 1px 0 rgba(255,255,255,0.25) !important;
  transform: translateY(-1px);
}
.stButton > button[kind="primary"]:active {
  transform: translateY(0);
  box-shadow: 0 2px 8px rgba(88,166,255,0.40) !important;
}

/* ──────────────────────── Secondary buttons: outlined hover ────────────
   Affects "Methodology" hero CTA + "Save to History" + similar. Subtle
   border-glow on hover so secondary CTAs aren't invisible. */
.stButton > button[kind="secondary"],
.stButton > button:not([kind="primary"]) {
  font-weight: 500 !important;
  font-size: 14px !important;
  padding: 10px 20px !important;
  border: 1px solid var(--border-strong) !important;
  transition: border-color var(--duration-fast) var(--ease-out),
              color var(--duration-fast) var(--ease-out),
              background var(--duration-fast) var(--ease-out) !important;
}
.stButton > button[kind="secondary"]:hover,
.stButton > button:not([kind="primary"]):hover {
  border-color: var(--accent-info) !important;
  color: var(--accent-info) !important;
  background: rgba(88,166,255,0.06) !important;
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
  padding-top: 1.5rem !important;
  padding-bottom: 2.5rem !important;
  max-width: 1240px;
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

/* ──────────────────────── Usability and accessibility refresh ────────── */
/*
   These rules deliberately sit after the base theme. They remove the visual
   ambiguity seen in the first iteration: low-emphasis controls, a floating
   navigation row, and status information that obscured page actions.
*/
.stApp {
  min-width: 320px;
  background:
    radial-gradient(circle at 50% -20%, rgba(88,166,255,0.09), transparent 34rem),
    var(--bg-base);
}

/* Product and account context ------------------------------------------------ */
.fsd-app-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 58px;
  padding: 8px 0;
}
.fsd-brand-mark {
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  color: #06101A;
  background: linear-gradient(135deg, #77B9FF, var(--accent-info));
  font-weight: 800;
  font-size: 18px;
  box-shadow: 0 6px 18px rgba(88,166,255,0.24);
}
.fsd-brand-name {
  color: var(--text-primary);
  font-weight: 750;
  font-size: 16px;
  letter-spacing: 0.2px;
}
.fsd-brand-context,
.fsd-account-role {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.4;
}
.fsd-account-summary {
  min-height: 58px;
  display: flex;
  justify-content: center;
  align-items: flex-end;
  flex-direction: column;
  padding: 8px 0;
}
.fsd-account-name {
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 650;
}

/* Streamlit pills are used as one named, keyboard-operable nav group. */
[data-testid="stPills"] {
  margin: 4px 0 20px;
}
[data-testid="stPills"] [role="radiogroup"] {
  gap: 6px;
  flex-wrap: wrap;
}
[data-testid="stPills"] button {
  min-height: 40px !important;
  border-radius: 8px !important;
  color: var(--text-secondary) !important;
  font-weight: 600 !important;
}
[data-testid="stPills"] button[aria-checked="true"],
[data-testid="stPills"] button[aria-pressed="true"] {
  color: #06101A !important;
  background: var(--accent-info) !important;
  border-color: var(--accent-info) !important;
}

/* Clear affordances, sufficiently large targets, and obvious keyboard focus. */
.stButton > button,
[data-testid="stDownloadButton"] > button,
[data-testid="stFileUploader"] button {
  min-height: 44px !important;
  border-radius: 8px !important;
}
.stButton > button:disabled,
[data-testid="stDownloadButton"] > button:disabled {
  opacity: 0.48 !important;
  cursor: not-allowed !important;
}
button:focus-visible,
input:focus-visible,
textarea:focus-visible,
[role="combobox"]:focus-visible,
[data-baseweb="tab"]:focus-visible {
  outline: 3px solid #A9D3FF !important;
  outline-offset: 2px !important;
  box-shadow: none !important;
}

/* Form fields: labels stay visible, and focus cannot rely on colour alone. */
[data-testid="stTextInput"] label,
[data-testid="stTextArea"] label,
[data-testid="stSelectbox"] label,
[data-testid="stRadio"] label,
[data-testid="stFileUploader"] label,
[data-testid="stCheckbox"] label {
  color: var(--text-primary) !important;
  font-weight: 600 !important;
}
[data-baseweb="input"] > div,
[data-baseweb="textarea"] > div,
[data-baseweb="select"] > div {
  min-height: 44px;
  background: var(--bg-surface) !important;
  border-color: var(--border-strong) !important;
  border-radius: 8px !important;
}
[data-baseweb="input"] > div:focus-within,
[data-baseweb="textarea"] > div:focus-within,
[data-baseweb="select"] > div:focus-within {
  border-color: var(--accent-info) !important;
  box-shadow: 0 0 0 3px rgba(88,166,255,0.20) !important;
}
[data-baseweb="input"] input::placeholder,
[data-baseweb="textarea"] textarea::placeholder {
  color: #AAB6C5 !important;
  opacity: 1 !important;
}

/* The server can accept a 50 MB zip; custom guidance below states the
   different single-image limit accurately, so hide Streamlit's generic cap. */
[data-testid="stFileUploader"] small {
  display: none !important;
}
[data-testid="stFileUploader"] section {
  min-height: 146px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(20,27,35,0.72) !important;
}
[data-testid="stFileUploader"] section:focus-within {
  border-color: var(--accent-info) !important;
  box-shadow: 0 0 0 3px rgba(88,166,255,0.20);
}
.fsd-upload-guidance {
  padding: 10px 12px;
  margin-top: 8px;
  border-left: 3px solid var(--accent-info);
  border-radius: 0 7px 7px 0;
  background: rgba(88,166,255,0.08);
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.55;
}
.fsd-upload-guidance strong { color: var(--text-primary); }

/* Page hierarchy and reusable workflow/empty states ------------------------ */
.fsd-page-title {
  font-size: clamp(26px, 3vw, 32px);
  line-height: 1.2;
  letter-spacing: -0.35px;
  margin: 16px 0 6px;
}
.fsd-page-subtitle {
  max-width: 720px;
  color: var(--text-secondary);
  font-size: 15px;
  line-height: 1.55;
  margin-bottom: 28px;
}
.fsd-section-h {
  margin-top: 20px;
  color: var(--text-primary);
}
.fsd-card,
.fsd-feature,
div[data-testid="stMetric"] {
  border-color: var(--border-strong);
  box-shadow: var(--elev-1);
}
.fsd-feature {
  min-height: 178px;
  transition: border-color var(--duration-fast) var(--ease-out),
              transform var(--duration-fast) var(--ease-out);
}
.fsd-feature:hover {
  border-color: rgba(88,166,255,0.72);
  transform: translateY(-2px);
}
.fsd-empty-state {
  max-width: 620px;
  margin: 36px auto 12px;
  padding: 32px;
  text-align: center;
  background: rgba(20,27,35,0.76);
  border: 1px solid var(--border-strong);
  border-radius: 12px;
}
.fsd-empty-icon { font-size: 38px; line-height: 1; }
.fsd-empty-title {
  margin-top: 14px;
  color: var(--text-primary);
  font-size: 18px;
  font-weight: 700;
}
.fsd-empty-message {
  max-width: 460px;
  margin: 8px auto 0;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.55;
}
.fsd-home-hero {
  max-width: 900px;
  margin: 26px auto 28px;
  padding: 40px 32px;
  text-align: center;
  border: 1px solid rgba(61,74,92,0.9);
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(20,27,35,0.98), rgba(20,27,35,0.64));
}
.fsd-home-eyebrow {
  margin-bottom: 12px;
  color: var(--accent-info);
  font-size: 12px;
  font-weight: 750;
  letter-spacing: 0.10em;
  text-transform: uppercase;
}
.fsd-home-title {
  color: var(--text-primary);
  font-size: clamp(30px, 4vw, 46px);
  font-weight: 750;
  line-height: 1.12;
  letter-spacing: -0.65px;
}
.fsd-home-subtitle {
  max-width: 680px;
  margin: 16px auto 0;
  color: var(--text-secondary);
  font-size: 16px;
  line-height: 1.6;
}
.fsd-home-proof {
  margin: 22px auto 0;
  color: var(--text-muted);
  font-size: 13px;
}
.fsd-login-intro {
  margin: 42px 0 20px;
  text-align: center;
}
.fsd-login-mark {
  width: 48px;
  height: 48px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  background: linear-gradient(135deg, #77B9FF, var(--accent-info));
  color: #06101A;
  font-size: 24px;
  font-weight: 800;
  box-shadow: 0 10px 28px rgba(88,166,255,0.28);
}
.fsd-login-title {
  margin-top: 12px;
  color: var(--text-primary);
  font-size: 26px;
  font-weight: 750;
  letter-spacing: -0.3px;
}
.fsd-login-subtitle,
.fsd-login-helper,
.fsd-login-notice {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.5;
}
.fsd-login-helper { margin: 0 0 16px; }
.fsd-login-notice {
  margin: 16px auto 0;
  max-width: 430px;
  text-align: center;
}

/* Login only: a single compact card, with one focus ring per composite input.
   An outline on the inner password input was clipped beside the reveal button,
   producing a white vertical bar. Keep the outer focus ring and toggle focus. */
.st-key-login_panel {
  width: 100% !important;
  max-width: 420px !important;
  margin-inline: auto !important;
}
.st-key-login_panel .fsd-login-intro { margin: 28px 0 16px; }
.st-key-login_panel .fsd-login-title {
  padding: 0;
  margin: 12px 0 0;
  font-size: 26px;
  line-height: 1.3;
}
.st-key-login_card {
  padding: 24px !important;
  border-radius: 12px !important;
}
.st-key-login_panel [data-testid="InputInstructions"] {
  display: none !important;
}
.st-key-login_panel [data-baseweb="input"] {
  min-height: 46px;
  background: var(--bg-surface) !important;
  border: 1px solid var(--border-strong) !important;
  border-radius: 8px !important;
}
.st-key-login_panel [data-baseweb="input"]:focus-within {
  border-color: var(--accent-info) !important;
  outline: 2px solid #A9D3FF !important;
  outline-offset: 2px !important;
}
.st-key-login_panel [data-baseweb="input"] > div,
.st-key-login_panel [data-baseweb="input"] > div:focus-within {
  border: 0 !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  background: transparent !important;
}
.st-key-login_panel [data-baseweb="input"] input:focus-visible {
  outline: none !important;
  box-shadow: none !important;
}
.st-key-login_panel [data-baseweb="input"] button {
  min-width: 44px;
  min-height: 44px;
  border: 0 !important;
  background: transparent !important;
}
.st-key-login_panel [data-baseweb="input"] button:focus-visible {
  outline: 2px solid #A9D3FF !important;
  outline-offset: -4px !important;
}
.st-key-login_panel [data-testid="stFormSubmitButton"] button {
  min-height: 46px;
  color: #06101A !important;
  font-weight: 600;
  border-radius: 8px;
}
@media (max-width: 480px) {
  .st-key-login_card { padding: 20px !important; }
  .st-key-login_panel .fsd-login-intro { margin-top: 12px; }
}

/* The status content remains available without covering controls. */
.fsd-status {
  position: static !important;
  height: auto !important;
  min-height: 44px;
  margin-top: 36px;
  padding: 10px 0 !important;
  background: transparent !important;
  border-top: 1px solid var(--border-subtle);
  border-bottom: 0;
  flex-wrap: wrap;
}
.fsd-status-spacer { flex: 1 1 24px; }
.fsd-chip {
  min-height: 24px;
  padding: 3px 9px;
  color: var(--text-secondary);
}

@media (max-width: 760px) {
  .block-container {
    padding: 12px 16px 28px !important;
  }
  .fsd-app-brand { min-height: 50px; }
  .fsd-account-summary {
    min-height: 50px;
    align-items: flex-end;
  }
  .fsd-brand-context,
  .fsd-account-role { display: none; }
  .fsd-home-hero { margin-top: 14px; padding: 28px 18px; }
  .fsd-feature { min-height: 0; }
  .fsd-empty-state { margin-top: 24px; padding: 24px 18px; }
  .fsd-audit-row {
    grid-template-columns: 1fr;
    gap: 3px;
  }
}
</style>
"""


def apply_theme():
    """Inject the dark mode CSS. Call once at the top of every page."""
    st.markdown(CSS, unsafe_allow_html=True)

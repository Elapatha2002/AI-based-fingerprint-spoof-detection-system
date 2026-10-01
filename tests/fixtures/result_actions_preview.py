"""Isolated result-action visual fixture; all persistence/audit calls are mocked."""
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'app'))
import streamlit as st
from app.theme import apply_theme
from app.services import persistence
from state import init_state
from views import single_result

st.set_page_config(layout='wide')
apply_theme()
init_state()
with patch.object(persistence, 'save_single_analysis', return_value='AN-PREVIEW'), \
        patch.object(single_result, 'log_action'):
    single_result._render_result_actions('fixture.png', b'fixture',
        {'case_id':'CASE-PREVIEW', 'examiner':'Fixture'},
        {'label':'live', 'confidence':.9, 'model':{'name':'fixture'}}, {})

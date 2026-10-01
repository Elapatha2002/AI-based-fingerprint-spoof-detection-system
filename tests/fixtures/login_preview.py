"""Isolated visual-test page. All submissions fail; never accesses cloud data."""
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st
from app.theme import apply_theme
from app.views import login
from app.services import auth

st.set_page_config(layout='wide')
apply_theme()
with patch.object(auth, 'login', return_value=(False, 'Invalid username or password.')):
    login.render()

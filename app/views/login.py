"""Login screen — shown when nobody is signed in."""
import streamlit as st

from app.services import auth


def render():
    """Render sign-in and return True when authentication just succeeded."""
    authenticated = False
    panel = st.empty()
    with panel.container():
        with st.container(key='login_panel'):
            st.markdown(
                """
                <div class='fsd-login-intro'>
                  <div class='fsd-login-mark'>
                    <img src='app/static/brand/fsd-xai-logo.png'
                         alt='FSD-XAI fingerprint shield logo'>
                  </div>
                  <h1 class='fsd-login-title'>FSD-XAI</h1>
                </div>
                """,
                unsafe_allow_html=True,
            )

            with st.container(border=True, key='login_card'):
                with st.form("login_form", clear_on_submit=False, border=False):
                    username = st.text_input(
                        "Username",
                        key="login_username",
                        autocomplete="username",
                    )
                    password = st.text_input(
                        "Password",
                        type="password",
                        key="login_password",
                        autocomplete="current-password",
                    )
                    submitted = st.form_submit_button(
                        "Sign in", type="primary", width="stretch",
                    )

                    if submitted:
                        ok, err = auth.login(username.strip(), password)
                        if ok:
                            st.session_state.current_page = "home"
                            authenticated = True
                        else:
                            st.error(err)
    if authenticated:
        panel.empty()
    return authenticated


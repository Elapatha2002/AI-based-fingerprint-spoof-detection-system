"""Login screen — shown when nobody is signed in."""
import streamlit as st

from app.services import auth


def render():
    """Render an intentionally small, focused sign-in task."""
    _, mid, _ = st.columns([1, 1.25, 1])
    with mid:
        st.markdown(
            """
            <div class='fsd-login-intro'>
              <div class='fsd-login-mark' aria-hidden='true'>F</div>
              <div class='fsd-login-title'>FSD-XAI</div>
              <div class='fsd-login-subtitle'>
                Forensic spoof detection and explanation workspace
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            st.markdown(
                "<div class='fsd-section-h' style='margin:0 0 4px;'>"
                "Sign in to your workspace</div>"
                "<div class='fsd-login-helper'>Use the examiner account assigned to you.</div>",
                unsafe_allow_html=True,
            )

            with st.form("login_form", clear_on_submit=False):
                username = st.text_input(
                    "Username",
                    key="login_username",
                    placeholder="Enter your username",
                    help="Use the username supplied by your system administrator.",
                )
                password = st.text_input(
                    "Password",
                    type="password",
                    key="login_password",
                    placeholder="Enter your password",
                )
                submitted = st.form_submit_button(
                    "Sign in", type="primary", width="stretch",
                )

                if submitted:
                    ok, err = auth.login(username.strip(), password)
                    if ok:
                        st.session_state.current_page = "home"
                        st.rerun()
                    else:
                        st.error(err)

        st.markdown(
            "<div class='fsd-login-notice'>"
            "Authorised forensic examiners only. If you have lost access, "
            "contact your system administrator to reset your account."
            "</div>",
            unsafe_allow_html=True,
        )

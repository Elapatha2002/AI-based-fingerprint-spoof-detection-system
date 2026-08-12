"""Login screen — shown when nobody is signed in."""
import streamlit as st

from app.services import auth


def render():
    # Center the login card
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown("<div style='height:60px;'></div>", unsafe_allow_html=True)

        st.markdown(
            """
            <div style='text-align:center;margin-bottom:24px;'>
              <div style='font-size:44px;line-height:1;'>◼</div>
              <div style='font-size:22px;font-weight:600;margin-top:8px;
                          color:var(--text-primary);'>FSD-XAI</div>
              <div style='font-size:13px;color:var(--text-muted);margin-top:4px;'>
                Forensic Spoof Detection · Explainable AI
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            st.markdown(
                "<div class='fsd-section-h' style='margin-bottom:12px;'>"
                "Sign in</div>",
                unsafe_allow_html=True,
            )

            with st.form("login_form", clear_on_submit=False):
                username = st.text_input(
                    "Username",
                    key="login_username",
                    placeholder="admin or examiner name",
                )
                password = st.text_input(
                    "Password",
                    type="password",
                    key="login_password",
                    placeholder="Enter your password",
                )
                submitted = st.form_submit_button(
                    "Sign in", type="primary", use_container_width=True,
                )

                if submitted:
                    ok, err = auth.login(username.strip(), password)
                    if ok:
                        st.session_state.current_page = "home"
                        st.rerun()
                    else:
                        st.error(err)

        st.markdown(
            "<div style='color:var(--text-muted);font-size:11px;"
            "text-align:center;margin-top:16px;'>"
            "Access is limited to authorised forensic examiners. "
            "Contact your system administrator for an account."
            "</div>",
            unsafe_allow_html=True,
        )

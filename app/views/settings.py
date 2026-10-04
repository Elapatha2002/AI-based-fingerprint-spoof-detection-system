"""Super-admin account management and examiner self-service password changes."""
import streamlit as st
from html import escape

from components.cards import page_title, banner
from components.model_picker import render_model_picker
from app.services import auth, database


def render():
    if not auth.is_logged_in():
        return
    if not auth.is_super_admin():
        page_title('My account', 'Review your account and change your password.')
        _render_my_account()
        return

    page_title("System Administration",
               "Create, review, and manage access for forensic examiners and model configurations.")

    tab_users, tab_new, tab_model, tab_account = st.tabs(
        ["Users", "Add examiner", "Model configuration", "My account"]
    )

    with tab_users:
        _render_user_list()

    with tab_new:
        _render_add_user_form()

    with tab_model:
        st.markdown(
            "<div class='fsd-section-h'>Active model configuration</div>",
            unsafe_allow_html=True,
        )
        st.caption(
            "Changing the model affects new analyses only. Record the selected "
            "model and checkpoint in the case record before use."
        )
        render_model_picker()

    with tab_account:
        _render_my_account()


def _account_change(function, *args, **kwargs):
    try:
        function(*args, **kwargs)
        return True
    except (PermissionError, ValueError) as error:
        st.error(str(error))
    except Exception:
        st.error('The account change could not be saved. Check the database connection and try again.')
    return False


def _render_user_list():
    st.markdown(
        "<div class='fsd-section-h'>Existing accounts</div>",
        unsafe_allow_html=True,
    )

    users = database.list_users(include_inactive=True)
    if not users:
        banner("No user accounts yet.", kind="info")
        return

    for u in users:
        with st.container(border=True):
            top = st.columns([2, 2, 1, 1, 1, 1])
            with top[0]:
                st.markdown(
                    f"<div style='font-size:14px;font-weight:600;'>{escape(u['full_name'])}</div>"
                    f"<div class='fsd-mono' style='color:var(--text-muted);font-size:12px;'>"
                    f"@{escape(u['username'])}</div>",
                    unsafe_allow_html=True,
                )
            with top[1]:
                role_badge = ("Super Admin" if u["role"] == "super_admin"
                              else "Examiner")
                st.markdown(
                    f"<div style='font-size:12px;color:var(--text-muted);'>Role</div>"
                    f"<div style='font-size:14px;'>{role_badge}</div>",
                    unsafe_allow_html=True,
                )
            with top[2]:
                status = "Active" if u["active"] else "Deactivated"
                color = "var(--accent-info)" if u["active"] else "var(--text-muted)"
                st.markdown(
                    f"<div style='font-size:12px;color:var(--text-muted);'>Status</div>"
                    f"<div style='font-size:14px;color:{color};'>{status}</div>",
                    unsafe_allow_html=True,
                )
            with top[3]:
                last = u.get("last_login") or "never"
                if last != "never":
                    last = last[:10]
                st.markdown(
                    f"<div style='font-size:12px;color:var(--text-muted);'>Last login</div>"
                    f"<div class='fsd-mono' style='font-size:12px;'>{last}</div>",
                    unsafe_allow_html=True,
                )

            # Actions: super admin can edit any account except we prevent
            # deactivating the only remaining super admin (would lock out).
            current = auth.current_user()
            is_self = current and current.get("user_id") == u["user_id"]
            is_last_admin = (u["role"] == "super_admin"
                             and sum(1 for x in users
                                     if x["role"] == "super_admin"
                                     and x["active"]) <= 1
                             and u["active"])

            with top[4]:
                key = f"edit_{u['user_id']}"
                if st.button("Edit", key=key, width="stretch"):
                    st.session_state[f"editing_{u['user_id']}"] = True

            with top[5]:
                # Deactivation is consequential. Require an explicit second
                # click and offer a clear exit rather than disabling an
                # account immediately from a list row.
                new_active = 0 if u["active"] else 1
                verb = "Disable" if u["active"] else "Enable"
                disabled = is_self or (u["active"] and is_last_admin)
                confirm_key = f"confirm_toggle_{u['user_id']}"
                awaiting_confirmation = bool(st.session_state.get(confirm_key))
                button_label = (
                    "Confirm disable" if u["active"] and awaiting_confirmation
                    else verb
                )
                if st.button(button_label, key=f"toggle_{u['user_id']}",
                              width="stretch", disabled=disabled):
                    if u["active"] and not awaiting_confirmation:
                        st.session_state[confirm_key] = True
                        st.rerun()
                    else:
                        if not _account_change(auth.update_account, u['user_id'], active=new_active):
                            return
                        st.session_state.pop(confirm_key, None)
                        st.rerun()

            if u["active"] and st.session_state.get(
                    f"confirm_toggle_{u['user_id']}"):
                notice_col, cancel_col, _ = st.columns([3, 1, 2])
                with notice_col:
                    st.warning(
                        f"Disable {u['full_name']}? They will not be able to sign in."
                    )
                with cancel_col:
                    if st.button("Cancel", key=f"cancel_toggle_{u['user_id']}",
                                 width="stretch"):
                        st.session_state.pop(f"confirm_toggle_{u['user_id']}", None)
                        st.rerun()

            # Inline edit panel
            if st.session_state.get(f"editing_{u['user_id']}"):
                _render_edit_panel(u, is_last_admin=is_last_admin,
                                   is_self=is_self)

            with st.expander(f"Delete account @{u['username']}"):
                st.warning('Deletion permanently removes this login account, not its cases or audit records. '
                           'Disable the account instead if access may be needed again.')
                confirmation = st.text_input('Type the exact username to confirm',
                    key=f"delete_confirmation_{u['user_id']}")
                if st.button('Delete account permanently', key=f"delete_{u['user_id']}",
                             disabled=is_self or is_last_admin):
                    if _account_change(auth.delete_account, u['user_id'], confirmation):
                        st.rerun()


def _render_edit_panel(u: dict, *, is_last_admin: bool, is_self: bool):
    st.markdown("<div class='fsd-divider'></div>", unsafe_allow_html=True)
    edit_cols = st.columns([1, 1])

    with edit_cols[0]:
        new_full_name = st.text_input(
            "Full name",
            value=u["full_name"],
            key=f"fn_{u['user_id']}",
        )
        new_email = st.text_input(
            "Email",
            value=u.get("email", "") or "",
            key=f"em_{u['user_id']}",
        )
        role_options = ["examiner", "super_admin"]
        role_default = role_options.index(u["role"])
        # Prevent demoting the last active super admin
        role_disabled = is_last_admin
        new_role = st.selectbox(
            "Role",
            role_options,
            index=role_default,
            key=f"rl_{u['user_id']}",
            disabled=role_disabled,
            help=("Cannot demote the last active super admin"
                  if role_disabled else None),
        )

    with edit_cols[1]:
        st.markdown(
            "<div style='font-size:12px;color:var(--text-muted);"
            "margin-bottom:8px;'>Reset password (leave blank to keep current)"
            "</div>",
            unsafe_allow_html=True,
        )
        new_pwd = st.text_input(
            "New password",
            type="password",
            key=f"pw_{u['user_id']}",
            placeholder=f"Min {auth.MIN_PASSWORD_LEN} characters",
        )
        confirm_pwd = st.text_input(
            "Confirm password",
            type="password",
            key=f"cp_{u['user_id']}",
        )

    save, cancel = st.columns([1, 1])
    with save:
        if st.button("Save changes", type="primary",
                      key=f"sv_{u['user_id']}", width="stretch"):
            if not new_full_name.strip():
                st.error('Full name is required.')
                return
            updates = {}
            if new_full_name.strip() and new_full_name != u["full_name"]:
                updates["full_name"] = new_full_name.strip()
            if new_email != (u.get("email") or ""):
                updates["email"] = new_email.strip()
            if new_role != u["role"] and not role_disabled:
                updates["role"] = new_role
            if new_pwd:
                pwd_err = auth.password_error(new_pwd)
                if pwd_err:
                    st.error(pwd_err)
                    return
                if new_pwd != confirm_pwd:
                    st.error("Passwords do not match.")
                    return
                updates["password"] = new_pwd

            if updates:
                if not _account_change(auth.update_account, u['user_id'], **updates):
                    return
                st.success("Changes saved.")
                st.session_state[f"editing_{u['user_id']}"] = False
                st.rerun()
            else:
                st.info("Nothing to update.")

    with cancel:
        if st.button("Cancel", key=f"cn_{u['user_id']}",
                      width="stretch"):
            st.session_state[f"editing_{u['user_id']}"] = False
            st.rerun()


def _render_add_user_form():
    st.markdown(
        "<div class='fsd-section-h'>Create a new examiner account</div>",
        unsafe_allow_html=True,
    )

    with st.form("add_user_form", clear_on_submit=True):
        cols = st.columns([1, 1])
        with cols[0]:
            username = st.text_input(
                "Username *",
                placeholder="e.g. p.perera",
                help="Used to log in. Cannot be changed later.",
            )
            full_name = st.text_input(
                "Full name *",
                placeholder="Analyst full name — appears as examiner on cases",
            )
            email = st.text_input("Email", placeholder="Optional")

        with cols[1]:
            role = st.selectbox(
                "Role",
                ["examiner", "super_admin"],
                index=0,
                help="Examiner: can run analyses. Super admin: full user management.",
            )
            password = st.text_input(
                "Password *",
                type="password",
                placeholder=f"Min {auth.MIN_PASSWORD_LEN} characters",
            )
            password2 = st.text_input(
                "Confirm password *",
                type="password",
            )

        submitted = st.form_submit_button(
            "Create account", type="primary", width="stretch",
        )

        if submitted:
            if not (username and full_name and password):
                st.error("Username, full name, and password are required.")
                return
            if database.get_user_by_username(username.strip()):
                st.error(f"Username '{username}' is already taken.")
                return
            pwd_err = auth.password_error(password)
            if pwd_err:
                st.error(pwd_err)
                return
            if password != password2:
                st.error("Passwords do not match.")
                return

            saved = _account_change(auth.create_account,
                username=username.strip(),
                password=password,
                role=role,
                full_name=full_name.strip(),
                email=email.strip(),
            )
            if saved:
                st.success(f"User '{username}' created. Open the Users tab to manage the account.")


def _render_my_account():
    st.markdown(
        "<div class='fsd-section-h'>My account</div>",
        unsafe_allow_html=True,
    )
    me = auth.current_user()
    if not me:
        return

    fresh = database.get_user(me["user_id"])
    if not fresh:
        st.error("Account not found.")
        return

    st.markdown(
        f"""
        <div style='font-size:14px;line-height:2;'>
          <b>Username:</b> {escape(fresh['username'])}<br/>
          <b>Full name:</b> {escape(fresh['full_name'])}<br/>
          <b>Role:</b> {fresh['role']}<br/>
          <b>Email:</b> {escape(fresh.get('email') or '—')}<br/>
          <b>Last login:</b> {fresh.get('last_login') or 'never'}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div class='fsd-divider'></div>", unsafe_allow_html=True)
    st.markdown("<div class='fsd-section-h'>Change my password</div>",
                 unsafe_allow_html=True)

    with st.form("my_pwd_form", clear_on_submit=True):
        current_pwd = st.text_input("Current password", type="password")
        new_pwd = st.text_input("New password", type="password",
                                 placeholder=f"Min {auth.MIN_PASSWORD_LEN} characters")
        confirm_pwd = st.text_input("Confirm new password", type="password")
        submitted = st.form_submit_button("Update password", type="primary")

        if submitted:
            fresh_with_hash = database.get_user_by_username(fresh["username"])
            if not auth.verify_password(current_pwd,
                                         fresh_with_hash["password_hash"]):
                st.error("Current password is incorrect.")
                return
            pwd_err = auth.password_error(new_pwd)
            if pwd_err:
                st.error(pwd_err)
                return
            if new_pwd != confirm_pwd:
                st.error("New passwords do not match.")
                return
            if _account_change(auth.change_password, current_pwd, new_pwd):
                st.rerun()

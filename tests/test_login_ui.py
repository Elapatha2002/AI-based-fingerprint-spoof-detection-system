"""Login interaction tests; no connection to the application database."""
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from app.services import auth

SCRIPT = '''
import streamlit as st
from app.theme import apply_theme
from app.views import login
apply_theme()
if st.session_state.get('current_page') == 'home':
    st.success('Signed in')
else:
    login.render()
'''


class LoginUITests(unittest.TestCase):
    def test_minimal_form_with_visible_labels_and_no_placeholders(self):
        app = AppTest.from_string(SCRIPT).run()
        self.assertFalse(app.exception)
        self.assertEqual([i.label for i in app.text_input], ['Username', 'Password'])
        self.assertTrue(all(not i.placeholder for i in app.text_input))
        self.assertEqual([b.label for b in app.button], ['Sign in'])
        self.assertFalse(app.get('form')[0].proto.form.border)
        copy = '\n'.join(m.value for m in app.markdown)
        self.assertNotIn('Use the examiner account assigned', copy)
        self.assertNotIn('Sign in to your workspace', copy)
        self.assertNotIn('Authorised forensic examiners only.', copy)

    def test_invalid_login_shows_error_and_stays_on_login(self):
        with patch.object(auth, 'login', return_value=(False, 'Invalid username or password.')) as signin:
            app = AppTest.from_string(SCRIPT).run()
            app.text_input(key='login_username').input(' examiner ')
            app.text_input(key='login_password').input('wrong-password')
            app.button[0].click().run()
            self.assertFalse(app.exception)
            signin.assert_called_once_with('examiner', 'wrong-password')
            self.assertEqual(app.error[0].value, 'Invalid username or password.')

    def test_success_keeps_existing_authentication_flow(self):
        with patch.object(auth, 'login', return_value=(True, '')):
            app = AppTest.from_string(SCRIPT).run()
            app.text_input(key='login_username').input('examiner')
            app.text_input(key='login_password').input('fixture-password')
            app.button[0].click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['current_page'], 'home')


if __name__ == '__main__':
    unittest.main()

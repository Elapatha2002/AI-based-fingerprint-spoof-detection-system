"""Interactive Supabase setup. Run: python -m app.setup_supabase

Only running this command writes to Supabase. No secrets are command arguments
or printed. .env.supabase holds the restricted runtime credentials, not the
Supabase administrator password. This starts a fresh application database; it
does not copy or overwrite the existing SQLite research/case records.
"""
import argparse
import getpass
import os
from pathlib import Path
import secrets
import sys
from urllib.parse import quote, urlsplit, unquote

PROJECT = 'cbifgdvmohxaxvjlxdkx'
HOST = 'aws-0-ap-southeast-1.pooler.supabase.com'
ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT/'.env.supabase'


def url_for(username, password, host=HOST):
    return f'postgresql://{quote(username, safe="")}:{quote(password, safe="")}@{host}:5432/postgres?sslmode=require'


def write_configuration(values):
    from dotenv import set_key
    # New secret files have owner-only permissions on POSIX. Windows inherits
    # the workspace ACL; the user must keep their Windows account private.
    if not CONFIG.exists():
        descriptor = os.open(CONFIG, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
    if os.name != 'nt':
        CONFIG.chmod(0o600)
    for key, value in values.items():
        set_key(str(CONFIG), key, str(value), quote_mode='always')


def password_twice(label):
    first = getpass.getpass(label + ': ')
    if first != getpass.getpass('Type it again: '):
        raise ValueError('Passwords did not match. Nothing was provisioned.')
    if len(first) < 12:
        raise ValueError('Choose a password with at least 12 characters.')
    return first


def check():
    from app.services import database
    if not database.using_postgres():
        raise ValueError('Supabase is not configured. Run python -m app.setup_supabase first.')
    database.init_db()
    with database.connect() as conn:
        info = conn.execute('SELECT current_user AS role').fetchone()
    print('Database connection: OK. Runtime role:', info['role'])
    print('Application accounts:', database.user_count())
    from app.services import storage
    service = storage.get_storage()
    if isinstance(service, storage.LocalStorageService):
        print('Files: LOCAL ONLY. Finish S3 configuration before hosting without persistent disk.')
    else:
        ok, _ = service.health_check()
        if not ok:
            raise ValueError('Database works, but storage is unreachable. Check the S3 keys/endpoint privately.')
        print('Cloud evidence bucket connection: OK (read-only check).')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Read-only connection/schema checks.')
    args = parser.parse_args()
    try:
        if args.check:
            check()
            return 0
        import psycopg
        from dotenv import dotenv_values
        from app.services import database, auth
        from app.supabase_schema import provision, verify_private_bucket, RUNTIME_ROLE

        print('FSD-XAI Supabase setup\nProject: ' + PROJECT)
        print('This creates the private application tables and first super admin. Existing SQLite files are untouched.')
        print('Passwords are hidden as you type. Do not paste them into chat.')
        existing = dotenv_values(CONFIG) if CONFIG.exists() else {}
        previous_url = existing.get('DATABASE_URL')
        if database.DATABASE_URL and database.DATABASE_URL != previous_url:
            raise ValueError('A different DATABASE_URL is already active outside .env.supabase. Clear or update that environment setting privately before using this wizard; no database was changed.')
        if previous_url:
            parts = urlsplit(previous_url)
            if parts.hostname != HOST or unquote(parts.username or '') != f'{RUNTIME_ROLE}.{PROJECT}':
                raise ValueError('Existing configuration points elsewhere. Keep it; do not overwrite it with this project setup.')
            runtime_password = unquote(parts.password or '')
        else:
            runtime_password = secrets.token_urlsafe(40)
        admin_password = getpass.getpass('1. Supabase DATABASE password (not your website login): ')
        if not admin_password:
            raise ValueError('Database password is required.')
        admin_url = url_for('postgres.' + PROJECT, admin_password)
        runtime_url = url_for(RUNTIME_ROLE + '.' + PROJECT, runtime_password)
        # Check the connection before asking for further secrets. No writes yet.
        with psycopg.connect(admin_url, connect_timeout=10) as conn:
            conn.execute('SELECT 1')
        print('Supabase database password accepted.')
        admin_name = input('2. Your application administrator username [admin]: ').strip() or 'admin'
        full_name = input('3. Your full name: ').strip()
        if not full_name:
            raise ValueError('Full name is required.')
        login_password = password_twice('4. Choose your APPLICATION login password (12+ characters)')
        config = dict(DATABASE_URL=runtime_url, FSDXAI_OFFLINE_MODE='0',
                      FSDXAI_STORAGE_BACKEND='local')
        configure_storage = input('5. Connect Supabase file storage now? [Y/n]: ').strip().lower() != 'n'
        if configure_storage:
            print('In Supabase, open Storage > S3 configuration. Copy the endpoint and region there.')
            endpoint = input('S3 endpoint (https://.../storage/v1/s3): ').strip()
            parsed = urlsplit(endpoint)
            if (parsed.scheme != 'https' or parsed.hostname not in
                    (PROJECT+'.supabase.co', PROJECT+'.storage.supabase.co') or
                    parsed.path.rstrip('/') != '/storage/v1/s3' or parsed.username or parsed.query):
                raise ValueError('Use the S3 endpoint for project ' + PROJECT + '.')
            region = input('S3 region [ap-southeast-1]: ').strip() or 'ap-southeast-1'
            access = getpass.getpass('S3 Access Key ID (hidden): ').strip()
            secret = getpass.getpass('S3 Secret Access Key (hidden): ').strip()
            if not access or not secret:
                raise ValueError('Both S3 keys are required. They are not the publishable/anon API key.')
            config.update(FSDXAI_STORAGE_BACKEND='supabase', SUPABASE_STORAGE_BUCKET='fingerprint-evidence',
                          SUPABASE_S3_ENDPOINT=endpoint, SUPABASE_S3_REGION=region,
                          SUPABASE_S3_ACCESS_KEY_ID=access, SUPABASE_S3_SECRET_ACCESS_KEY=secret)
            with psycopg.connect(admin_url, connect_timeout=10) as conn:
                verify_private_bucket(conn, 'fingerprint-evidence')
        if input('6. Type SETUP to create/update this project application schema: ').strip() != 'SETUP':
            print('Cancelled. No configuration or project changes made.')
            return 0
        # Save the generated runtime secret before provisioning, so an interrupted
        # setup can resume without losing it. Never save the database admin secret.
        write_configuration(config)
        with psycopg.connect(admin_url, connect_timeout=10) as conn:
            provision(conn, runtime_password, allow_existing=bool(previous_url))
        os.environ.update(config)
        database.DATABASE_URL = runtime_url
        database.init_db()
        created = database.bootstrap_admin(admin_name, auth.hash_password(login_password), full_name)
        print('First super admin created.' if created else 'Existing accounts kept. No existing password was changed.')
        check()
        print('\nSetup complete. Start the application:\npython -m streamlit run app/streamlit_app.py')
        print('Sign in using your APPLICATION username/password. Use Settings > Add examiner.')
        print('Private configuration: .env.supabase. Never commit or share this file.')
        return 0
    except KeyboardInterrupt:
        print('\nStopped. If setup had started, rerun it to resume safely.')
        return 130
    except Exception as error:
        # Database exceptions may embed usernames/URLs; never print their text.
        if isinstance(error, ValueError):
            print('Setup needs attention:', str(error))
        elif isinstance(error, ModuleNotFoundError):
            print('Install dependencies first: python -m pip install -r requirements-supabase.txt')
        else:
            print('Setup/check failed (' + type(error).__name__ + '). Check connectivity, database password, and storage settings privately.')
            print('If configuration was saved, rerun setup to resume. Do not share a connection string containing a password.')
        return 1


if __name__ == '__main__':
    sys.exit(main())

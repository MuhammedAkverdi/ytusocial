from playwright.sync_api import sync_playwright
import time
import os

# create test user directly in DB so we can login via UI
import sys
import pathlib
# Ensure project root is on sys.path so imports like `app` work when running tests directly
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import app as flask_app
from extensions import db
from models import User
from werkzeug.security import generate_password_hash

BASE = os.environ.get('BASE_URL','http://localhost:5002')

TEST_PASSWORD = 'Password123!'

def ensure_test_user():
    unique = str(int(time.time()))
    test_email = f'e2e_user_{unique}@test.local'
    test_handle = f'e2e_{unique}'
    with flask_app.app_context():
        db.create_all()
        if not User.query.filter_by(email=test_email).first():
            u = User(email=test_email, username=test_handle, password=generate_password_hash(TEST_PASSWORD), handle=test_handle, is_verified=True)
            db.session.add(u)
            db.session.commit()
    return test_email, TEST_PASSWORD

def run():
    email, password = ensure_test_user()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Login using created user
        page.goto(f"{BASE}/login")
        page.fill('input[name="email"]', email)
        page.fill('input[name="password"]', password)
        page.click('button[type="submit"]')
        time.sleep(1)

        # Visit main page
        page.goto(f"{BASE}/")
        time.sleep(1)

        results = {}
        results['index_title'] = page.title()

        # Find a comment input (first .comment-input or .detail-comment-input)
        input_sel = None
        if page.locator('.detail-comment-input').count() > 0:
            input_sel = '.detail-comment-input'
        elif page.locator('.comment-input').count() > 0:
            input_sel = '.comment-input'

        results['found_comment_input'] = bool(input_sel)

        if input_sel:
            # Focus and type @ to trigger mention
            page.click(input_sel)
            page.type(input_sel, '@')
            time.sleep(0.5)
            # type query
            page.type(input_sel, 'a')
            time.sleep(1)
            # check if suggestion box visible
            suggestion = page.locator('#mention-suggestions-global')
            results['suggestions_visible'] = suggestion.is_visible()

            # if visible, pick first item
            if suggestion.is_visible():
                # click first .mention-item
                if page.locator('.mention-item').count() > 0:
                    page.locator('.mention-item').first.click()
                    time.sleep(0.5)
                    results['after_insert_value'] = page.locator(input_sel).input_value()

        # Test send_audio flow by navigating to a chat if exists
        try:
            # create a temporary wav file
            wav_dir = os.path.join(os.getcwd(), 'tests')
            os.makedirs(wav_dir, exist_ok=True)
            wav_path = os.path.join(wav_dir, 'tmp_test_audio.wav')
            with open(wav_path, 'wb') as f:
                f.write(b'TESTAUDIO')

            if page.locator('input[type=file][name=audio]').count() > 0:
                page.set_input_files('input[type=file][name=audio]', wav_path)
                time.sleep(0.5)
                # submit nearest form
                page.locator('input[type=file][name=audio]').first.evaluate("el => el.closest('form').querySelector('button[type=submit]').click()")
                time.sleep(1)
                results['audio_tested'] = True
            else:
                results['audio_tested'] = False
        except Exception as e:
            results['audio_error'] = str(e)

        # Close browser
        browser.close()
        print(results)

if __name__ == '__main__':
    run()

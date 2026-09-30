"""Browser checks. Test events are intercepted in memory, never published."""
import hashlib
import json
import threading
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path.cwd()
assert hashlib.sha256((ROOT / 'nun-logo.jpg').read_bytes()).hexdigest() == 'fcb558a08bf4d29cf3d16fa62975a4fa342392514aa1f68f1192a3d4265bf795', 'Logo must match the actual school upload'
server = ThreadingHTTPServer(('127.0.0.1', 8765), partial(SimpleHTTPRequestHandler, directory=str(ROOT)))
threading.Thread(target=server.serve_forever, daemon=True).start()
RAW = 'https://raw.githubusercontent.com/nun-art/nun-parents-calendar/main/calendar-data.json'
PAGE = 'http://127.0.0.1:8765/index.html'
fixtures = [
    {'id': 'test-parent', 'uid': 'testparent@google.com', 'title': 'TEST ONLY Coffee Morning', 'description': 'Parents are invited. Audience: Primary Parents', 'location': 'Test hall', 'start': '2026-10-01T09:00:00+03:00', 'end': '2026-10-01T10:00:00+03:00', 'startDay': '2026-10-01', 'endDay': '2026-10-01', 'allDay': False, 'semester': 's1', 'status': 'confirmed'},
    {'id': 'test-break', 'uid': 'testbreak@google.com', 'title': 'TEST ONLY Mid-Semester Break', 'description': 'No school', 'location': '', 'start': '2026-10-15', 'end': '2026-10-26', 'startDay': '2026-10-15', 'endDay': '2026-10-26', 'allDay': True, 'semester': 's1', 'status': 'confirmed'},
    {'id': 'test-s2', 'uid': 'testmock@google.com', 'title': 'TEST ONLY Year 11 Mocks', 'description': 'Students only', 'location': '', 'start': '2027-01-18', 'end': '2027-01-22', 'startDay': '2027-01-18', 'endDay': '2027-01-22', 'allDay': True, 'semester': 's2', 'status': 'confirmed'},
    {'id': 'test-discussions', 'uid': 'testdiscuss@google.com', 'title': 'TEST ONLY Development Discussions', 'description': 'No school for students. Parents attend scheduled meetings.', 'location': '', 'start': '2026-12-23', 'end': '2026-12-25', 'startDay': '2026-12-23', 'endDay': '2026-12-25', 'allDay': True, 'semester': 's1', 'status': 'confirmed'}
]
payload = {'schema': 1, 'events': fixtures, 'lastSynced': datetime.now(timezone.utc).isoformat()}
with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(viewport={'width': 1440, 'height': 1000}, timezone_id='America/New_York')
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.clock.set_fixed_time(datetime(2026, 9, 30, 13, 0, tzinfo=timezone.utc))
    page.route('https://calendar.google.com/calendar/embed*', lambda route: route.fulfill(status=200, content_type='text/html', body='<p>Live calendar frame (test stub)</p>'))
    page.route(RAW + '*', lambda route: route.fulfill(status=200, content_type='application/json', body=json.dumps(payload)))
    page.goto(PAGE, wait_until='networkidle')
    expect(page.locator('#events .card')).to_have_count(4)
    expect(page.locator('#upcoming .card')).to_have_count(3)
    assert page.locator('#school-logo').evaluate('(img) => img.complete && img.naturalWidth === 603')
    expect(page.locator('#events')).to_contain_text('9:00 AM')
    expect(page.locator('#events')).to_contain_text('15 Oct 2026 – 25 Oct 2026')
    page.locator('#search').fill('coffee')
    expect(page.locator('#events .card')).to_have_count(1)
    page.locator('#events button').click()
    expect(page.locator('#event-dialog')).to_be_visible()
    expect(page.locator('#event-body')).to_contain_text('Primary Parents')
    page.keyboard.press('Escape')
    expect(page.locator('#event-dialog')).not_to_be_visible()
    page.locator('#reset').click()
    page.locator('[data-filter="parents"]').click()
    expect(page.locator('#events .card')).to_have_count(2)
    page.locator('[data-filter="holidays"]').click()
    expect(page.locator('#events .card')).to_have_count(1)
    expect(page.locator('#events')).not_to_contain_text('Development Discussions')
    page.locator('#reset').click()
    page.locator('[data-sem="s2"]').click()
    expect(page.locator('#events .card')).to_have_count(1)
    page.locator('#search').fill('Y11')
    expect(page.locator('#events .card')).to_have_count(1)
    page.locator('#search').fill('no-such-event')
    expect(page.locator('#events')).to_contain_text('No events match')
    page.locator('#reset').click()
    page.locator('#month').select_option('2026-10')
    expect(page.locator('#events .card')).to_have_count(2)
    page.locator('#reset').click()
    assert page.locator('#full-calendar').bounding_box()['y'] > page.locator('#events').bounding_box()['y']
    assert page.locator('#download').get_attribute('href').endswith('/public/basic.ics')
    assert page.locator('#apple-subscribe').get_attribute('href').startswith('webcal:')
    assert page.locator('#subscribe').get_attribute('href').startswith('https://calendar.google.com/calendar/u/0?cid=')
    Path('test-results').mkdir(exist_ok=True)
    page.screenshot(path='test-results/desktop-test-fixtures.png', full_page=True)
    page.set_viewport_size({'width': 390, 'height': 844})
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'), 'Mobile layout overflows'
    assert page.locator('#school-logo').evaluate('(img) => img.naturalWidth === 603')
    page.screenshot(path='test-results/mobile-test-fixtures.png', full_page=True)
    page.unroute(RAW + '*')
    actual = json.loads(Path('calendar-data.json').read_text(encoding='utf-8'))
    page.route(RAW + '*', lambda route: route.fulfill(status=200, content_type='application/json', body=json.dumps(actual)))
    page.reload(wait_until='networkidle')
    if actual.get('restrictedCount'):
        expect(page.locator('#feed-notice')).to_contain_text('hiding event details')
        assert not page.locator('#events h3').filter(has_text='Busy').count()
    page.set_viewport_size({'width': 1440, 'height': 1000})
    page.screenshot(path='test-results/current-public-data.png', full_page=True)
    assert not errors, errors
    # Validate that raw GitHub allows the browser data request in production.
    page.unroute(RAW + '*')
    result = page.evaluate('''async url => {
      const response = await fetch(url, {credentials: 'omit', cache: 'no-store'});
      const body = await response.json();
      return {status: response.status, valid: Array.isArray(body.events)};
    }''', RAW)
    assert result == {'status': 200, 'valid': True}, result
    print('PASS: desktop and mobile logo, upcoming cards, text search, category filters, semester filters, month filter, event dialog, download links, restricted-feed state, raw GitHub browser access, and zero JavaScript errors.')
    browser.close()
server.shutdown()

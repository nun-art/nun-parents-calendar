"""Real browser checks; synthetic Google events are intercepted only in memory."""
import hashlib
import json
import threading
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from icalendar import Calendar
from playwright.sync_api import sync_playwright, expect

ROOT = Path.cwd()
assert hashlib.sha256((ROOT / 'nun-logo.jpg').read_bytes()).hexdigest() == 'fcb558a08bf4d29cf3d16fa62975a4fa342392514aa1f68f1192a3d4265bf795', 'Logo must match the supplied school upload'
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
Path('test-results').mkdir(exist_ok=True)

def check_download(page, count):
    with page.expect_download() as info:
        page.locator('#download').click()
    download = info.value
    assert download.suggested_filename.endswith('.ics')
    data = Path(download.path()).read_bytes()
    assert b'\r\n' in data
    for line in data.split(b'\r\n'):
        assert len(line) <= 75, ('ICS folding', len(line))
    events = Calendar.from_ical(data).walk('VEVENT')
    assert len(events) == count, (len(events), count)
    assert len({str(e['UID']) for e in events}) == count
    assert all('DTSTAMP' in e and 'DTEND' in e for e in events)
    return events

try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={'width': 1440, 'height': 1000}, timezone_id='America/New_York', accept_downloads=True)
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
        assert page.locator('#apple-subscribe').get_attribute('href').startswith('webcal:')
        assert page.locator('#subscribe').get_attribute('href').startswith('https://calendar.google.com/calendar/u/0?cid=')
        check_download(page, 4)

        # Busy-only public data must not leave the website empty.
        page.unroute(RAW + '*')
        restricted = {'schema': 1, 'events': [{**fixtures[0], 'title': 'Busy', 'description': '', 'location': ''}], 'restrictedCount': 1}
        page.route(RAW + '*', lambda route: route.fulfill(status=200, content_type='application/json', body=json.dumps(restricted)))
        page.reload(wait_until='networkidle')
        expect(page.locator('#feed-notice')).to_contain_text('School-published schedule')
        expect(page.locator('#upcoming .card')).to_have_count(3)
        expect(page.locator('#upcoming')).to_contain_text('Goal Setting')
        expect(page.locator('#upcoming')).to_contain_text('Class Representatives Welcome')
        expect(page.locator('#upcoming')).to_contain_text('Ongoing')
        assert not page.locator('#events h3').filter(has_text='Busy').count()
        page.locator('#search').fill('coffee')
        expect(page.locator('#events .card')).to_have_count(1)
        expect(page.locator('#events')).to_contain_text('18 Nov 2026')
        expect(page.locator('#events')).to_contain_text('Time to be confirmed')
        page.locator('#events button').click()
        expect(page.locator('#event-body')).to_contain_text('Semester 1 document')
        with page.expect_download() as one:
            page.get_by_role('button', name='Download this event (.ics)').click()
        assert len(Calendar.from_ical(Path(one.value.path()).read_bytes()).walk('VEVENT')) == 1
        page.keyboard.press('Escape')
        page.locator('#reset').click()
        page.locator('#show-past').check()
        expect(page.locator('#result-count')).to_have_text('29 events found')
        while page.locator('#more').is_visible():
            page.locator('#more').click()
        expect(page.locator('#events .card')).to_have_count(29)
        downloads = check_download(page, 29)
        by_uid = {str(e['UID']): e for e in downloads}
        open_house = by_uid['nun-document-open-primary@nunacademy.com']
        assert open_house.decoded('DTSTART').hour == 13, '4 PM Riyadh = 13:00 UTC'
        assert open_house.decoded('DTEND').hour == 15
        holiday = by_uid['nun-document-national-holiday@nunacademy.com']
        assert holiday.decoded('DTEND').isoformat() == '2026-09-25', 'Multi-day all-day end is exclusive'
        goal = by_uid['nun-document-goal-setting@nunacademy.com']
        assert goal.decoded('DTEND').isoformat() == '2026-10-09'
        assert str(by_uid['nun-document-girls-trip@nunacademy.com']['STATUS']) == 'TENTATIVE'
        page.locator('#reset').click()
        page.locator('#search').fill('Year 8')
        assert page.locator('#events .card').count() > 0, 'Year-group search finds stated ranges'
        page.locator('#reset').click()
        page.locator('[data-filter="parents"]').click()
        expect(page.locator('#events')).to_contain_text('Development Discussions')
        page.locator('[data-filter="holidays"]').click()
        expect(page.locator('#events .card')).to_have_count(1)
        expect(page.locator('#events')).not_to_contain_text('Development Discussions')
        page.locator('#reset').click()
        page.locator('[data-sem="s2"]').click()
        expect(page.locator('#events')).to_contain_text('Semester 2 event details are not available')
        page.locator('#reset').click()
        page.screenshot(path='test-results/desktop-document-cards.png', full_page=True)
        page.set_viewport_size({'width': 390, 'height': 844})
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'), 'Mobile layout overflows'
        assert page.locator('#school-logo').evaluate('(img) => img.naturalWidth === 603')
        check_download(page, 29)
        page.screenshot(path='test-results/mobile-document-cards.png', full_page=True)

        # No network access to the data feeds: cards and downloads still work.
        page.unroute(RAW + '*')
        page.route(RAW + '*', lambda route: route.abort())
        page.route('**/calendar-data.json*', lambda route: route.abort())
        page.reload(wait_until='networkidle')
        expect(page.locator('#upcoming .card')).to_have_count(3)
        page.locator('#search').fill('sports')
        expect(page.locator('#events .card')).to_have_count(1)
        expect(page.locator('#feed-notice')).to_contain_text('not live updates')
        assert not errors, errors
        print('PASS: exact school logo; all 29 document events; upcoming/ongoing cards; search including year ranges; audience, semester and month filters; event details; desktop/mobile layout; full and individual ICS downloads; timed and multi-day dates; restricted-feed and network-failure fallback; no JavaScript errors.')
        browser.close()
finally:
    server.shutdown()

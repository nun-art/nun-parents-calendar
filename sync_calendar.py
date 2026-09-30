"""Refresh only the PUBLIC Nün parents calendar. No account credentials used."""
import base64
import hashlib
import html
import json
import re
import time
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from icalendar import Calendar
import recurring_ical_events

CALENDAR_ID = 'c_de33ef4171ba5b6f2b53f141f01f626b06bc435d997772736afcef09507880e6@group.calendar.google.com'
FEED = 'https://calendar.google.com/calendar/ical/' + quote(CALENDAR_ID, safe='') + '/public/basic.ics'
TZ = ZoneInfo('Asia/Riyadh')
OUTPUT = Path('calendar-data.json')

# Save the exact uploaded logo as an ordinary image, not nested image markup.
if not Path('nun-logo.jpg').exists():
    for path in (Path('nun-logo.svg'), Path('index.html')):
        if not path.exists():
            continue
        match = re.search(r'data:image/jpeg;base64,([A-Za-z0-9+/=]+)', path.read_text(encoding='utf-8'))
        if match:
            image = base64.b64decode(match.group(1), validate=True)
            if not image.startswith(b'\xff\xd8'):
                raise ValueError('The school logo is not a JPEG.')
            Path('nun-logo.jpg').write_bytes(image)
            print('Original school logo restored:', len(image), 'bytes; SHA256:', hashlib.sha256(image).hexdigest())
            break

class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip += 1
        if not self.skip and tag in ('br', 'p', 'div', 'li'):
            self.parts.append('\n')
        if not self.skip and tag == 'a':
            href = dict(attrs).get('href', '')
            if href.startswith(('https://', 'http://')):
                self.parts.append(' ' + href + ' ')
    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.skip:
            self.skip -= 1
        if not self.skip and tag in ('p', 'div', 'li'):
            self.parts.append('\n')
    def handle_data(self, text):
        if not self.skip:
            self.parts.append(text)

def plain(value):
    text = str(value or '')
    if re.search(r'</?(?:p|div|br|span|a|b|strong|ul|li|script|style)\b', text, re.I):
        parser = PlainText()
        parser.feed(text)
        text = ''.join(parser.parts)
    return re.sub(r'\n{3,}', '\n\n', html.unescape(text).replace('**', '')).strip()

def zoned(value):
    if isinstance(value, datetime):
        return (value if value.tzinfo else value.replace(tzinfo=TZ)).astimezone(TZ)
    return datetime.combine(value, datetime.min.time(), TZ)

def main():
    cal = None
    for attempt in range(3):
        try:
            request = Request(FEED, headers={'User-Agent': 'NunParentsCalendar/2.0', 'Origin': 'https://nun-art.github.io'})
            with urlopen(request, timeout=40) as response:
                body = response.read(5000001)
                print('Public Google feed HTTP:', response.status, 'Access-Control-Allow-Origin:', response.headers.get('Access-Control-Allow-Origin', 'not supplied'))
            if len(body) > 5000000 or b'BEGIN:VCALENDAR' not in body:
                raise ValueError('No valid public iCalendar feed')
            cal = Calendar.from_ical(body)
            break
        except HTTPError as error:
            if error.code in (401, 403, 404):
                # Do not keep exposing older event details after public access is revoked.
                payload = {'schema': 1, 'events': [], 'source': FEED, 'lastSynced': None, 'lastAttempt': datetime.now(timezone.utc).isoformat(), 'syncError': 'Calendar is not publicly available', 'refreshMinutes': 30}
                OUTPUT.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
                print('Public calendar unavailable; details withheld.')
                return
            if attempt == 2:
                raise
            time.sleep(3 * (attempt + 1))
        except Exception:
            if attempt == 2:
                raise
            time.sleep(3 * (attempt + 1))
    items = []
    for event in recurring_ical_events.of(cal).between((2026, 8, 1), (2027, 8, 1)):
        if str(event.get('STATUS', '')).upper() == 'CANCELLED' or str(event.get('CLASS', '')).upper() in ('PRIVATE', 'CONFIDENTIAL'):
            continue
        start = event.decoded('DTSTART')
        all_day = not isinstance(start, datetime)
        end = event.decoded('DTEND', start + (timedelta(days=1) if all_day else timedelta(0)))
        uid = str(event.get('UID', ''))
        record = {
            'id': hashlib.sha256((uid + '|' + start.isoformat()).encode()).hexdigest()[:20],
            'uid': uid,
            'title': plain(event.get('SUMMARY', 'School event')),
            'description': plain(event.get('DESCRIPTION', '')),
            'location': plain(event.get('LOCATION', '')),
            'start': start.isoformat() if all_day else zoned(start).isoformat(),
            'end': end.isoformat() if all_day else zoned(end).isoformat(),
            'allDay': all_day,
            'status': str(event.get('STATUS', 'CONFIRMED')).lower(),
            'startDay': zoned(start).date().isoformat(),
            'endDay': zoned(end).date().isoformat(),
            'semester': 's2' if zoned(start).date() >= date(2027, 1, 18) else 's1'
        }
        for field in ('LAST-MODIFIED', 'DTSTAMP'):
            if field in event:
                record['updated'] = zoned(event.decoded(field)).isoformat()
                break
        items.append(record)
    items.sort(key=lambda item: (item['startDay'], item['start'], item['title']))
    restricted = sum(1 for item in items if item['title'].strip().lower() in ('busy', '(busy)', 'private', 'occupied', 'unavailable') and not item['description'])
    payload = {
        'schema': 1,
        'calendarName': str(cal.get('X-WR-CALNAME', 'Nün Parents Events Calendar')),
        'source': FEED,
        'timeZone': 'Asia/Riyadh',
        'lastSynced': datetime.now(timezone.utc).isoformat(),
        'refreshMinutes': 30,
        'restrictedCount': restricted,
        'events': items
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Public records:', len(items), '| Details hidden:', restricted)

if __name__ == '__main__':
    main()

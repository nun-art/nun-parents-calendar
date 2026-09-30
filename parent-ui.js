'use strict';

// Public Google data is refreshed by the repository's scheduled workflow.
// The school-supplied document is a separately labelled fallback, not live data.
const CALENDAR_ID = 'c_de33ef4171ba5b6f2b53f141f01f626b06bc435d997772736afcef09507880e6@group.calendar.google.com';
const CALENDAR_LINK = 'https://calendar.google.com/calendar/u/0?cid=' + btoa(CALENDAR_ID);
const FEED = 'https://calendar.google.com/calendar/ical/' + encodeURIComponent(CALENDAR_ID) + '/public/basic.ics';
const SNAPSHOT = 'https://raw.githubusercontent.com/nun-art/nun-parents-calendar/main/calendar-data.json';
const TZ = 'Asia/Riyadh';
const $ = id => document.getElementById(id);
const state = {events: [], semester: 'all', category: 'all', query: '', month: 'all', past: false, limit: 12, restricted: 0, source: 'document', failed: false};
const normalize = text => String(text || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/\byear\s*(\d+)/g, 'y$1').replace(/[^a-z0-9\u0600-\u06ff]+/g, ' ').trim();
const textNode = (tag, text, cls) => { const node = document.createElement(tag); if (cls) node.className = cls; node.textContent = text; return node; };
const parseDate = value => new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? value + 'T00:00:00+03:00' : value);
const dayOf = date => new Intl.DateTimeFormat('en-CA', {timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit'}).format(date);
const formatDate = value => parseDate(value).toLocaleDateString('en-GB', {day: 'numeric', month: 'short', year: 'numeric', timeZone: TZ});
const formatTime = value => parseDate(value).toLocaleTimeString('en-US', {hour: 'numeric', minute: '2-digit', timeZone: TZ});
const categoryLabel = key => ({parents: 'Parents', students: 'Students', holidays: 'No school', school: 'School activity'})[key] || 'School activity';
function nextDay(day) { const date = new Date(day + 'T12:00:00Z'); date.setUTCDate(date.getUTCDate() + 1); return date.toISOString().slice(0, 10); }
function lastDay(e) { return dayOf(new Date(Math.max(parseDate(e.start).getTime(), parseDate(e.end).getTime() - 1))); }
function ongoing(e) { const now = Date.now(); return parseDate(e.start).getTime() <= now && parseDate(e.end).getTime() > now; }
function upcoming(e) { const now = Date.now(); return parseDate(e.end).getTime() > now || parseDate(e.start).getTime() >= now; }
function dateLabel(e) { return e.startDay === lastDay(e) ? formatDate(e.start) : formatDate(e.start) + ' – ' + formatDate(lastDay(e)); }
function timeLabel(e) {
  if (e.timeLabel) return e.timeLabel;
  if (!e.allDay) return formatTime(e.start) + ' – ' + formatTime(e.end);
  if (e.categories.includes('holidays')) return 'No school · all day';
  if (/goal setting|development discussions/i.test(e.title)) return 'Individual scheduled meetings';
  return 'Time to be confirmed';
}
function categories(e) {
  const title = normalize(e.title);
  const body = normalize((e.description || '').replace(/dear\s+n[uü]n\s+parents[,:]?/ig, ''));
  const result = new Set();
  if (/\bholidays?\b|\bbreak\b|school closed/.test(title)) result.add('holidays');
  if (/parent|open house|coffee morning|forum|goal setting|development discussion|options evening|class representative|class reps/.test(title) || /parents are .{0,15}invited|parents attend|audience.{0,25}parents|students and parents/.test(body)) result.add('parents');
  if (!result.has('holidays') && /student|first day|sports|athletics|trip|exam|mock|book week|science fair|celebration|assembly|competition|talent|promotion|graduation/.test(title + ' ' + body)) result.add('students');
  if (!result.size) result.add('school');
  return [...result];
}
function prepare(e) {
  const item = {...e, uid: e.uid || e.id + '@nunacademy.com', location: e.location || '', description: e.description || '', startDay: e.startDay || dayOf(parseDate(e.start)), endDay: e.endDay || dayOf(parseDate(e.end))};
  item.categories = e.categories || categories(item);
  item.audience = e.audience || (item.description.match(/Audience\s*:\s*([^\n]+)/i) || [])[1] || '';
  let search = [item.title, item.description, item.location, item.audience, ...item.categories].join(' ');
  // Searching Y8 should also find an event explicitly labelled Y6–Y13.
  for (const match of search.matchAll(/(?:Y|Year\s*)(\d{1,2})\s*[-–—]\s*(?:Y|Year\s*)?(\d{1,2})/gi)) {
    const low = Number(match[1]), high = Number(match[2]);
    if (low >= 1 && high <= 13 && high >= low) for (let n = low; n <= high; n++) search += ' Y' + n;
  }
  item.searchText = normalize(search);
  return item;
}
const documentEvents = ((window.NUN_SEMESTER_ONE_DOCUMENT || {}).events || []).map(e => prepare({
  ...e, id: 'document-' + e.id, uid: 'nun-document-' + e.id + '@nunacademy.com',
  start: e.startTime ? e.date + 'T' + e.startTime + ':00+03:00' : e.date,
  end: e.endTime ? e.date + 'T' + e.endTime + ':00+03:00' : nextDay(e.lastDate || e.date),
  allDay: !e.startTime, semester: 's1', status: e.status || 'confirmed',
  description: e.notes || '', sourceKind: 'document'
}));

function card(e) {
  const article = textNode('article', '', 'card');
  const top = textNode('div', '', 'card-top');
  const tile = textNode('div', '', 'date-tile');
  const start = parseDate(e.start);
  tile.append(textNode('span', start.toLocaleDateString('en-GB', {month: 'short', timeZone: TZ})), textNode('b', start.toLocaleDateString('en-GB', {day: 'numeric', timeZone: TZ})));
  const tags = textNode('div', '', 'badges');
  for (const category of e.categories) tags.append(textNode('span', categoryLabel(category), 'badge ' + category));
  if (e.status === 'tentative' || /tentative/i.test(e.description)) tags.append(textNode('span', 'Tentative', 'badge notice-badge'));
  if (ongoing(e)) tags.append(textNode('span', 'Ongoing', 'badge notice-badge'));
  if (/early dismissal/i.test(e.description + ' ' + (e.timeLabel || ''))) tags.append(textNode('span', 'Early dismissal', 'badge notice-badge'));
  top.append(tile, tags);
  const body = textNode('div', '', 'card-body');
  body.append(textNode('h3', e.title), textNode('p', dateLabel(e), 'info'), textNode('p', timeLabel(e), 'info'));
  if (e.audience) body.append(textNode('p', e.audience, 'info'));
  if (e.location) body.append(textNode('p', /^https?:\/\//.test(e.location) ? 'Online · joining link in details' : e.location, 'info'));
  if (/book character/i.test(e.description)) body.append(textNode('p', 'Book character costumes · see parade details', 'brief'));
  const foot = textNode('div', '', 'card-foot');
  const button = textNode('button', 'View details →'); button.type = 'button'; button.setAttribute('aria-label', 'View details: ' + e.title); button.addEventListener('click', () => openEvent(e));
  foot.append(button, textNode('span', e.semester === 's2' ? 'Semester 2' : 'Semester 1'));
  article.append(top, body, foot);
  return article;
}
function empty(target, message) { target.replaceChildren(textNode('div', message, 'empty')); }
function filtered() {
  const words = normalize(state.query).split(' ').filter(Boolean);
  return state.events.filter(e => (state.semester === 'all' || e.semester === state.semester) && (state.category === 'all' || e.categories.includes(state.category)) && (state.past || upcoming(e)) && (state.month === 'all' || e.startDay.slice(0, 7) <= state.month && lastDay(e).slice(0, 7) >= state.month) && words.every(word => e.searchText.includes(word)));
}
function render() {
  const found = filtered();
  $('events').replaceChildren(...found.slice(0, state.limit).map(card));
  if (!found.length) empty($('events'), state.semester === 's2' && !state.events.some(e => e.semester === 's2') ? 'Semester 2 event details are not available here yet. Please check the live calendar below.' : 'No events match these filters. Try another category, or include past events.');
  $('result-count').textContent = found.length + (found.length === 1 ? ' event' : ' events') + (state.past ? ' found' : ' upcoming or ongoing');
  $('more').hidden = found.length <= state.limit;
  $('more').textContent = 'Show more (' + Math.max(0, found.length - state.limit) + ' remaining)';
  const next = state.events.filter(upcoming).slice(0, 3);
  $('upcoming').replaceChildren(...next.map(card));
  if (!next.length) empty($('upcoming'), 'No upcoming events are listed in the available school schedule.');
}
function rebuildMonths() {
  const values = new Set();
  for (const e of state.events) {
    let [year, month] = e.startDay.slice(0, 7).split('-').map(Number);
    const end = lastDay(e).slice(0, 7);
    for (let guard = 0; guard < 36; guard++) {
      const value = year + '-' + String(month).padStart(2, '0');
      if (value > end) break;
      values.add(value); month++; if (month === 13) { month = 1; year++; }
    }
  }
  $('month').replaceChildren(new Option('Any month', 'all'));
  for (const month of [...values].sort()) $('month').add(new Option(parseDate(month + '-01').toLocaleDateString('en-GB', {month: 'long', year: 'numeric', timeZone: TZ}), month));
  if (values.has(state.month)) $('month').value = state.month; else state.month = 'all';
}

// RFC 5545 TEXT escaping and UTF-8-aware line folding for calendar downloads.
function escapeICS(value) { return String(value || '').replace(/\\/g, '\\\\').replace(/\r?\n/g, '\\n').replace(/;/g, '\\;').replace(/,/g, '\\,'); }
function foldICS(line) {
  const encoder = new TextEncoder(); let result = '', current = '', bytes = 0;
  for (const char of line) {
    const length = encoder.encode(char).length;
    if (bytes + length > 75) { result += current + '\r\n'; current = ' '; bytes = 1; }
    current += char; bytes += length;
  }
  return result + current;
}
function utcStamp(value) { return parseDate(value).toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z'); }
function icsText(items) {
  const stamp = utcStamp(new Date().toISOString());
  const lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Nun Academy//Parents Calendar//EN', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH', 'X-WR-CALNAME:Nün Parents Events Calendar', 'X-WR-TIMEZONE:Asia/Riyadh'];
  for (const e of items) {
    const info = [e.audience ? 'Audience: ' + e.audience : '', e.allDay ? 'Timing: ' + timeLabel(e) : '', e.description, e.sourceKind === 'document' ? 'Source: Nün Academy Semester 1 2026/2027 document, supplied 30 September 2026.' : 'Source: public Nün Parents Events Google Calendar snapshot.', 'This download is a one-time copy. Check official school communications for updates.'].filter(Boolean).join('\n\n');
    lines.push('BEGIN:VEVENT', 'UID:' + escapeICS(e.uid), 'DTSTAMP:' + stamp,
      e.allDay ? 'DTSTART;VALUE=DATE:' + e.start.slice(0, 10).replace(/-/g, '') : 'DTSTART:' + utcStamp(e.start),
      e.allDay ? 'DTEND;VALUE=DATE:' + e.end.slice(0, 10).replace(/-/g, '') : 'DTEND:' + utcStamp(e.end),
      'SUMMARY:' + escapeICS(e.title), 'DESCRIPTION:' + escapeICS(info));
    if (e.location) lines.push('LOCATION:' + escapeICS(e.location));
    lines.push('STATUS:' + (e.status === 'tentative' ? 'TENTATIVE' : 'CONFIRMED'), 'TRANSP:TRANSPARENT', 'END:VEVENT');
  }
  lines.push('END:VCALENDAR');
  return lines.map(foldICS).join('\r\n') + '\r\n';
}
let downloadURL = '';
function updateDownload() {
  if (downloadURL) URL.revokeObjectURL(downloadURL);
  downloadURL = URL.createObjectURL(new Blob([icsText(state.events)], {type: 'text/calendar;charset=utf-8'}));
  $('download').href = downloadURL;
  $('download').download = state.source === 'document' ? 'Nun_Parents_Semester_1_2026_2027.ics' : 'Nun_Parents_Events_2026_2027.ics';
  $('download').textContent = state.source === 'document' ? 'Download Semester 1 (.ics)' : 'Download events (.ics)';
}
function eventDownload(e) {
  const url = URL.createObjectURL(new Blob([icsText([e])], {type: 'text/calendar;charset=utf-8'}));
  const a = document.createElement('a'); a.href = url; a.download = 'Nun_' + e.id + '.ics'; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 60000);
}
function openEvent(e) {
  $('event-title').textContent = e.title;
  const body = $('event-body'); body.replaceChildren(textNode('p', dateLabel(e)), textNode('p', timeLabel(e) + (e.allDay ? '' : ' · Riyadh time')));
  if (e.audience) body.append(textNode('p', 'For: ' + e.audience));
  body.append(textNode('p', e.location ? 'Location: ' + e.location : 'Location: not specified in this source.'));
  body.append(textNode('div', e.description || 'Further event information has not been provided in this source.', 'description'));
  body.append(textNode('p', e.sourceKind === 'document' ? 'Source: the school’s Semester 1 document. This card is not a live Google Calendar entry.' : 'Source: public Google Calendar. Dates and details shown are from the latest successful refresh.', 'tiny source-note'));
  const actions = textNode('div', '', 'buttons');
  function link(title, url) { const a = textNode('a', title, 'button outline'); a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer'; actions.append(a); }
  if (e.sourceKind !== 'document') {
    const eventId = e.uid.endsWith('@google.com') ? e.uid.slice(0, -11) : '';
    const eventLink = eventId && /^[a-zA-Z0-9_-]+$/.test(eventId) ? 'https://calendar.google.com/calendar/event?eid=' + encodeURIComponent(btoa(eventId + ' ' + CALENDAR_ID)) : CALENDAR_LINK;
    link('Open in Google Calendar', eventLink);
  } else {
    const params = new URLSearchParams({action: 'TEMPLATE', text: e.title, dates: e.allDay ? e.start.replace(/-/g, '') + '/' + e.end.replace(/-/g, '') : utcStamp(e.start) + '/' + utcStamp(e.end), details: e.description + '\n\nSource: school Semester 1 document. This is a separate one-time copy.', location: e.location, ctz: TZ});
    link('Add a copy to Google Calendar', 'https://calendar.google.com/calendar/render?' + params);
  }
  const save = textNode('button', 'Download this event (.ics)', 'button outline'); save.type = 'button'; save.addEventListener('click', () => eventDownload(e)); actions.append(save);
  const urls = [...new Set(((e.description || '') + ' ' + e.location).match(/https?:\/\/[^\s<>"']+/g) || [])];
  for (let url of urls.slice(0, 5)) {
    url = url.replace(/[),.;]+$/, '');
    try {
      const parsed = new URL(url);
      if (!['http:', 'https:'].includes(parsed.protocol)) continue;
      if (/(^|\.)(zoom\.us|meet\.google\.com|teams\.microsoft\.com)$/.test(parsed.hostname)) link('Join online meeting', url);
      else if (/(^|\.)(forms\.gle|forms\.google\.com)$/.test(parsed.hostname) || parsed.hostname === 'docs.google.com' && parsed.pathname.startsWith('/forms/')) link('Open school form', url);
    } catch (_) { /* Ignore malformed URLs. */ }
  }
  body.append(actions);
  $('event-dialog').showModal();
}

$('subscribe').href = CALENDAR_LINK;
$('open-calendar').href = CALENDAR_LINK;
$('apple-subscribe').href = FEED.replace('https:', 'webcal:');
$('calendar-frame').src = 'https://calendar.google.com/calendar/embed?' + new URLSearchParams({src: CALENDAR_ID, ctz: TZ, mode: 'AGENDA', showTitle: '0', showPrint: '0', showCalendars: '0', showTz: '0', bgcolor: '#ffffff'});
$('school-logo').addEventListener('error', () => { const logo = $('school-logo'); if (!logo.dataset.fallback) { logo.dataset.fallback = 'true'; logo.src = './nun-logo.svg'; } });
$('close-dialog').addEventListener('click', () => $('event-dialog').close());
$('event-dialog').addEventListener('click', event => { if (event.target === $('event-dialog')) { const r = $('event-dialog').getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) $('event-dialog').close(); } });
function selectGroup(selector, key, value) { document.querySelectorAll(selector).forEach(button => button.setAttribute('aria-pressed', String(button.dataset[key] === value))); }
document.querySelectorAll('[data-sem]').forEach(button => button.addEventListener('click', () => { state.semester = button.dataset.sem; state.limit = 12; selectGroup('[data-sem]', 'sem', state.semester); render(); }));
document.querySelectorAll('[data-filter]').forEach(button => button.addEventListener('click', () => { state.category = button.dataset.filter; state.limit = 12; selectGroup('[data-filter]', 'filter', state.category); render(); }));
$('search').addEventListener('input', event => { state.query = event.target.value; state.limit = 12; render(); });
$('month').addEventListener('change', event => { state.month = event.target.value; state.limit = 12; render(); });
$('show-past').addEventListener('change', event => { state.past = event.target.checked; state.limit = 12; render(); });
$('more').addEventListener('click', () => { state.limit += 12; render(); });
$('reset').addEventListener('click', () => { Object.assign(state, {semester: 'all', category: 'all', query: '', month: 'all', past: false, limit: 12}); $('search').value = ''; $('month').value = 'all'; $('show-past').checked = false; selectGroup('[data-sem]', 'sem', 'all'); selectGroup('[data-filter]', 'filter', 'all'); render(); });
$('copy-feed').addEventListener('click', async () => { try { await navigator.clipboard.writeText(FEED); $('copy-status').textContent = 'Subscription address copied. Paste it into your calendar’s subscribe-from-web option.'; } catch (_) { $('copy-status').textContent = 'Copy this subscription address: ' + FEED; } });

function applyEvents(items) { state.events = items.slice().sort((a, b) => parseDate(a.start) - parseDate(b.start)); rebuildMonths(); updateDownload(); render(); }
function fallbackNotice(message, managerHelp) {
  const notice = $('feed-notice'); notice.hidden = false; notice.replaceChildren(textNode('strong', 'Semester 1 · School-published schedule'), textNode('p', message));
  if (managerHelp) {
    const details = document.createElement('details'); details.append(textNode('summary', 'For the school calendar manager'));
    details.append(textNode('p', 'Google’s public feed is hiding event details. In Google Calendar → Settings → Nün Parents Events Calendar → Access permissions for events, choose “See all event details” next to “Make available to public”. This makes event details visible to anyone. Apply this only to the parents events calendar, not your personal calendar. Card refreshes are scheduled every 30 minutes and may be delayed.'));
    notice.append(details);
  }
}
async function requestData(url) {
  const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), 8000);
  try { const response = await fetch(url + '?v=' + Date.now(), {cache: 'no-store', signal: controller.signal, credentials: 'omit'}); if (!response.ok) throw new Error('Calendar unavailable'); const data = await response.json(); if (!Array.isArray(data.events)) throw new Error('Invalid calendar data'); return data; } finally { clearTimeout(timer); }
}
let refreshing = false;
async function refresh() {
  if (refreshing) return; refreshing = true; $('refresh').disabled = true;
  try {
    let data;
    try { data = await requestData(SNAPSHOT); } catch (_) { data = await requestData('./calendar-data.json'); }
    const valid = data.events.filter(e => e && typeof e.title === 'string' && e.start && e.end && !isNaN(parseDate(e.start)) && !isNaN(parseDate(e.end)) && e.status !== 'cancelled');
    const hidden = e => /^(busy|\(busy\)|private|occupied|unavailable)$/i.test(e.title.trim()) && !e.description;
    state.restricted = valid.filter(hidden).length;
    const named = valid.filter(e => !hidden(e)).map(e => prepare({...e, sourceKind: 'google'}));
    state.failed = Boolean(data.syncError);
    if (state.restricted || data.syncError) {
      // Do not reconcile conflicting Semester 1 dates from two different sources.
      // Keep the document complete while live data is restricted; only add readable S2.
      const s2 = named.filter(e => e.semester === 's2');
      state.source = s2.length ? 'mixed' : 'document';
      applyEvents([...documentEvents, ...s2]);
      fallbackNotice('These Semester 1 cards and downloads use the school document supplied on 30 September 2026. Live event details are not fully public yet. The Google Calendar remains below; please check official school updates for changes.', true);
      $('sync-status').textContent = 'School document · ' + documentEvents.length + ' Semester 1 events · Google details currently limited';
    } else {
      state.source = 'google'; applyEvents(named); $('feed-notice').hidden = true;
      const synced = data.lastSynced ? new Date(data.lastSynced) : null;
      $('sync-status').textContent = 'Google Calendar' + (synced && !isNaN(synced) ? ' · Last checked ' + synced.toLocaleString('en-GB', {day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: TZ}) + ' (Riyadh)' : '') + ' · Refresh scheduled every 30 minutes';
      if (synced && Date.now() - synced.getTime() > 7200000) $('sync-status').textContent += ' · Refresh delayed';
    }
  } catch (_) {
    state.failed = true; state.source = 'document'; applyEvents(documentEvents);
    fallbackNotice('The online update could not be checked. These cards and downloads use the school’s Semester 1 document, not live updates. Please check official communications for changes.', false);
    $('sync-status').textContent = 'School document · ' + documentEvents.length + ' Semester 1 events · Online refresh unavailable';
  } finally { refreshing = false; $('refresh').disabled = false; }
}
// Render useful, searchable cards immediately, even with no network response.
applyEvents(documentEvents);
$('sync-status').textContent = 'Semester 1 school schedule · checking public Google updates…';
$('refresh').addEventListener('click', refresh);
refresh();
setInterval(() => { if (!document.hidden) refresh(); }, 300000);

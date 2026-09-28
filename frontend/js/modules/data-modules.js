/**
 * JARVIS — Notes, Weather and News modules.
 * Notes use the existing CRUD endpoints. Weather and News use the additive
 * read-only routes in `ultron/web_modules.py`; when those are not deployed the
 * module states the truth rather than inventing data.
 */

import { el, escapeHtml, relativeTime } from '../lib/dom.js';
import { get, setWeatherLocation } from '../core/store.js';
import * as api from '../lib/api.js';
import * as log from '../core/activity-log.js';
import * as toast from '../core/toast.js';
import { setSubtitle, emptyBlock } from '../ui/drawer.js';
import { section, row, field, textarea, button, reportError } from './kit.js';

/* ── NOTES ────────────────────────────────────────────────────────── */
function notesView(body) {
  const composer = el('div', { class: 'note-composer' });
  const list = el('div', { class: 'note-list' });

  const titleField = field('Title');
  const bodyField = textarea('Write something worth keeping…');
  const tagsField = field('Tags, comma separated');
  titleField.setAttribute('aria-label', 'Note title');
  tagsField.setAttribute('aria-label', 'Note tags');

  const save = button('Save note', async () => {
    const title = titleField.value.trim();
    if (!title) {
      toast.warning('TITLE REQUIRED', 'A note needs a title');
      titleField.focus();
      return;
    }
    const tags = tagsField.value.split(',').map((t) => t.trim()).filter(Boolean);
    try {
      await api.createNote({ title, content: bodyField.value, tags });
      titleField.value = '';
      bodyField.value = '';
      tagsField.value = '';
      log.push('success', `Note created: ${title}`);
      toast.success('NOTE SAVED', title);
      await refresh();
    } catch (err) {
      reportError('Note creation', err);
    }
  }, 'primary');

  composer.append(titleField, bodyField, tagsField, el('div', { class: 'composer-actions' }, [save]));

  async function refresh() {
    try {
      const data = await api.listNotes();
      const notes = data?.notes || [];
      list.replaceChildren();
      setSubtitle(`${notes.length} note${notes.length === 1 ? '' : 's'}`);
      if (!notes.length) {
        list.append(emptyBlock('NO NOTES', 'Create the first note above.'));
        return;
      }
      for (const note of notes) list.append(noteCard(note, refresh));
    } catch (err) {
      list.replaceChildren(
        el('div', { class: 'state-block is-error' }, [
          el('span', { class: 'h', text: 'NOTES UNAVAILABLE' }),
          el('span', { class: 'd', text: err.message }),
        ]),
      );
    }
  }

  body.append(section('NEW NOTE'), composer, section('STORAGE'), list);
  list.replaceChildren(el('div', { class: 'loading-line', text: 'LOADING NOTES' }));
  refresh();
  return () => {};
}

function noteCard(note, refresh) {
  const tags = Array.isArray(note.tags) ? note.tags : [];
  const card = el('article', { class: 'note-card' }, [
    el('header', { class: 'note-head' }, [
      el('h3', { class: 'note-title', text: note.title || 'Untitled' }),
      el('time', { class: 'note-time', text: relativeTime(note.updated_at || note.created_at) }),
    ]),
  ]);
  if (note.content) card.append(el('p', { class: 'note-body', text: note.content }));
  if (tags.length) {
    card.append(
      el('div', { class: 'note-tags' }, tags.map((t) => el('span', { class: 'tag', text: t }))),
    );
  }
  card.append(
    el('div', { class: 'note-actions' }, [
      button('Edit', () => startEdit(card, note, refresh)),
      button('Delete', () => remove(note, refresh), 'danger'),
    ]),
  );
  return card;
}

function startEdit(card, note, refresh) {
  if (card.querySelector('.note-edit')) return;
  const editor = el('div', { class: 'note-edit' });
  const titleField = field('Title', note.title || '');
  const bodyField = textarea('', note.content || '');
  editor.append(titleField, bodyField, el('div', { class: 'composer-actions' }, [
    button('Cancel', () => editor.remove()),
    button('Save', async () => {
      try {
        await api.updateNote(note.id, {
          title: titleField.value.trim() || note.title,
          content: bodyField.value,
        });
        log.push('success', `Note updated: ${titleField.value.trim()}`);
        await refresh();
      } catch (err) {
        reportError('Note update', err);
      }
    }, 'primary'),
  ]));
  card.append(editor);
  titleField.focus();
}

async function remove(note, refresh) {
  if (!window.confirm(`Delete note "${note.title}"? This cannot be undone.`)) return;
  try {
    await api.deleteNote(note.id);
    log.push('info', `Note deleted: ${note.title}`);
    toast.info('NOTE DELETED', note.title);
    await refresh();
  } catch (err) {
    reportError('Note deletion', err);
  }
}

export const notes = {
  id: 'notes',
  title: 'Notes',
  label: 'NOTES',
  icon: 'i-notes',
  subtitle: 'Persistent note storage',
  available: true,
  render: notesView,
};

/* ── WEATHER ──────────────────────────────────────────────────────── */
function weatherView(body) {
  const host = el('div', { class: 'mod-body' });
  const bar = el('div', { class: 'location-bar' });
  const location = field('City name', get().weatherLocation);
  location.setAttribute('aria-label', 'City for weather lookup');

  const load = async (city, coords = null) => {
    host.replaceChildren(el('div', { class: 'loading-line', text: 'FETCHING FORECAST' }));
    setSubtitle(city ? `fetching ${city}…` : 'no location set');
    try {
      const data = await api.weather(city || undefined, { lat: coords?.lat, lon: coords?.lon });
      render(data, city);
    } catch (err) {
      const reason =
        err.status === 404 ? err.message
        : 'The weather upstream could not be reached. Check network access.';
      host.replaceChildren(
        el('div', { class: 'state-block is-error' }, [
          el('span', { class: 'h', text: 'WEATHER UNAVAILABLE' }),
          el('span', { class: 'd', text: reason }),
        ]),
      );
      setSubtitle('unavailable');
    }
  };

  const submit = button('Fetch', async () => {
    const city = location.value.trim();
    if (!city) {
      toast.warning('LOCATION REQUIRED', 'Enter a city name to fetch a forecast');
      location.focus();
      return;
    }
    setWeatherLocation(city);
    await load(city);
  }, 'primary');

  const useMine = button('Use my location', () => {
    if (!navigator.geolocation) {
      toast.warning('UNSUPPORTED', 'This browser exposes no geolocation API');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        // Coordinates bypass geocoding; the returned label tells us the place.
        const coords = { lat: pos.coords.latitude, lon: pos.coords.longitude };
        const label = `${coords.lat.toFixed(3)}, ${coords.lon.toFixed(3)}`;
        location.value = label;
        setWeatherLocation(label, coords);
        await load(label, coords);
      },
      (err) => toast.warning('LOCATION DENIED', err.message),
      { timeout: 8000 },
    );
  }, 'soft');

  bar.append(location, submit, useMine);
  body.append(section('LOCATION'), bar, section('FORECAST'), host);

  const saved = get().weatherLocation;
  const coords = get().weatherCoords;
  if (saved) load(saved, coords);
  else {
    host.replaceChildren(
      emptyBlock('NO LOCATION SET', 'Enter a city above or use your location to fetch real conditions from Open-Meteo.'),
    );
    setSubtitle('no location set');
  }

  function render(data, city) {
    const current = data.current || {};
    const daily = Array.isArray(data.daily) ? data.daily : [];
    const place = data.location || city || 'UNKNOWN';
    setSubtitle(`${place} · ${current.description || 'unknown'}`);
    host.replaceChildren(
      el('div', { class: 'weather-now' }, [
        el('div', { class: 'weather-temp', text: current.temperature_c != null ? `${Math.round(current.temperature_c)}°` : '—' }),
        el('div', { class: 'weather-meta' }, [
          el('div', { class: 'weather-place', text: place }),
          el('div', { class: 'weather-desc', text: current.description || 'UNKNOWN' }),
          el('div', { class: 'weather-stats', text: `Feels ${current.apparent_c ?? '—'}°C · Wind ${current.wind_kph ?? '—'} km/h · Humidity ${current.humidity ?? '—'}%` }),
        ]),
      ]),
      section('DAILY FORECAST'),
      ...(daily.length
        ? daily.slice(0, 6).map((d) =>
            el('div', { class: 'kv' }, [
              el('span', { class: 'k', text: d.date || '—' }),
              el('span', { class: 'v', text: `${d.min_c ?? '—'}° / ${d.max_c ?? '—'}° · ${d.description || '—'}` }),
              el('span', { class: 'kv-extra', text: d.precipitation_pct != null ? `${d.precipitation_pct}% rain` : '' }),
            ]),
          )
        : [el('div', { class: 'state-block', text: 'NO DAILY DATA' })]),
    );
  }

  return () => {};
}

export const weather = {
  id: 'weather',
  title: 'Weather',
  label: 'WEATHER',
  icon: 'i-weather',
  subtitle: 'Live forecast',
  available: true,
  render: weatherView,
};

/* ── NEWS ─────────────────────────────────────────────────────────── */
function newsView(body) {
  const host = el('div', { class: 'mod-body' });
  body.append(section('HEADLINES', 'real feed'), host);
  host.append(el('div', { class: 'loading-line', text: 'FETCHING HEADLINES' }));
  load();

  async function load() {
    host.replaceChildren(el('div', { class: 'loading-line', text: 'FETCHING HEADLINES' }));
    try {
      const data = await api.news();
      const items = Array.isArray(data?.items) ? data.items : [];
      host.replaceChildren();
      if (!items.length) {
        host.append(emptyBlock('NO HEADLINES', 'The feed returned no stories.'));
        return;
      }
      for (const item of items) {
        const node = el('article', { class: 'news-card' });
        if (item.link) {
          const link = el('a', { class: 'news-title', href: item.link, target: '_blank', rel: 'noopener noreferrer' });
          link.textContent = item.title || 'Untitled';
          node.append(link);
        } else {
          node.append(el('span', { class: 'news-title', text: item.title || 'Untitled' }));
        }
        if (item.source) node.append(el('span', { class: 'news-source', text: item.source }));
        if (item.summary) node.append(el('p', { class: 'news-summary', text: item.summary }));
        if (item.published) node.append(el('time', { class: 'news-time', text: relativeTime(item.published) }));
        host.append(node);
      }
    } catch (err) {
      host.replaceChildren(
        el('div', { class: 'state-block is-error' }, [
          el('span', { class: 'h', text: 'NEWS UNAVAILABLE' }),
          el('span', { class: 'd', text: `${err.message}. The /api/news route is served by ultron/web_modules.py.` }),
        ]),
      );
    }
  }

  return () => {};
}

export const news = {
  id: 'news',
  title: 'News',
  label: 'NEWS',
  icon: 'i-news',
  subtitle: 'Current headlines',
  available: true,
  render: newsView,
};

export { escapeHtml, row };

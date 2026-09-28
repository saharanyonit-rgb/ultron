/**
 * JARVIS — Chat view.
 * Builds the conversation surface inside the module drawer and exposes the
 * renderer consumed by `features/chat.js`.
 */

import { $, el, escapeHtml } from '../lib/dom.js';
import { setCoreState } from './hud-core.js';
import { submit } from '../features/chat.js';
import { get } from '../core/store.js';

let scroll = null;
let composerInput = null;
let history = [];
let historyIndex = -1;
let typingNode = null;

/* ── Fenced code + inline formatting ──────────────────────────────── */
const KEYWORDS = {
  python: /\b(def|class|return|import|from|if|elif|else|for|while|in|not|and|or|try|except|finally|with|as|lambda|pass|None|True|False|self|yield|async|await)\b/g,
  javascript: /\b(const|let|var|function|return|if|else|for|while|async|await|new|class|extends|import|export|from|try|catch|finally|throw|typeof|null|undefined|this|break|continue|switch|case|default)\b/g,
  json: /\b(true|false|null)\b/g,
  sql: /\b(SELECT|FROM|WHERE|INSERT|UPDATE|DELETE|CREATE|TABLE|JOIN|GROUP|ORDER|AND|OR|NOT|NULL|VALUES|INTO)\b/g,
  shell: /\b(echo|cd|ls|dir|mkdir|rm|mv|cp|cat|sudo|git|npm|pip|python|node|powershell|if|then|else|fi)\b/g,
};
const ALIAS = { py: 'python', js: 'javascript', jsx: 'javascript', ts: 'typescript', sh: 'shell', bash: 'shell', ps1: 'shell' };

function highlight(code, lang) {
  const rule = ALIAS[(lang || '').toLowerCase()] || (lang || '').toLowerCase();
  let html = escapeHtml(code);
  const kw = KEYWORDS[rule];
  if (kw) html = html.replace(kw, '<span class="tk-k">$&</span>');
  html = html.replace(/(&quot;[^&]*?&quot;|&#39;[^&]*?&#39;)/g, '<span class="tk-s">$1</span>');
  html = html.replace(/\b(\d+(?:\.\d+)?)\b/g, '<span class="tk-n">$1</span>');
  return html;
}

function renderContent(text) {
  const safe = escapeHtml(String(text || ''));
  const parts = safe.split(/```(?:[a-zA-Z0-9_+-]*)\n?([\s\S]*?)```/g);
  const frag = document.createDocumentFragment();

  parts.forEach((part, i) => {
    if (i % 2 === 1) {
      const block = el('div', { class: 'code-block' });
      const raw = unescapeForCode(part);
      block.append(
        el('div', { class: 'code-head' }, [
          el('span', { class: 'code-lang', text: 'CODE' }),
          el('button', { type: 'button', class: 'btn-mini', text: 'Copy', onclick: (e) => {
            navigator.clipboard?.writeText(raw).then(
              () => { e.target.textContent = 'Copied'; setTimeout(() => { e.target.textContent = 'Copy'; }, 1500); },
              () => { e.target.textContent = 'Failed'; },
            );
          } }),
        ]),
      );
      const pre = el('pre', { class: 'code-pre' });
      pre.innerHTML = highlight(raw, '');
      block.append(pre);
      frag.append(block);
    } else {
      const span = el('span');
      span.innerHTML = part
        .replace(/`([^`]+)`/g, '<code class="inline">$1</code>')
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');
      frag.append(span);
    }
  });
  return frag;
}

function unescapeForCode(value) {
  const node = document.createElement('textarea');
  node.innerHTML = value;
  return node.value;
}

/* ── Message helpers ──────────────────────────────────────────────── */
function push(node) {
  if (!scroll) return;
  typingNode?.remove();
  typingNode = null;
  scroll.append(node);
  scroll.scrollTop = scroll.scrollHeight;
}

function bubble(kind, text) {
  const node = el('div', { class: `msg from-${kind}` });
  node.append(renderContent(text));
  return node;
}

function showTyping() {
  if (!scroll || typingNode) return;
  typingNode = el('div', { class: 'msg from-assistant' }, [
    el('span', { class: 'chat-hint', text: 'PROCESSING' }),
  ]);
  scroll.append(typingNode);
  scroll.scrollTop = scroll.scrollHeight;
}

/* ── Renderer consumed by features/chat.js ───────────────────────── */
export const renderer = {
  user(text) {
    showTyping();
    push(bubble('user', text));
  },
  assistant(text) {
    push(bubble('assistant', text));
  },
  error(text) {
    push(bubble('error', `ERROR — ${text}`));
  },
  system(text) {
    push(el('div', { class: 'msg from-system', text }));
  },
  plan(title, steps) {
    const wrap = el('div', { class: 'msg is-plan' }, [el('strong', { text: title })]);
    const list = el('div', { class: 'plan-list' });
    wrap.append(list);
    updatePlan(wrap, steps);
    return wrap;
  },
  updatePlan(node, steps) {
    if (!node) return;
    const list = node.querySelector('.plan-list');
    if (!list) return;
    list.replaceChildren();
    const symbols = { pending: '○', running: '▸', completed: '✓', failed: '✗' };
    for (const step of steps) {
      list.append(
        el('div', { class: `plan-step st-${step.status}` }, [
          el('span', { class: 'sym', text: symbols[step.status] || '○' }),
          el('span', { text: step.text }),
        ]),
      );
    }
  },
};

/* ── Composer ─────────────────────────────────────────────────────── */
function send() {
  const text = composerInput.value.trim();
  if (!text) return;
  composerInput.value = '';
  history.push(text);
  historyIndex = history.length;
  submit(text).catch((err) => {
    renderer.error(err.message);
    setCoreState(get().link === 'offline' ? 'offline' : 'idle');
  });
}

function buildComposer() {
  const wrap = el('div', { class: 'chat-compose' });
  const input = el('input', {
    class: 'input-field',
    type: 'text',
    id: 'chat-input',
    placeholder: 'Issue a command to JARVIS…',
    'aria-label': 'Command input',
    autocomplete: 'off',
  });
  const button = el('button', { type: 'submit', class: 'icon-btn', 'aria-label': 'Send command' });
  button.innerHTML = '<svg aria-hidden="true"><use href="#i-send"></use></svg>';

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (historyIndex > 0) {
        historyIndex -= 1;
        input.value = history[historyIndex];
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (historyIndex < history.length - 1) {
        historyIndex += 1;
        input.value = history[historyIndex];
      } else {
        historyIndex = history.length;
        input.value = '';
      }
    }
  });

  wrap.append(input, button);
  composerInput = input;
  return wrap;
}

/* ── Module entry ─────────────────────────────────────────────────── */
export function renderChatModule(body) {
  body.replaceChildren();
  const wrap = el('div', { class: 'chat-wrap' });
  scroll = el('div', { class: 'chat-scroll scrollable', id: 'chat-scroll' });
  wrap.append(scroll, buildComposer());
  body.append(wrap);

  renderer.system('CHANNEL OPEN — JARVIS core reachable for commands');
  if (get().link === 'offline') renderer.error('BACKEND OFFLINE — commands will fail until the core is running');

  setTimeout(() => composerInput?.focus(), 60);
  return () => {
    composerInput = null;
    scroll = null;
  };
}

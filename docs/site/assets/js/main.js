/* =========================================================
   LoadSpiker Documentation — main.js
   ========================================================= */

/* ── Theme Toggle ───────────────────────────────────────── */
(function () {
  const THEME_KEY = 'ls-docs-theme';
  const root = document.documentElement;
  const saved = localStorage.getItem(THEME_KEY);
  if (saved) root.setAttribute('data-theme', saved);

  window.toggleTheme = function () {
    const cur = root.getAttribute('data-theme') || 'dark';
    const next = cur === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    localStorage.setItem(THEME_KEY, next);
    const btn = document.getElementById('theme-toggle');
    if (btn) btn.textContent = next === 'dark' ? '☀️' : '🌙';
  };

  document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('theme-toggle');
    const theme = root.getAttribute('data-theme') || 'dark';
    if (btn) btn.textContent = theme === 'dark' ? '☀️' : '🌙';
  });
})();

/* ── Active Nav Link ─────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  const path = window.location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.sidebar a').forEach(a => {
    const href = a.getAttribute('href');
    if (href && href.includes(path)) a.classList.add('active');
  });
});

/* ── Mobile Sidebar Toggle ───────────────────────────────── */
window.toggleSidebar = function () {
  document.querySelector('.sidebar')?.classList.toggle('open');
};
document.addEventListener('click', e => {
  const sidebar = document.querySelector('.sidebar');
  const toggle = document.querySelector('.menu-toggle');
  if (sidebar && sidebar.classList.contains('open') && !sidebar.contains(e.target) && !toggle?.contains(e.target)) {
    sidebar.classList.remove('open');
  }
});

/* ── Copy Buttons ────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('pre').forEach(pre => {
    const code = pre.querySelector('code');
    if (!code) return;
    // If no pre-header, inject one
    if (!pre.querySelector('.pre-header')) {
      const lang = (code.className.match(/language-(\w+)/) || [])[1] || '';
      const header = document.createElement('div');
      header.className = 'pre-header';
      header.innerHTML = `<span>${lang}</span><button class="copy-btn" aria-label="Copy code">Copy</button>`;
      pre.insertBefore(header, code);
    }
    pre.querySelector('.copy-btn')?.addEventListener('click', () => {
      navigator.clipboard.writeText(code.innerText).then(() => {
        const btn = pre.querySelector('.copy-btn');
        btn.textContent = 'Copied!';
        btn.style.color = 'var(--green)';
        setTimeout(() => { btn.textContent = 'Copy'; btn.style.color = ''; }, 2000);
      });
    });
  });
});

/* ── Back to Top ─────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('back-to-top');
  if (!btn) return;
  window.addEventListener('scroll', () => {
    btn.classList.toggle('visible', window.scrollY > 400);
  });
  btn.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
});

/* ── Table of Contents Highlight ────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  // Support both .toc-inner (old) and .toc-nav (new) class names
  const tocLinks = document.querySelectorAll('.toc-inner a, .toc-nav a');
  if (!tocLinks.length) return;
  const headings = Array.from(document.querySelectorAll('h2[id], h3[id]'));
  const headerH = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--header-h')) || 60;

  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        tocLinks.forEach(a => a.classList.remove('toc-active'));
        const id = entry.target.id;
        const link =
          document.querySelector(`.toc-inner a[href="#${id}"]`) ||
          document.querySelector(`.toc-nav a[href="#${id}"]`);
        link?.classList.add('toc-active');
      }
    });
  }, { rootMargin: `-${headerH + 10}px 0px -80% 0px`, threshold: 0 });

  headings.forEach(h => observer.observe(h));
});

/* ── Search ──────────────────────────────────────────────── */
const PAGES = [
  { file: 'index.html',          title: 'Home',                 desc: 'Overview, features, quick start' },
  { file: 'getting-started.html',title: 'Getting Started',      desc: 'Installation, requirements, first test' },
  { file: 'api-reference.html',  title: 'API Reference',        desc: 'Engine, Scenario, run_scenario, execute_request, get_metrics' },
  { file: 'cli.html',            title: 'CLI Reference',        desc: 'Command-line flags, patterns, interactive mode' },
  { file: 'protocols.html',      title: 'Protocols',            desc: 'HTTP, WebSocket, TCP, UDP, MQTT, Database protocols' },
  { file: 'assertions.html',     title: 'Assertions',           desc: 'status_is, json_path, response_time_under, run_assertions' },
  { file: 'sessions-auth.html',  title: 'Sessions & Auth',      desc: 'Session management, authentication flows, cookies, tokens' },
  { file: 'architecture.html',   title: 'Architecture',         desc: 'C engine, Python extension, threading, connection pooling' },
  { file: 'troubleshooting.html',title: 'Troubleshooting',      desc: 'Segfault, build failures, memory, performance issues' },
  { file: 'roadmap.html',        title: 'Roadmap & Changelog',  desc: 'Phase 1 complete, future phases, version history' },
  { file: 'contributing.html',   title: 'Contributing',         desc: 'Dev setup, code style, testing, PR checklist' },
];

document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('search-input');
  const results = document.getElementById('search-results');
  if (!input || !results) return;

  input.addEventListener('input', () => {
    const q = input.value.toLowerCase().trim();
    if (!q) { results.classList.remove('visible'); return; }
    const matches = PAGES.filter(p =>
      p.title.toLowerCase().includes(q) || p.desc.toLowerCase().includes(q)
    );
    if (!matches.length) { results.classList.remove('visible'); return; }
    results.innerHTML = matches.map(p =>
      `<a href="${p.file}"><div>${p.title}</div><div class="sr-page">${p.desc}</div></a>`
    ).join('');
    results.classList.add('visible');
  });

  document.addEventListener('click', e => {
    if (!input.contains(e.target) && !results.contains(e.target)) {
      results.classList.remove('visible');
    }
  });
});

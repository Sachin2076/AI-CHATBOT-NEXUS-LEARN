/* ═══════════════════════════════════════════════════════════════
   theme.js  —  Nexus Learn global dark/light theme manager
   Include this ONCE in every page, before </body>
   ═══════════════════════════════════════════════════════════════ */

(function () {
  /* ── 1. Apply saved theme immediately (prevents flash) ───── */
  const saved = localStorage.getItem('nx-theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);

  /* ── 2. Public API ─────────────────────────────────────────── */
  window.NxTheme = {
    get: () => document.documentElement.getAttribute('data-theme') || 'dark',

    set: function (theme) {
      document.documentElement.setAttribute('data-theme', theme);
      localStorage.setItem('nx-theme', theme);
      // Sync every toggle on the page (navbar + any settings card)
      document.querySelectorAll('.nx-theme-toggle input[type="checkbox"]').forEach(cb => {
        cb.checked = (theme === 'light');
      });
      // Sync theme-card selections (settings page)
      document.querySelectorAll('.theme-card').forEach(c => {
        c.classList.toggle('active', c.dataset.themeVal === theme);
      });
      // Fire custom event so other scripts can react
      document.dispatchEvent(new CustomEvent('nx-theme-change', { detail: theme }));
    },

    toggle: function () {
      this.set(this.get() === 'dark' ? 'light' : 'dark');
    }
  };

  /* ── 3. Wire up any .nx-theme-toggle checkbox on DOM ready ── */
  function wireToggles() {
    const current = NxTheme.get();
    document.querySelectorAll('.nx-theme-toggle input[type="checkbox"]').forEach(cb => {
      cb.checked = (current === 'light');
      cb.addEventListener('change', () => NxTheme.toggle());
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wireToggles);
  } else {
    wireToggles();
  }
})();

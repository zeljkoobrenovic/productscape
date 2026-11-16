(() => {
  'use strict';
  // Shared tabs handle section links and keyboard navigation. Nested links such
  // as source citations also need to reveal the panel containing their target.
  function revealLinkedPanel() {
    let id;
    try { id = decodeURIComponent(window.location.hash.slice(1)); }
    catch (_) { return; }
    const target = id && document.getElementById(id);
    const panel = target && target.closest('.tabcontent');
    if (!panel) return;
    openTab(panel.dataset.tab, {updateHistory: false});
    if (id !== panel.dataset.tab) {
      requestAnimationFrame(() => target.scrollIntoView({block: 'start'}));
    }
  }
  initTab('value');
  revealLinkedPanel();
  window.addEventListener('hashchange', revealLinkedPanel);
  // Clicking the same citation twice does not produce a hashchange event.
  document.addEventListener('click', event => {
    const link = event.target.closest('a[href^="#"]');
    if (link && link.hash === window.location.hash) revealLinkedPanel();
  });
  const scenarios = JSON.parse(document.getElementById('market-data').textContent);
  const form = document.getElementById('market-form');
  if (!form || !scenarios.length) return;
  const keys = ['units', 'revenuePerUnit', 'serviceableShare', 'obtainableShare'];
  const select = document.getElementById('scenario');
  const state = document.getElementById('market-state');
  const error = document.getElementById('market-error');
  const scenario = () => scenarios[Number(select.value)];
  const percent = key => key.endsWith('Share');
  function calculate(edited) {
    const values = {};
    const valid = keys.every(key => {
      const input = document.getElementById(key);
      values[key] = input.valueAsNumber / (percent(key) ? 100 : 1);
      return input.validity.valid && Number.isFinite(values[key]);
    });
    const tam = values.units * values.revenuePerUnit;
    const sam = tam * values.serviceableShare;
    const som = sam * values.obtainableShare;
    const safe = valid && [tam, sam, som].every(Number.isFinite);
    error.hidden = safe;
    error.textContent = safe ? '' : 'Enter finite, nonnegative values. Shares must be between 0% and 100%.';
    const formatter = new Intl.NumberFormat('en', {style: 'currency', currency: scenario().currency, currencyDisplay: 'code', maximumFractionDigits: 0});
    Object.entries({tam, sam, som}).forEach(([key, value]) => {
      document.getElementById('result-' + key).textContent = safe ? formatter.format(value) : '—';
    });
    state.textContent = edited ? 'Your exploratory assumptions — unsaved and not a forecast. Original assumptions remain recorded below.' : 'Illustrative scenario assumptions — not a measured market forecast.';
  }
  function load() {
    const s = scenario();
    keys.forEach(key => { document.getElementById(key).value = s[key] * (percent(key) ? 100 : 1); });
    document.getElementById('label-units').textContent = s.unitLabel;
    document.getElementById('label-revenuePerUnit').textContent = s.revenueLabel;
    document.getElementById('scenario-scope').textContent = `${s.geography} · Base ${s.baseYear} · ${s.horizonYears}-year horizon · Annual ${s.currency} provider revenue`;
    calculate(false);
  }
  select.addEventListener('change', load);
  keys.forEach(key => document.getElementById(key).addEventListener('input', () => calculate(true)));
  document.getElementById('reset-market').addEventListener('click', load);
  form.addEventListener('submit', event => event.preventDefault());
  load();
})();

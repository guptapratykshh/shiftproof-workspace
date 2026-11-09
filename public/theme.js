// Apply the stored theme before the first paint without permitting inline scripts.
try {
  const stored = localStorage.getItem('shiftproof-theme');
  const preference = ['dark', 'light', 'system'].includes(stored) ? stored : 'light';
  document.documentElement.dataset.theme = preference === 'system'
    ? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
    : preference;
} catch {}

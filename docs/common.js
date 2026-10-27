// WorkMonitor サイト共通: 設定値とテーマ切り替え
const WM = {
  supabaseUrl: 'https://wbzfrhdhfmqxdjheiutl.supabase.co',
  // 公開用のキー（ブラウザに置いてよい種類。データは行レベルのアクセス制限で守られる）
  supabaseKey: 'sb_publishable_9v6XNPJ_Tdo4fcwejezQiA_LjUBYohT',
  repo: 'kaikomziu/WorkMonitor',
  downloads: {
    installer: 'https://github.com/kaikomziu/WorkMonitor/releases/latest/download/WorkMonitor-Setup.exe',
    zip: 'https://github.com/kaikomziu/WorkMonitor/releases/latest/download/WorkMonitor.zip',
  },
};

// ---- テーマ（選んだものはこのブラウザに保存）----
(function () {
  const root = document.documentElement;
  let saved = null;
  try { saved = localStorage.getItem('wm-theme'); } catch (e) { /* 保存できない環境でも動かす */ }
  if (saved === 'light' || saved === 'dark') root.dataset.theme = saved;

  WM.isDark = () => root.dataset.theme === 'dark' ||
    (!root.dataset.theme && matchMedia('(prefers-color-scheme: dark)').matches);

  WM.onThemeChange = [];
  WM.setTheme = (t) => {
    root.dataset.theme = t;
    try { localStorage.setItem('wm-theme', t); } catch (e) { /* 無視 */ }
    WM.updateThemeButtons();
    WM.onThemeChange.forEach(fn => fn());
  };
  WM.updateThemeButtons = () => {
    document.querySelectorAll('[data-theme-toggle]').forEach(b => {
      b.textContent = WM.isDark() ? '☀ ライト' : '🌙 ダーク';
      b.setAttribute('aria-label', WM.isDark() ? 'ライトテーマにする' : 'ダークテーマにする');
    });
  };
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-theme-toggle]').forEach(b =>
      b.addEventListener('click', () => WM.setTheme(WM.isDark() ? 'light' : 'dark')));
    WM.updateThemeButtons();
  });
})();

WM.esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
WM.fmt = s => `${Math.floor(s / 3600)}時間${String(Math.floor(s % 3600 / 60)).padStart(2, '0')}分`;

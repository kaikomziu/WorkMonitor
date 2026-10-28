// WorkMonitor の MOD ページ: 公開中の MOD の一覧（docs/mods/index.json）と投稿
const sb = supabase.createClient(WM.supabaseUrl, WM.supabaseKey);
const $ = id => document.getElementById(id);
const MOD_FILE = /^[a-z0-9][a-z0-9_-]{1,39}\.(py|zip)$/;
const MAX_SIZE = 512 * 1024;
// tools/mod_review.py の PERMISSIONS と同じ
const PERMISSIONS = {
  network: 'インターネットに接続します', browser: 'ブラウザでページを開きます', file_write: 'ファイルを書き込みます',
  file_read: 'ファイルを読み込みます', wm_logs: 'WorkMonitor の作業記録を読みます', thread: '裏で処理を動かします',
  panel: 'メイン画面に表示を追加します', overlay: 'オーバーレイの表示を変えます', discord: 'Discord の表示を変えます',
  notify: '通知を出します', sound: '音を鳴らします', dialog: 'ウィンドウを開きます',
};
const STATUS = { pending: ['審査待ち', 'wait'], reviewing: ['審査中', 'wait'], approved: ['✓ 公開', 'ok'], rejected: ['✗ 不合格', 'ng'] };
const ERRORS = {
  'wm:auth': 'ログインしてください。',
  'wm:terms': '新しい利用規約への同意が必要です。ページを読み込み直してください。',
  'wm:agree': '利用規約 第8条への同意が必要です。',
  'wm:name': 'ファイル名は「英小文字・数字・_・- で2〜40文字」+「.py か .zip」にしてください。',
  'wm:size': 'ファイルが大きすぎます（512KB まで）。',
  'wm:file': 'ファイルを読み込めませんでした。',
  'wm:taken': 'この名前の MOD は、ほかの人がすでに公開しています（または予約されています）。ファイル名を変えてください。',
  'wm:pending': '審査待ちの投稿が 3 件あります。審査が終わってから投稿してください。',
  'wm:daily': '今日の投稿は 10 件までです。明日また投稿してください。',
};
const jaError = e => {
  const m = (e && e.message) || String(e);
  for (const k in ERRORS) if (m.includes(k)) return ERRORS[k];
  return m;
};
const fmtSize = n => n < 1024 ? `${n}B` : `${(n / 1024).toFixed(1)}KB`;
const fmtDate = s => s ? new Date(s).toLocaleString('ja-JP', { dateStyle: 'short', timeStyle: 'short' }) : '';
const el = (tag, attrs = {}, ...children) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') e.className = v; else if (k === 'text') e.textContent = v; else e.setAttribute(k, v);
  }
  for (const c of children) if (c != null) e.append(c);
  return e;
};

// ================= 一覧 =================
let mods = [];

async function loadMods() {
  try {
    const res = await fetch('mods/index.json', { cache: 'no-cache' });
    if (!res.ok) throw new Error(res.status);
    mods = (await res.json()).mods || [];
  } catch (e) {
    $('mods').replaceChildren(el('div', { class: 'card empty', text: 'MOD の一覧を読み込めませんでした。時間をおいて読み込み直してください。' }));
    return;
  }
  render();
}

function render() {
  const q = $('search').value.trim().toLowerCase();
  const list = mods.filter(m => !q || [m.name, m.author, m.description, m.id].join(' ').toLowerCase().includes(q));
  $('count').textContent = `${list.length} 件`;
  if (!list.length) {
    $('mods').replaceChildren(el('div', { class: 'card empty', text: mods.length ? '見つかりませんでした。' : 'まだ MOD がありません。' }));
    return;
  }
  $('mods').replaceChildren(...list.map(card));
}

function card(m) {
  const v = m.versions[0];
  const perms = (v.permissions || []).map(p => el('span', { class: 'tag', text: PERMISSIONS[p] || p }));
  const older = m.versions.slice(1);
  return el('div', { class: 'card mod' },
    el('h3', { text: m.name }),
    el('div', { class: 'by', text: `作者: ${m.author} ・ v${m.version} ・ ${fmtDate(m.updated)} 公開 ・ ${m.id}` }),
    el('p', { class: 'desc', text: m.description }),
    el('div', { class: 'perms' }, el('span', { class: 'tag ok', text: '✓ 自動審査済み' }),
      ...(perms.length ? perms : [el('span', { class: 'tag', text: '通信・ファイル操作なし' })])),
    el('div', { class: 'foot' },
      el('a', { class: 'btn primary', href: v.file, download: v.file.split('/').pop(), text: `ダウンロード（${fmtSize(v.size)}）` }),
      el('a', { class: 'small', href: v.file, target: '_blank', rel: 'noopener', text: '中身を見る' })),
    el('div', { class: 'hash', title: 'ダウンロードしたファイルが改ざんされていないかの確認用', text: `SHA-256: ${v.sha256}` }),
    older.length ? el('details', {}, el('summary', { text: `以前のバージョン（${older.length}）` }),
      ...older.map(o => el('div', {}, el('a', { href: o.file, download: o.file.split('/').pop(), text: `v${o.version}` }),
        ` ・ ${fmtDate(o.published)} ・ ${fmtSize(o.size)}`))) : null,
  );
}

$('search').addEventListener('input', render);

// ================= 投稿 =================
let session = null;
let pollTimer = null;
const consented = () => !!session && ((session.user.user_metadata || {}).terms_version || '') >= WM.termsVersion;

function showSubmit() {
  $('sub-login').classList.toggle('hidden', !!session);
  $('sub-consent').classList.toggle('hidden', !session || consented());
  $('sub-form').classList.toggle('hidden', !session || !consented());
  $('mine').classList.toggle('hidden', !session);
  $('nav-login').classList.toggle('hidden', !!session);
  if (session) {
    $('sub-user').textContent = `${session.user.email} でログイン中`;
    loadMine();
  }
}

$('consent-btn').onclick = async () => {
  if (!$('consent-agree').checked) return alert('同意する場合はチェックを入れてください。');
  $('consent-btn').disabled = true;
  try {
    const { data, error } = await sb.auth.updateUser({ data: { terms_version: WM.termsVersion } });
    if (error) throw error;
    session.user = data.user;
    await sb.auth.refreshSession();   // 新しい同意を含んだ鍵（JWT）にする
    showSubmit();
  } catch (e) {
    alert(jaError(e));
  } finally {
    $('consent-btn').disabled = false;
  }
};

function subMsg(text, kind) { const m = $('sub-msg'); m.textContent = text || ''; m.className = 'msg ' + (kind || ''); }

$('sub-file').addEventListener('change', () => {
  const f = $('sub-file').files[0];
  subMsg('');
  if (!f) return $('sub-file-info').textContent = '';
  const ok = MOD_FILE.test(f.name) && f.size <= MAX_SIZE && f.size > 0;
  $('sub-file-info').textContent = ok ? `MOD の名前: ${f.name.replace(/\.(py|zip)$/, '')}（${fmtSize(f.size)}）` : '';
  if (!MOD_FILE.test(f.name)) subMsg(ERRORS['wm:name'], 'error');
  else if (f.size > MAX_SIZE) subMsg(ERRORS['wm:size'], 'error');
});

const toBase64 = file => new Promise((resolve, reject) => {
  const r = new FileReader();
  r.onload = () => resolve(String(r.result).split(',')[1] || '');
  r.onerror = () => reject(new Error('wm:file'));
  r.readAsDataURL(file);
});

$('sub-form').onsubmit = async (e) => {
  e.preventDefault();
  const f = $('sub-file').files[0];
  if (!f) return subMsg('ファイルを選んでください。', 'error');
  if (!MOD_FILE.test(f.name)) return subMsg(ERRORS['wm:name'], 'error');
  if (f.size > MAX_SIZE || f.size === 0) return subMsg(ERRORS['wm:size'], 'error');
  if (!$('sub-agree').checked) return subMsg(ERRORS['wm:agree'], 'error');
  $('sub-btn').disabled = true;
  subMsg('送信しています…');
  try {
    const { error } = await sb.rpc('wm_mod_submit', { p_file_name: f.name, p_file_b64: await toBase64(f), p_agreed: true });
    if (error) throw error;
    $('sub-form').reset();
    $('sub-file-info').textContent = '';
    subMsg('受け付けました。10〜20 分ほどで自動審査が終わります。結果は下の「あなたの投稿」に出ます。', 'ok');
    loadMine();
  } catch (err) {
    subMsg(jaError(err), 'error');
  } finally {
    $('sub-btn').disabled = false;
  }
};

async function loadMine() {
  const { data, error } = await sb.from('wm_mod_submissions')
    .select('id, file_name, status, version, report, created_at, reviewed_at')
    .order('created_at', { ascending: false }).limit(20);
  if (error) return;
  const rows = data.map(s => {
    const [label, cls] = STATUS[s.status] || [s.status, ''];
    const report = s.report || {};
    const findings = (report.findings || []).filter(f => s.status === 'rejected' ? f.level === 'block' : f.level === 'note');
    let result;
    if (s.status === 'approved') {
      result = el('div', {}, el('span', { text: `v${s.version} を公開しました` }),
        report.published ? el('div', {}, el('a', { href: report.published, text: 'ファイル' })) : null);
    } else if (s.status === 'rejected') {
      result = el('ul', { class: 'findings' }, ...findings.map(f =>
        el('li', { class: 'block', text: `${f.file ? `${f.file}${f.line ? `:${f.line}` : ''} ` : ''}${f.message}` })));
    } else {
      result = el('span', { class: 'sub', text: '自動審査を待っています' });
    }
    const del = s.status === 'pending' ? el('button', { class: 'btn', type: 'button', text: '取り消す' }) : null;
    if (del) del.onclick = async () => {
      if (!confirm(`${s.file_name} の投稿を取り消しますか？`)) return;
      await sb.from('wm_mod_submissions').delete().eq('id', s.id);
      loadMine();
    };
    return el('tr', {}, el('td', { text: s.file_name }), el('td', { text: fmtDate(s.created_at) }),
      el('td', {}, el('span', { class: `tag ${cls}`, text: label })), el('td', {}, result), el('td', {}, del));
  });
  $('mine-rows').replaceChildren(...(rows.length ? rows : [el('tr', {}, el('td', { colspan: '5', class: 'sub', text: 'まだ投稿はありません。' }))]));
  // 審査待ちがあるあいだは 1 分ごとに確認
  clearTimeout(pollTimer);
  if (data.some(s => s.status === 'pending' || s.status === 'reviewing')) {
    pollTimer = setTimeout(() => { loadMine(); loadMods(); }, 60000);
  }
}

sb.auth.onAuthStateChange((_event, s) => { session = s; showSubmit(); });
sb.auth.getSession().then(({ data }) => { session = data.session; showSubmit(); });
loadMods();

// WorkMonitor の「記録を見る」ページ
// 記録はエンドツーエンド暗号化されている。パスワードからこのブラウザ内で鍵を作って復号する（crypto.js）
const sb = supabase.createClient(WM.supabaseUrl, WM.supabaseKey);
const $ = id => document.getElementById(id);
const pageUrl = location.origin + location.pathname;
const MIN_PASSWORD = 8;

// ================= ログイン・登録・鍵 =================
let authMode = 'login';   // login / signup / forgot / recovery / unlock / consent
let session = null;
let dek = null;            // データ鍵（取り出し不可の CryptoKey）
let pendingPassword = null;
let afterSignOutMessage = null;

const AUTH_TEXT = {
  login:    { title: 'ログイン', submit: 'ログイン', desc: 'WorkMonitor アプリと同じアカウントでログインすると、同期した記録を見られます。記録は暗号化されていて、パスワードからこのブラウザの中でだけ鍵を作って読みます。' },
  signup:   { title: '新しく登録', submit: '登録する', desc: '登録後に確認メールが届きます。リンクを開くと登録が完了します。パスワードは記録の暗号化の鍵にも使うので、8文字以上の推測されにくいものにしてください。' },
  forgot:   { title: 'パスワードの再設定', submit: '再設定メールを送る', desc: '登録したメールアドレスに、パスワードを再設定するためのリンクを送ります。記録は古いパスワードで暗号化されているため、再設定するとクラウドの記録は作り直しになります（アプリの次の同期で、PC の記録から最大120日分が送り直されます）。' },
  recovery: { title: '新しいパスワード', submit: 'パスワードを変更', desc: '新しいパスワードを入力してください（8文字以上）。暗号鍵も新しいパスワードで作り直します。' },
  unlock:   { title: '記録の暗号を解除', submit: '解除して表示', desc: '記録は暗号化されています。このブラウザで見るには、パスワードを入力してください（パスワードはサーバーに送らず、この中で鍵を作るのに使います）。' },
  consent:  { title: '利用規約・プライバシーポリシー', submit: '同意して続ける', desc: '続けるには、利用規約とプライバシーポリシーをお読みのうえ、同意してください。' },
};
// 同意した版（サーバー側で日時と一緒に記録される）
const consented = () => !!session && (session.user.user_metadata || {}).terms_version === WM.termsVersion;
const ERRORS = {
  'invalid login credentials': 'メールアドレスかパスワードが違います。',
  'email not confirmed': 'メールアドレスの確認が済んでいません。届いた確認メールのリンクを開いてください。',
  'user already registered': 'このメールアドレスはすでに登録されています。ログインしてください。',
  'password should be at least': `パスワードは${MIN_PASSWORD}文字以上にしてください。`,
  'pwned': 'このパスワードは過去に流出したことがあるため使えません。別のパスワードにしてください。',
  'rate limit': '送信が多すぎます。しばらく待ってからやり直してください。',
  'same password': '今と同じパスワードは使えません。',
};
const jaError = e => {
  const m = (e && e.message || String(e)).toLowerCase();
  for (const k in ERRORS) if (m.includes(k)) return ERRORS[k];
  return (e && e.message) || String(e);
};
function msg(text, kind) { const el = $('auth-msg'); el.textContent = text || ''; el.className = 'msg ' + (kind || ''); }

function setAuthMode(m) {
  authMode = m;
  const t = AUTH_TEXT[m];
  $('auth-title').textContent = t.title;
  $('auth-desc').textContent = t.desc;
  $('auth-submit').textContent = t.submit;
  $('auth-tabs').classList.toggle('hidden', !(m === 'login' || m === 'signup'));
  document.querySelectorAll('#auth-tabs button').forEach(b => b.classList.toggle('on', b.dataset.tab === m));
  $('f-email').classList.toggle('hidden', m === 'recovery' || m === 'unlock' || m === 'consent');
  $('f-password').classList.toggle('hidden', m === 'forgot' || m === 'consent');
  $('f-remember').classList.toggle('hidden', !(m === 'login' || m === 'unlock'));
  $('f-agree').classList.toggle('hidden', !(m === 'signup' || m === 'consent'));
  $('agree').checked = false;
  $('password').autocomplete = (m === 'login' || m === 'unlock') ? 'current-password' : 'new-password';
  $('password').value = '';
  $('auth-alt').innerHTML = m === 'login' ? '<a href="#forgot">パスワードを忘れた場合</a>'
                          : m === 'forgot' ? '<a href="#">ログインに戻る</a>' : '';
  msg('');
}
document.querySelectorAll('#auth-tabs button').forEach(b => b.onclick = () => setAuthMode(b.dataset.tab));
window.addEventListener('hashchange', () => { if (!session) setAuthMode(location.hash === '#forgot' ? 'forgot' : 'login'); });

$('auth-form').onsubmit = async (e) => {
  e.preventDefault();
  const email = $('email').value.trim(), password = $('password').value;
  if ((authMode === 'signup' || authMode === 'consent') && !$('agree').checked)
    return msg('利用規約とプライバシーポリシーへの同意が必要です。', 'error');
  if (authMode === 'consent') return agreeToTerms();
  if (authMode !== 'forgot' && !password) return msg('パスワードを入力してください。', 'error');
  if ((authMode === 'signup' || authMode === 'recovery') && password.length < MIN_PASSWORD)
    return msg(`パスワードは${MIN_PASSWORD}文字以上にしてください。`, 'error');
  $('auth-submit').disabled = true;
  msg(authMode === 'login' || authMode === 'unlock' ? '鍵を作っています…（数秒かかります）' : '処理しています…');
  try {
    if (authMode === 'login') {
      pendingPassword = password;   // ログイン後に鍵を作るのに使う（保存はしない）
      const { error } = await sb.auth.signInWithPassword({ email, password });
      if (error) { pendingPassword = null; throw error; }
    } else if (authMode === 'unlock') {
      await unlock(password, { allowReset: false });
      showDashboard();
    } else if (authMode === 'signup') {
      const { data, error } = await sb.auth.signUp({ email, password,
        options: { emailRedirectTo: pageUrl, data: { terms_version: WM.termsVersion } } });
      if (error) throw error;
      if (!data.session) msg(`${email} に確認メールを送りました。メールのリンクを開くと登録が完了します。`, 'ok');
    } else if (authMode === 'forgot') {
      const { error } = await sb.auth.resetPasswordForEmail(email, { redirectTo: pageUrl });
      if (error) throw error;
      msg('再設定のメールを送りました。メールのリンクを開いてください。', 'ok');
    } else if (authMode === 'recovery') {
      const { error } = await sb.auth.updateUser({ password });
      if (error) throw error;
      await resetVault(password);   // 古い鍵は古いパスワードでしか開けないので作り直す
      history.replaceState(null, '', pageUrl);
      authMode = 'login';
      showDashboard();
    }
  } catch (err) {
    msg(jaError(err), 'error');
  } finally {
    $('auth-submit').disabled = false;
  }
};

// 同意を記録する（ユーザー情報に版を入れると、サーバーが日時と一緒に wm_consents に記録する）
async function agreeToTerms() {
  $('auth-submit').disabled = true;
  try {
    const { data, error } = await sb.auth.updateUser({ data: { terms_version: WM.termsVersion } });
    if (error) throw error;
    session.user = data.user;
    authMode = 'login';
    showDashboard();   // USER_UPDATED でも呼ばれるが、二重に動かないようにしてある
  } catch (err) {
    msg(jaError(err), 'error');
  } finally {
    $('auth-submit').disabled = false;
  }
}

// アカウントの削除（記録・鍵・同意の記録もサーバーで一緒に消える）
$('delete-account').onclick = async () => {
  if (!session) return;
  const email = session.user.email;
  const typed = prompt(`アカウントを削除します。クラウドの記録はすべて消え、元に戻せません（PC の記録は残ります）。\n\n確認のため、メールアドレス（${email}）を入力してください。`);
  if (typed === null) return;
  if (typed.trim().toLowerCase() !== email.toLowerCase()) { alert('メールアドレスが一致しないため、削除しませんでした。'); return; }
  const btn = $('delete-account');
  btn.disabled = true;
  try {
    const { error } = await sb.rpc('wm_delete_account');
    if (error) throw error;
    await E2EE.deleteKey(session.user.id);
    dek = null;
    afterSignOutMessage = 'アカウントを削除しました。ご利用ありがとうございました。';
    await sb.auth.signOut({ scope: 'local' });   // サーバー側のセッションはアカウントと一緒に消えている
  } catch (err) {
    alert('削除できませんでした: ' + jaError(err));
  } finally {
    btn.disabled = false;
  }
};

$('logout').onclick = async () => {
  if (session) await E2EE.deleteKey(session.user.id);   // この端末に記憶した鍵も消す
  dek = null;
  await sb.auth.signOut();
};

sb.auth.onAuthStateChange((event, s) => {
  session = s;
  if (event === 'PASSWORD_RECOVERY') { showAuth('recovery'); return; }
  if (authMode === 'recovery' && s) return;   // 新しいパスワードの入力中はそのまま
  if (!s) {
    dek = null; loadedFor = null;
    showAuth(location.hash === '#forgot' ? 'forgot' : 'login');
    if (afterSignOutMessage) { msg(afterSignOutMessage, 'ok'); afterSignOutMessage = null; }
    return;
  }
  // onAuthStateChange の中で待つと supabase-js が詰まるので、少し後で続ける
  setTimeout(() => showDashboard(), 0);
});

function showAuth(mode) {
  $('dash').classList.add('hidden');
  $('auth').classList.remove('hidden');
  const loggedIn = !!session && (mode === 'unlock' || mode === 'consent');
  $('logout').classList.toggle('hidden', !loggedIn);
  $('user-email').classList.toggle('hidden', !loggedIn);
  if (loggedIn) $('user-email').textContent = session.user.email;
  setAuthMode(mode);
}

// ---- 鍵の保管庫 ----
async function getVault() {
  const { data, error } = await sb.from('wm_profiles').select('kdf_salt,kdf_iterations,wrapped_key').maybeSingle();
  if (error) throw error;
  return data && data.wrapped_key ? data : null;
}

async function putVault(vault) {
  const { error } = await sb.from('wm_profiles').upsert({ user_id: session.user.id, ...vault, settings_payload: null });
  if (error) throw error;
}

async function resetVault(password) {
  const uid = session.user.id;
  const { error } = await sb.from('wm_days').delete().eq('user_id', uid);
  if (error) throw error;
  const made = await E2EE.newVault(password, uid);
  await putVault(made.vault);
  dek = made.dek;
  if ($('remember').checked) await E2EE.saveKey(uid, dek);
}

// パスワードからデータ鍵を取り出す（まだ鍵が無ければ作る）
async function unlock(password, { allowReset }) {
  const uid = session.user.id;
  const vault = await getVault();
  if (!vault) {
    const made = await E2EE.newVault(password, uid);
    await putVault(made.vault);
    dek = made.dek;
  } else {
    try {
      dek = await E2EE.unwrap(password, uid, vault);
    } catch (e) {
      if (!allowReset) throw new Error('パスワードが違います。');
      // ログインできた（＝今のパスワードは正しい）のに開けない ＝ 鍵が古いパスワードで作られている
      if (!confirm('暗号鍵が以前のパスワードで作られているため、クラウドの記録を読めません。\n'
                 + '鍵を作り直しますか？（クラウドの記録は消え、アプリの次の同期で PC の記録から送り直されます）')) {
        throw new Error('暗号鍵を作り直さなかったため、記録を表示できません。');
      }
      await resetVault(password);
      return;
    }
  }
  if ($('remember').checked) await E2EE.saveKey(uid, dek);
}

let loadedFor = null;
let showing = null;
// ログイン状態の変化とボタン操作の両方から呼ばれるので、実行中なら同じ処理を待つ
function showDashboard() {
  if (!showing) showing = openDashboard().finally(() => { showing = null; });
  return showing;
}
async function openDashboard() {
  if (!session) return;
  const uid = session.user.id;
  // まだ今の版の利用規約に同意していなければ、先に同意をお願いする（パスワードは鍵作りのために残しておく）
  if (!consented()) { showAuth('consent'); return; }
  try {
    if (!dek && pendingPassword) {
      const pw = pendingPassword;
      pendingPassword = null;
      await unlock(pw, { allowReset: true });
    }
    if (!dek) dek = await E2EE.loadKey(uid);
  } catch (err) {
    showAuth('unlock');
    msg(jaError(err), 'error');
    return;
  }
  if (!dek) { showAuth('unlock'); return; }

  $('auth').classList.add('hidden');
  $('dash').classList.remove('hidden');
  $('logout').classList.remove('hidden');
  $('user-email').textContent = session.user.email;
  $('user-email').classList.remove('hidden');
  if (loadedFor !== uid) { loadedFor = uid; loadData(); }
}

// ================= データ =================
let DATA = {}, dates = [], GOAL = 0, COLORS = {}, CATS = [], APPS = [];
const PALETTE = ['#4f6bed','#22a06b','#e2a03f','#d9534f','#8e6bd8','#2bb3c0','#e57fb0','#7f8c8d'];
const catColor = c => COLORS[c] || PALETTE[Math.max(0, CATS.indexOf(c)) % PALETTE.length];

// ---- まとめ方（アプリ別 / カテゴリ別）。行は [アプリ名, 秒, カテゴリ] ----
const OTHER = 'その他', OTHER_COLOR = '#8a919c', TOP_N = 7;   // グラフに出すのは上位7つ + その他
let group = 'app';
const GI = () => group === 'app' ? 0 : 2;
const GN = () => group === 'app' ? 'アプリ' : 'カテゴリ';
const groupColor = k => k === OTHER ? OTHER_COLOR
  : group === 'app' ? PALETTE[Math.max(0, APPS.indexOf(k)) % (PALETTE.length - 1)] : catColor(k);
document.querySelectorAll('#group button').forEach(b => b.onclick = () => {
  group = b.dataset.group;
  document.querySelectorAll('#group button').forEach(x => x.classList.toggle('on', x.dataset.group === group));
  if (sel.value) render(sel.value);
});
const total = d => (DATA[d] || []).reduce((a, r) => a + r[1], 0);

async function loadData() {
  $('root').innerHTML = '<div class="card empty sub">読み込んで復号しています…</div>';
  const uid = session.user.id;
  try {
    const since = new Date(); since.setDate(since.getDate() - 400);
    const enc = [];
    // 1回に取れる行数に上限があるので、1000行ずつ取る
    for (let from = 0; ; from += 1000) {
      const { data, error } = await sb.from('wm_days').select('day,payload')
        .gte('day', iso(since)).order('day').range(from, from + 999);
      if (error) throw error;
      enc.push(...data);
      if (data.length < 1000) break;
    }
    const { data: prof } = await sb.from('wm_profiles').select('settings_payload,last_sync_at,app_version').maybeSingle();

    // 復号（AAD にユーザー ID と日付が入っているので、すり替えられた行は復号に失敗する）
    DATA = {};
    let failed = 0;
    for (const r of enc) {
      try {
        const rows = await E2EE.decryptJson(dek, r.payload, E2EE.aadDay(uid, r.day));
        if (rows.length) DATA[r.day] = rows.map(x => [x.name, x.seconds, x.category]);
      } catch (e) { failed++; }
    }
    if (enc.length && failed === enc.length) {
      // 鍵が合わない（別の場所でパスワードを変えた等）→ 記憶した鍵を消して入れ直してもらう
      await E2EE.deleteKey(uid);
      dek = null; loadedFor = null;
      showAuth('unlock');
      msg('記憶していた鍵では記録を復号できませんでした。パスワードを入力してください。', 'error');
      return;
    }
    let settings = {};
    if (prof && prof.settings_payload) {
      try { settings = await E2EE.decryptJson(dek, prof.settings_payload, E2EE.aadSettings(uid)); } catch (e) { /* 表示は既定値で続ける */ }
    }
    dates = Object.keys(DATA).sort();
    GOAL = (settings.daily_goal_min || 0) * 60;
    COLORS = settings.category_colors || {};
    const ct = {};
    dates.forEach(d => DATA[d].forEach(r => ct[r[2]] = (ct[r[2]] || 0) + r[1]));
    CATS = Object.keys(ct).sort((a, b) => ct[b] - ct[a]);
    // アプリの色は全期間で多い順に固定
    const at = {};
    dates.forEach(d => DATA[d].forEach(r => at[r[0]] = (at[r[0]] || 0) + r[1]));
    APPS = Object.keys(at).sort((a, b) => at[b] - at[a]);
    $('sync-info').textContent = (prof && prof.last_sync_at
      ? `最後の同期: ${new Date(prof.last_sync_at).toLocaleString('ja-JP')}（アプリ ${prof.app_version || ''}）。`
      : '') + '🔒 記録はエンドツーエンド暗号化（AES-256-GCM）されています。'
      + (failed ? ` 復号できなかった日が ${failed} 日あります。` : '');
    if (!dates.length) {
      $('root').innerHTML = `<div class="card empty"><h2 style="font-size:18px">まだ同期された記録がありません</h2>
        <p class="sub">WorkMonitor アプリ（v1.3.0 以降）の「設定 → アカウント」で、このアカウントにログインしてください。<br>ログインすると、これまでの記録（最大120日分）が暗号化して送られます。</p>
        <a class="btn primary" href="./#download">アプリをダウンロード</a></div>`;
      return;
    }
    setMode(location.hash.slice(1) in MODES ? location.hash.slice(1) : 'day');
  } catch (err) {
    $('root').innerHTML = `<div class="card empty"><p class="down">読み込めませんでした: ${WM.esc(jaError(err))}</p></div>`;
  }
}

// ================= 期間（日・週・月） =================
const pad = n => String(n).padStart(2, '0');
const iso = dt => `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}`;
const parse = s => { const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d || 1); };
const addDays = (s, n) => { const d = parse(s); d.setDate(d.getDate() + n); return iso(d); };
const mondayOf = s => { const d = parse(s); d.setDate(d.getDate() - (d.getDay() + 6) % 7); return iso(d); };
const monthOf = s => s.slice(0, 7);
const md = s => `${+s.slice(5, 7)}/${+s.slice(8, 10)}`;
const WEEKDAY = ['日', '月', '火', '水', '木', '金', '土'];
const MODES = {
  day:   { name: '日', prevName: '前日',   key: s => s, label: s => `${s}（${WEEKDAY[parse(s).getDay()]}）`,
           days: k => [k], prev: k => addDays(k, -1) },
  week:  { name: '週', prevName: '前の週', key: mondayOf, label: k => `${md(k)}〜${md(addDays(k, 6))} の週`,
           days: k => [...Array(7).keys()].map(i => addDays(k, i)), prev: k => addDays(k, -7) },
  month: { name: '月', prevName: '前の月', key: monthOf, label: k => `${+k.slice(0, 4)}年${+k.slice(5)}月`,
           days: k => { const d = parse(k + '-01'), out = []; while (monthOf(iso(d)) === k) { out.push(iso(d)); d.setDate(d.getDate() + 1); } return out; },
           prev: k => { const d = parse(k + '-01'); d.setMonth(d.getMonth() - 1); return monthOf(iso(d)); } },
};
let mode = 'day', charts = [];
const sel = $('period');
document.querySelectorAll('#mode button').forEach(b => b.onclick = () => setMode(b.dataset.mode));
sel.onchange = () => render(sel.value);
WM.onThemeChange.push(() => { if (sel.value) render(sel.value); });

function setMode(m, key) {
  mode = m;
  document.querySelectorAll('#mode button').forEach(b => b.classList.toggle('on', b.dataset.mode === m));
  const keys = [...new Set(dates.map(MODES[m].key))].sort().reverse();
  sel.innerHTML = '';
  keys.forEach(k => sel.add(new Option(MODES[m].label(k), k)));
  if (key && keys.includes(key)) sel.value = key;
  render(sel.value);
}

function sumBy(rows, idx) {
  const m = {};
  rows.forEach(r => m[r[idx]] = (m[r[idx]] || 0) + r[1]);
  return Object.entries(m).sort((a, b) => b[1] - a[1]);
}
function diffHtml(now, before) {
  if (!before) return '<span>比較なし</span>';
  const p = (now - before) / before * 100;
  return `<span class="${p >= 0 ? 'up' : 'down'}">${p >= 0 ? '▲' : '▼'} ${Math.abs(p).toFixed(0)}%</span>`;
}

function render(key) {
  charts.forEach(c => c.destroy()); charts = [];
  const M = MODES[mode], fmt = WM.fmt, esc = WM.esc;
  const days = M.days(key), prevDays = M.days(M.prev(key));
  const rows = days.flatMap(d => DATA[d] || []);
  const prevRows = prevDays.flatMap(d => DATA[d] || []);
  const sum = days.reduce((a, d) => a + total(d), 0);
  const prevSum = prevDays.reduce((a, d) => a + total(d), 0);
  const base = sum || 1;
  const cats = sumBy(rows, 2);
  const prevCats = Object.fromEntries(sumBy(prevRows, 2));
  const apps = sumBy(rows, 0);
  const prevApps = Object.fromEntries(sumBy(prevRows, 0));
  const appCat = {}; rows.forEach(r => appCat[r[0]] = r[2]);
  // グラフ用: 選んだまとめ方で集計（上位 TOP_N 以外は「その他」）
  const groups = sumBy(rows, GI());
  const prevGroups = Object.fromEntries(sumBy(prevRows, GI()));
  const topKeys = groups.slice(0, TOP_N).map(x => x[0]);
  const keyOf = r => topKeys.includes(r[GI()]) ? r[GI()] : OTHER;
  const chartGroups = sumBy(rows.map(r => { const c = r.slice(); c[GI()] = keyOf(r); return c; }), GI());

  let kpis;
  if (mode === 'day') {
    const idx = dates.indexOf(key);
    const last7 = dates.slice(Math.max(0, idx - 6), idx + 1);
    const avg7 = last7.reduce((a, d) => a + total(d), 0) / last7.length;
    kpis = [
      ['この日の作業時間', fmt(sum), GOAL ? (sum >= GOAL ? `<span class="up">🎉 目標達成（${Math.round(sum / GOAL * 100)}%）</span>` : `目標の ${Math.round(sum / GOAL * 100)}%`) : `${diffHtml(sum, prevSum)} 前日比`],
      ['直近7日の平均', fmt(avg7), ''],
      ['いちばん使ったアプリ', apps[0] ? esc(apps[0][0]) : '-', apps[0] ? fmt(apps[0][1]) : ''],
      ['いちばん多いカテゴリ', cats[0] ? esc(cats[0][0]) : '-', cats[0] ? fmt(cats[0][1]) : ''],
    ];
  } else {
    const worked = days.filter(d => total(d) > 0);
    const achieved = days.filter(d => GOAL && total(d) >= GOAL).length;
    kpis = [
      [`この${M.name}の合計`, fmt(sum), `${diffHtml(sum, prevSum)} ${M.prevName}（${fmt(prevSum)}）より`],
      ['1日の平均', fmt(worked.length ? sum / worked.length : 0), `作業した日 ${worked.length}日 / ${days.length}日`],
      [`いちばん多い${GN()}`, groups[0] ? esc(groups[0][0]) : '-', groups[0] ? fmt(groups[0][1]) : ''],
      GOAL ? ['目標を達成した日', `${achieved}日`, `目標 ${fmt(GOAL)} / 日`]
           : ['いちばん作業した日', worked.length ? md(worked.slice().sort((a, b) => total(b) - total(a))[0]) : '-', ''],
    ];
  }

  const ratioHead = mode === 'day' ? '割合' : M.prevName + '比';
  const appColor = a => group === 'app' ? groupColor(topKeys.includes(a) ? a : OTHER) : catColor(appCat[a]);
  const appTable = `<div class="card scroll"><h2>アプリ別の内訳</h2>
        <table><thead><tr><th>アプリ</th><th>カテゴリ</th><th class="num">時間</th><th class="num">${ratioHead}</th></tr></thead><tbody>
        ${apps.slice(0, 15).map(([a, s]) => `<tr><td><span class="dot" style="background:${appColor(a)}"></span>${esc(a)}</td><td><span class="tag">${esc(appCat[a])}</span></td><td class="num">${fmt(s)}</td><td class="num">${mode === 'day' ? (s / base * 100).toFixed(1) + '%' : diffHtml(s, prevApps[a])}</td></tr>`).join('')}
        </tbody></table></div>`;
  const catTable = `<div class="card scroll"><h2>カテゴリ別の内訳</h2>
        <table><thead><tr><th>カテゴリ</th><th style="width:28%"></th><th class="num">時間</th><th class="num">${ratioHead}</th></tr></thead><tbody>
        ${cats.map(([c, s]) => `<tr><td><span class="dot" style="background:${catColor(c)}"></span>${esc(c)}</td><td><div class="bar" style="width:${s / cats[0][1] * 100}%;background:${catColor(c)}"></div></td><td class="num">${fmt(s)}</td><td class="num">${mode === 'day' ? (s / base * 100).toFixed(1) + '%' : diffHtml(s, prevCats[c])}</td></tr>`).join('')}
        </tbody></table></div>`;

  $('root').innerHTML = `
    <div class="kpis">${kpis.map(([l, v, n]) => `<div class="card kpi"><div class="label">${l}</div><div class="value">${v}</div><div class="note">${n}</div></div>`).join('')}</div>
    <div class="card" style="margin-bottom:12px"><h2>${mode === 'day' ? `日別の作業時間（直近30日・${GN()}別）` : `日別の作業時間（この${M.name}・${GN()}別）`}</h2><div class="chart"><canvas id="cDaily"></canvas></div></div>
    <div class="grid">
      <div class="card"><h2>${GN()}別</h2><div class="chart"><canvas id="cCat"></canvas></div></div>
      <div class="card"><h2>${mode === 'day' ? `${GN()}別の時間` : `${GN()}別の推移（${M.prevName}と比べて）`}</h2><div class="chart"><canvas id="cThird"></canvas></div></div>
    </div>
    <div class="grid">${group === 'app' ? appTable + catTable : catTable + appTable}</div>`;

  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  Chart.defaults.color = css('--sub');
  Chart.defaults.borderColor = css('--line');
  Chart.defaults.font.family = '"Segoe UI","Yu Gothic UI","Hiragino Sans",sans-serif';
  const legend = { display: true, position: 'bottom', labels: { boxWidth: 10, boxHeight: 10 } };
  const opt = { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } };

  // 日別（アプリ / カテゴリで積み上げ + 目標ライン）
  let span;
  if (mode === 'day') { const idx = dates.indexOf(key); span = dates.slice(Math.max(0, idx - 29), idx + 1); }
  else span = days;
  const spanTop = sumBy(span.flatMap(d => DATA[d] || []), GI()).slice(0, TOP_N).map(x => x[0]);
  const spanKey = r => spanTop.includes(r[GI()]) ? r[GI()] : OTHER;
  const spanKeys = [...spanTop, ...(span.some(d => (DATA[d] || []).some(r => spanKey(r) === OTHER)) ? [OTHER] : [])];
  const ofDay = (d, k) => (DATA[d] || []).filter(r => spanKey(r) === k).reduce((a, r) => a + r[1], 0);
  const ds = spanKeys.map(k => ({ label: k, data: span.map(d => +(ofDay(d, k) / 3600).toFixed(2)), backgroundColor: groupColor(k), borderRadius: 3, stack: 'work' }));
  if (GOAL) ds.push({ type: 'line', label: '目標', data: span.map(() => +(GOAL / 3600).toFixed(2)), stack: 'goal',
    borderColor: css('--sub'), borderDash: [6, 4], borderWidth: 1.5, pointRadius: 0, fill: false });
  charts.push(new Chart($('cDaily'), {
    type: 'bar',
    data: { labels: span.map(d => mode === 'month' ? String(+d.slice(8)) : `${md(d)}(${WEEKDAY[parse(d).getDay()]})`), datasets: ds },
    options: { ...opt, scales: { x: { stacked: true }, y: { stacked: true, title: { display: true, text: '時間' } } },
      plugins: { legend, tooltip: { callbacks: {
        label: c => c.dataset.stack === 'goal' ? `目標: ${fmt(GOAL)}` : `${c.dataset.label}: ${fmt(ofDay(span[c.dataIndex], c.dataset.label))}`,
        footer: items => `合計 ${fmt(total(span[items[0].dataIndex]))}` } } },
      onClick: (e, els) => { if (els.length) setMode('day', span[els[0].index]); } }
  }));

  charts.push(new Chart($('cCat'), {
    type: 'doughnut',
    data: { labels: chartGroups.map(x => x[0]), datasets: [{ data: chartGroups.map(x => x[1]), backgroundColor: chartGroups.map(x => groupColor(x[0])), borderColor: css('--card'), borderWidth: 2 }] },
    options: { ...opt, plugins: { legend: { ...legend, position: 'right' }, tooltip: { callbacks: { label: c => `${c.label}: ${fmt(c.raw)}` } } } }
  }));

  if (mode === 'day') {
    const top = chartGroups.slice(0, 8);
    charts.push(new Chart($('cThird'), {
      type: 'bar',
      data: { labels: top.map(x => x[0]), datasets: [{ data: top.map(x => +(x[1] / 3600).toFixed(2)), backgroundColor: top.map(x => groupColor(x[0])), borderRadius: 3 }] },
      options: { ...opt, indexAxis: 'y', scales: { x: { title: { display: true, text: '時間' } } },
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => fmt(c.raw * 3600) } } } }
    }));
  } else {
    // 前の期間との比較（多い順に最大10件）
    const now = k => (groups.find(x => x[0] === k) || [0, 0])[1];
    const names = [...new Set([...groups.map(x => x[0]), ...Object.keys(prevGroups)])]
      .sort((a, b) => (now(b) + (prevGroups[b] || 0)) - (now(a) + (prevGroups[a] || 0))).slice(0, 10);
    charts.push(new Chart($('cThird'), {
      type: 'bar',
      data: { labels: names, datasets: [
        { label: M.prevName, data: names.map(k => +((prevGroups[k] || 0) / 3600).toFixed(2)), backgroundColor: css('--line'), borderRadius: 3 },
        { label: `この${M.name}`, data: names.map(k => +(now(k) / 3600).toFixed(2)), backgroundColor: names.map(k => groupColor(k)), borderRadius: 3 },
      ] },
      options: { ...opt, indexAxis: 'y', scales: { x: { title: { display: true, text: '時間' } } },
        plugins: { legend, tooltip: { callbacks: { label: c => `${c.dataset.label}: ${fmt(c.raw * 3600)}` } } } }
    }));
  }
}

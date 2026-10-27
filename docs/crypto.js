// エンドツーエンド暗号化（アプリの e2ee.py と同じ形式。WebCrypto を使う）
//   データ鍵: AES-256-GCM（ブラウザ内では取り出し不可の CryptoKey として扱う）
//   鍵の保管: PBKDF2-HMAC-SHA256（60万回）でパスワードから作った鍵でデータ鍵を包む
//   暗号文:   base64(nonce 12B + 暗号文 + 認証タグ)。AAD にユーザー ID と日付を入れる
const E2EE = (() => {
  const enc = new TextEncoder(), dec = new TextDecoder();
  const KDF_ITERATIONS = 600000;

  const b64e = bytes => {
    let s = '';
    const u = new Uint8Array(bytes);
    for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode.apply(null, u.subarray(i, i + 0x8000));
    return btoa(s);
  };
  const b64d = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));

  const aadKey = uid => enc.encode(`wm:${uid}:key`);
  const aadDay = (uid, day) => enc.encode(`wm:${uid}:day:${day}`);
  const aadSettings = uid => enc.encode(`wm:${uid}:settings`);

  async function deriveKek(password, salt, iterations) {
    const base = await crypto.subtle.importKey('raw', enc.encode(password), 'PBKDF2', false, ['deriveKey']);
    return crypto.subtle.deriveKey({ name: 'PBKDF2', salt, iterations, hash: 'SHA-256' },
      base, { name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt']);
  }

  async function encryptBytes(key, bytes, aad) {
    const iv = crypto.getRandomValues(new Uint8Array(12));   // 毎回ランダム
    const ct = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv, additionalData: aad }, key, bytes));
    const out = new Uint8Array(iv.length + ct.length);
    out.set(iv); out.set(ct, iv.length);
    return b64e(out);
  }

  async function decryptBytes(key, token, aad) {
    const raw = b64d(token);
    try {
      return new Uint8Array(await crypto.subtle.decrypt(
        { name: 'AES-GCM', iv: raw.slice(0, 12), additionalData: aad }, key, raw.slice(12)));
    } catch (e) {
      throw new Error('復号できませんでした（鍵が違うか、データが改ざんされています）');
    }
  }

  // データ鍵は取り出し不可（extractable: false）で読み込む
  const importDek = raw => crypto.subtle.importKey('raw', raw, { name: 'AES-GCM' }, false, ['encrypt', 'decrypt']);

  async function newVault(password, uid) {
    const raw = crypto.getRandomValues(new Uint8Array(32));
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const kek = await deriveKek(password, salt, KDF_ITERATIONS);
    const vault = { kdf_salt: b64e(salt), kdf_iterations: KDF_ITERATIONS, wrapped_key: await encryptBytes(kek, raw, aadKey(uid)) };
    const dek = await importDek(raw);
    raw.fill(0);
    return { vault, dek };
  }

  async function unwrap(password, uid, vault) {
    const kek = await deriveKek(password, b64d(vault.kdf_salt), vault.kdf_iterations);
    const raw = await decryptBytes(kek, vault.wrapped_key, aadKey(uid));
    if (raw.length !== 32) throw new Error('鍵の形式が正しくありません');
    const dek = await importDek(raw);
    raw.fill(0);
    return dek;
  }

  const encryptJson = async (key, obj, aad) => encryptBytes(key, enc.encode(JSON.stringify(obj)), aad);
  const decryptJson = async (key, token, aad) => JSON.parse(dec.decode(await decryptBytes(key, token, aad)));

  // ---- この端末に鍵を記憶（取り出し不可の CryptoKey のまま IndexedDB に保存）----
  function db() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open('workmonitor', 1);
      req.onupgradeneeded = () => req.result.createObjectStore('keys');
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }
  async function store(mode, fn) {
    const d = await db();
    return new Promise((resolve, reject) => {
      const tx = d.transaction('keys', mode);
      const req = fn(tx.objectStore('keys'));
      tx.oncomplete = () => resolve(req && req.result);
      tx.onerror = () => reject(tx.error);
    });
  }
  const saveKey = (uid, key) => store('readwrite', s => s.put(key, uid)).catch(() => {});
  const loadKey = uid => store('readonly', s => s.get(uid)).catch(() => null);
  const deleteKey = uid => store('readwrite', s => s.delete(uid)).catch(() => {});

  return { aadDay, aadSettings, newVault, unwrap, encryptJson, decryptJson, saveKey, loadKey, deleteKey };
})();

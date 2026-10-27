// トップページ: ダウンロードのリンクと、最新版の番号・サイズの表示
document.getElementById('dl-installer').href = WM.downloads.installer;
document.getElementById('dl-zip').href = WM.downloads.zip;
fetch(`https://api.github.com/repos/${WM.repo}/releases/latest`)
  .then(r => r.ok ? r.json() : Promise.reject())
  .then(rel => {
    const date = new Date(rel.published_at).toLocaleDateString('ja-JP');
    document.getElementById('version-meta').textContent =
      `最新版 ${rel.tag_name}（${date}）・Windows 10 / 11 対応・オープンソース（MIT）`;
    const mb = n => `${(n / 1024 / 1024).toFixed(1)} MB`;
    for (const a of rel.assets || []) {
      if (a.name === 'WorkMonitor-Setup.exe') document.getElementById('size-installer').textContent = `${rel.tag_name} ・ ${mb(a.size)}`;
      if (a.name === 'WorkMonitor.zip') document.getElementById('size-zip').textContent = `${rel.tag_name} ・ ${mb(a.size)}`;
    }
  })
  .catch(() => { /* 取得できなくてもダウンロードはできる */ });

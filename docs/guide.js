// 使い方ガイド: 目次（広い画面では開いたまま）と、いま読んでいる場所の強調
(function () {
  const details = document.getElementById('toc-details');
  const wide = matchMedia('(min-width: 901px)');
  const sync = () => { details.open = wide.matches; };
  sync();
  wide.addEventListener('change', sync);

  const links = [...document.querySelectorAll('#toc a')];
  const byId = Object.fromEntries(links.map(a => [a.getAttribute('href').slice(1), a]));
  const sections = links.map(a => document.getElementById(a.getAttribute('href').slice(1))).filter(Boolean);

  // スマホでは目次のリンクを押したら閉じる
  links.forEach(a => a.addEventListener('click', () => { if (!wide.matches) details.open = false; }));

  // 画面の上の方にある見出しの項目を強調する
  function update() {
    let current = sections[0];
    for (const s of sections) {
      if (s.getBoundingClientRect().top <= 120) current = s;
    }
    // いちばん下までスクロールしたら、最後の項目（短くて上まで来ないため）
    if (innerHeight + scrollY >= document.documentElement.scrollHeight - 4) current = sections[sections.length - 1];
    links.forEach(a => a.classList.remove('on'));
    const a = current && byId[current.id];
    if (a) {
      a.classList.add('on');
      if (wide.matches) {
        const toc = document.querySelector('.toc');
        const r = a.getBoundingClientRect(), t = toc.getBoundingClientRect();
        if (r.top < t.top || r.bottom > t.bottom) a.scrollIntoView({ block: 'nearest' });
      }
    }
  }
  let timer = null;
  addEventListener('scroll', () => {
    if (!timer) timer = setTimeout(() => { timer = null; update(); }, 60);
  }, { passive: true });
  update();
})();

(() => {
  const styleId = 'temo-shared-bottom-nav-style';
  if (!document.getElementById(styleId)) {
    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
      body { padding-bottom: calc(92px + env(safe-area-inset-bottom)) !important; }
      .bottom-nav {
        position: fixed !important; left: 0 !important; right: 0 !important;
        bottom: 0 !important; z-index: 2147483000 !important;
        display: grid !important; grid-template-columns: repeat(5, minmax(0, 1fr)) !important;
        gap: 6px !important; padding: 9px 10px calc(9px + env(safe-area-inset-bottom)) !important;
        background: rgba(255,255,255,.97) !important; border-top: 1px solid #d5e5ef !important;
        box-shadow: 0 -5px 18px #173e5512 !important; backdrop-filter: blur(12px) !important;
        box-sizing: border-box !important;
      }
      .bottom-nav a, .bottom-nav button {
        min-width: 0 !important; min-height: 62px !important; border: 1px solid #d9e7f0 !important;
        border-radius: 22px !important; background: #f0f5fb !important; color: #38556a !important;
        display: flex !important; align-items: center !important; justify-content: center !important;
        flex-direction: column !important; gap: 3px !important; text-decoration: none !important;
        font: inherit !important; font-weight: 700 !important; cursor: pointer !important;
        box-sizing: border-box !important;
      }
      .bottom-nav .home { background: #e4f5fc !important; border-color: #2783b6 !important; color: #236b98 !important; }
      .bottom-nav .nav-number { font-size: 29px !important; line-height: 1.1 !important; }
      .bottom-nav .nav-label { font-size: 13px !important; line-height: 1.1 !important; }
    `;
    document.head.appendChild(style);
  }
  let nav = document.querySelector('.bottom-nav');
  if (!nav) {
    const scriptUrl = document.currentScript && document.currentScript.src;
    const homeUrl = scriptUrl ? new URL('./', scriptUrl).href : './';
    nav = document.createElement('nav');
    nav.className = 'bottom-nav';
    nav.setAttribute('aria-label', 'მთავარი ნავიგაცია');
    nav.innerHTML = '<a class="home" href="' + homeUrl + '" aria-label="მთავარი"><span style="font-size:19px;line-height:1">⌂</span><span class="nav-label">მთავარი</span></a>' +
      [2,3,4,5].map(n => '<button type="button" aria-label="გვერდი ' + n + ', მომავალში დაემატება"><span class="nav-number">' + n + '</span></button>').join('');
    document.body.appendChild(nav);
  }
  // Keep the shared bar outside page containers so transforms/scrolling on any page cannot move it.
  if (nav.parentElement !== document.documentElement) {
    document.documentElement.appendChild(nav);
  }
})();
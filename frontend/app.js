/* ============================================================
   Boche — app.js
   Super-app shell: member app + Business Admin module.
   UI only — every data value is read from data.js (BC_* objects).
   ============================================================ */
(function () {
  'use strict';

  /* ---------- State ----------
     Shared data (members, points, vouchers…) lives in localStorage so the member app and
     the Business Admin module, even in two tabs, see the same world.
     Session (who is signed in on THIS tab) lives in sessionStorage. */
  var LS_KEY = 'bocheclub-shared-v4', SS_KEY = 'bocheclub-session-v4', DEV_KEY = 'bocheclub-device';
  /* One-time clean start: drop the old saved orders, draw entries, claims and profile edits */
  try { localStorage.removeItem('bocheclub-shared-v3'); sessionStorage.removeItem('bocheclub-session-v3'); } catch (e) {}

  function freshShared() {
    var members = {};
    BC_MEMBERS.forEach(function (m) {
      /* Age (Aadhaar) check is optional: the signed-in demo member starts unverified */
      members[m.id] = JSON.parse(JSON.stringify({ points: m.points, spend: m.spend, vouchers: m.vouchers, checkins: m.checkins, history: m.history, kyc: m === BC_MEMBER ? null : m.kyc }));
    });
    return { members: members, activated: [], reserved: [], bookings: [], notif: { offers: true, events: true, points: true, sound: true }, staffLog: [] };
  }
  function readJSON(store, key) { try { var j = store.getItem(key); return j ? JSON.parse(j) : null; } catch (e) { return null; } }
  function save() { try { localStorage.setItem(LS_KEY, JSON.stringify(S)); } catch (e) {} }
  function saveSes() { try { sessionStorage.setItem(SS_KEY, JSON.stringify(SES)); } catch (e) {} }
  var S = readJSON(localStorage, LS_KEY) || freshShared();
  if (S.notif.sound === undefined) S.notif.sound = true;
  Object.keys(S.members).forEach(function (k) {
    var m = S.members[k];
    if (m.address && !m.addresses) { m.addresses = [{ id: 'A1', label: 'Home', addr: m.address.addr, area: m.address.area }]; m.defaultAddr = 'A1'; delete m.address; }
  });
  /* Older orders carried one card with one number; now an order carries one card per pack */
  Object.keys(S.members).forEach(function (k) {
    (S.members[k].teaOrders || []).forEach(function (o) {
      if (o.card && !o.cards) { o.cards = [{ id: o.id + '-1', pack: '', nos: [o.card.no], scratched: o.card.scratched, submitted: o.card.submitted, drawDate: o.card.drawDate }]; delete o.card; }
    });
  });
  var SES = readJSON(sessionStorage, SS_KEY) || { authed: false, pending: null, staffId: null, outlet: null };

  var ui = {
    mobile: '', staffMobile: '', kycBack: 'profile', kyc: { no: '', consent: false, step: 'no' }, ob: { name: '', email: '' }, dev: null,
    exploreFilter: 'all', actTab: 'points', actBiz: 'all', offersTab: 'offers',
    book: null, billAmt: '', sheetLock: false,
    pinCache: {}, addrEd: null, em: null, grv: { biz: null, text: '', files: [], focusText: false }, grvJustSent: null,
    tea: { qty: teaBlankBag(), addr: { pin: '', name: '', house: '', street: '' }, area: null, look: 'idle', err: '', focusNext: false }
  };
  /* Name, email and mobile the member gave at onboarding override the seed profile */
  var BASE = { name: BC_MEMBER.name, firstName: BC_MEMBER.firstName, email: BC_MEMBER.email, mobile: BC_MEMBER.mobile };
  /* The signed-in Google account (from /api/me); when present it is the member's real name and email */
  var ME = null, BOOT = { googleClientId: '' };
  function applyProfile() {
    var p = S.members[BC_MEMBER.id].profile;
    BC_MEMBER.name = p ? p.name : BASE.name; BC_MEMBER.firstName = p ? p.name.split(' ')[0] : BASE.firstName;
    BC_MEMBER.email = p ? p.email : BASE.email; BC_MEMBER.mobile = p && p.mobile ? p.mobile : BASE.mobile;
    if (ME) { BC_MEMBER.name = ME.name; BC_MEMBER.firstName = ME.firstName; BC_MEMBER.email = ME.email; if (ME.mobile) BC_MEMBER.mobile = ME.mobile; }
  }
  applyProfile();
  function teaBlankBag() { var q = {}; BC_TEA.packs.forEach(function (p) { q[p.id] = 0; }); return q; }
  function resetBook() { ui.book = { day: 0, time: null, guests: 2, occasion: BC_BOOKING.occasions[0], note: '' }; }
  resetBook();

  /* ---------- Helpers ---------- */
  function $(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function num(n) { var p = Math.round(n * 100) % 100 !== 0; return (p ? Math.round(n * 100) / 100 : Math.round(n)).toLocaleString('en-IN', p ? { minimumFractionDigits: 2, maximumFractionDigits: 2 } : {}); }
  function inr(n) { return '₹' + num(n); }
  function byId(arr, id) { for (var i = 0; i < arr.length; i++) if (arr[i].id === id) return arr[i]; return null; }
  function biz(id) { return byId(BC_BUSINESSES, id); }
  function outlet(id) { return byId(BC_OUTLETS, id); }
  function liveBiz() { return BC_BUSINESSES.filter(function (b) { return b.live; }); }
  function soonBiz() { return BC_BUSINESSES.filter(function (b) { return !b.live; }); }
  function memberOf(id) { return byId(BC_MEMBERS, id); }
  function dyn(id) { return S.members[id]; }
  function ageOf(dob) {
    var d = new Date(dob), n = new Date(), a = n.getFullYear() - d.getFullYear(), m = n.getMonth() - d.getMonth();
    if (m < 0 || (m === 0 && n.getDate() < d.getDate())) a--;
    return a;
  }
  function totalSpend(id) { var s = dyn(id).spend, t = 0; for (var k in s) t += s[k]; return t; }
  function tierBySpend(sp) { var t = BC_TIERS[0]; BC_TIERS.forEach(function (x) { if (sp >= x.minSpend) t = x; }); return t; }
  function tierOfMember(id) { return tierBySpend(totalSpend(id)); }
  function nextTier(t) { return BC_TIERS[BC_TIERS.indexOf(t) + 1] || null; }
  function curTier() { return tierOfMember(BC_MEMBER.id); }
  function pointsOf(id, bizId) { return dyn(id).points[bizId] || 0; }
  /* Age check happens only where the law needs it (ageGate outlets), the first time it's needed.
     'open' no rule · 'verify' rule but not yet verified · 'ok' meets it · 'under' too young */
  function kycOf(id) { return dyn(id || BC_MEMBER.id).kyc; }
  function ageState(o, id) {
    if (!o.ageGate) return 'open';
    if (!kycOf(id)) return 'verify';
    return ageOf(memberOf(id || BC_MEMBER.id).dob) >= BC_STATES[o.state].drinkingAge ? 'ok' : 'under';
  }
  function eligible(o, id) { var st = ageState(o, id); return st === 'open' || st === 'ok'; }
  function verifyRoute(back) { return 'kyc/' + encodeURIComponent(back); }
  /* Member photo: their own upload, else the supplied member picture (the Boche portrait is brand art, never a member photo) */
  function memberPhoto() { var p = (S.members[BC_MEMBER.id] || {}).profile || {}; return p.photo || '/img/member.webp'; }
  function avatarHtml() { var ph = memberPhoto(); return ph ? '<div class="avatar has-photo"><img src="' + esc(ph) + '" alt=""></div>' : '<div class="avatar">' + initials(BC_MEMBER.name) + '</div>'; }
  function photoTag(cls, brandImg) {
    var ph = brandImg || memberPhoto();
    return ph ? '<img class="' + cls + '" src="' + esc(ph) + '" alt="" decoding="async">' : '<span class="' + cls + ' ph">' + initials(BC_MEMBER.name) + '</span>';
  }
  function initials(name) { return name.split(' ').map(function (w) { return w[0]; }).join('').slice(0, 2).toUpperCase(); }
  function greeting() { var h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening'; }
  function todayLabel() { return new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }); }
  function timeLabel() { return new Date().toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' }); }
  function rand(n) { var s = ''; for (var i = 0; i < n; i++) s += 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'[Math.floor(Math.random() * 32)]; return s; }
  function outletsLabel(o) {
    var b = biz(o.biz);
    return o.outlets === 'all' ? 'All ' + b.name + ' outlets' : o.outlets.map(function (id) { return outlet(id).city; }).filter(function (c, i, a) { return a.indexOf(c) === i; }).join(' · ');
  }
  function addHistory(id, bizId, title, ref, pts) { dyn(id).history.unshift({ biz: bizId, date: todayLabel(), title: title, ref: ref, pts: pts }); }
  function isStandalone() { return (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches) || navigator.standalone === true; }
  function isIOS() { return /iphone|ipad|ipod/i.test(navigator.userAgent); }
  function staff() { return byId(BC_STAFF, SES.staffId); }
  function staffOutlet() { var st = staff(); return outlet(SES.outlet && st.outlets.indexOf(SES.outlet) > -1 ? SES.outlet : st.outlets[0]); }
  function earnFor(bizId, tierId, amount) { return Math.floor(amount / 100) * biz(bizId).earn[tierId]; }

  /* ---------- Icons ---------- */
  var ICONS = {
    home: '<path d="M3 9.5l9-7 9 7V20a2 2 0 0 1-2 2h-4v-7H9v7H5a2 2 0 0 1-2-2z"/>',
    card: '<rect x="2" y="5" width="20" height="14" rx="2.5"/><line x1="2" y1="10" x2="22" y2="10"/><line x1="6" y1="15" x2="10" y2="15"/>',
    qr: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><path d="M14 14h3v3h-3zM20 14v.01M14 20h.01M17 20h4v-3"/>',
    pin: '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0z"/><circle cx="12" cy="10" r="3"/>',
    gift: '<polyline points="20 12 20 22 4 22 4 12"/><rect x="2" y="7" width="20" height="5" rx="1"/><line x1="12" y1="22" x2="12" y2="7"/><path d="M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7zM12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z"/>',
    user: '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    back: '<polyline points="15 18 9 12 15 6"/>',
    chev: '<polyline points="9 18 15 12 9 6"/>',
    bell: '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/>',
    calendar: '<rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
    clock: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    users: '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8"/>',
    star: '<polygon points="12 2 15.1 8.3 22 9.3 17 14.1 18.2 21 12 17.8 5.8 21 7 14.1 2 9.3 8.9 8.3 12 2"/>',
    check: '<polyline points="20 6 9 17 4 12"/>',
    shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/>',
    phone: '<rect x="5" y="2" width="14" height="20" rx="2.5"/><line x1="12" y1="18" x2="12.01" y2="18"/>',
    crown: '<path d="M3 18h18M4 8l4 4 4-7 4 7 4-4-2 10H6z"/>',
    tag: '<path d="M20.6 13.4l-7.2 7.2a2 2 0 0 1-2.8 0L2 12V2h10l8.6 8.6a2 2 0 0 1 0 2.8z"/><line x1="7" y1="7" x2="7.01" y2="7"/>',
    receipt: '<path d="M4 2v20l3-2 3 2 3-2 3 2 3-2 1 .7V2l-1 .7-3-2-3 2-3-2-3 2-3-2z"/><line x1="8" y1="8" x2="16" y2="8"/><line x1="8" y1="12" x2="16" y2="12"/><line x1="8" y1="16" x2="12" y2="16"/>',
    download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
    logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>',
    more: '<circle cx="12" cy="5" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="12" cy="19" r="1.6"/>',
    sparkle: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M19 17l.7 1.8 1.8.7-1.8.7L19 22l-.7-1.8-1.8-.7 1.8-.7z"/>',
    leaf: '<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.5 19 2c1 2 2 4.2 2 8 0 5.5-4.8 10-10 10z"/><path d="M2 21c0-3 1.9-5.4 5.1-6C9.5 14.5 12 13 13 12"/>',
    gem: '<path d="M6 3h12l4 6-10 13L2 9z"/><path d="M2 9h20M12 22L8 9l4-6 4 6z"/>',
    plus: '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
    minus: '<line x1="5" y1="12" x2="19" y2="12"/>',
    x: '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
    music: '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
    wallet: '<path d="M20 7H5a2 2 0 0 1 0-4h13v4"/><path d="M3 5v14a2 2 0 0 0 2 2h15V7"/><circle cx="16" cy="14" r="1"/>',
    lock: '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    chat: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    clip: '<path d="M21.4 11.1l-9.2 9.2a6 6 0 0 1-8.5-8.5l9.2-9.2a4 4 0 0 1 5.7 5.7l-9.2 9.2a2 2 0 0 1-2.8-2.8l8.5-8.5"/>',
    headset: '<path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/>',
    help: '<circle cx="12" cy="12" r="10"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
    share: '<path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/><polyline points="16 6 12 2 8 6"/><line x1="12" y1="2" x2="12" y2="15"/>',
    refresh: '<polyline points="23 4 23 10 17 10"/><path d="M20.5 15a9 9 0 1 1-2.1-9.4L23 10"/>',
    doc: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>',
    beer: '<rect x="5" y="9" width="11" height="12" rx="1.5"/><path d="M16 11h2.5a2 2 0 0 1 2 2v3.5a2 2 0 0 1-2 2H16"/><path d="M5 9c-1.8 0-2.6-2.1-1.3-3.3C4.4 4.8 5.8 4.9 6.5 5.5 7.2 3.7 10 3.3 11 5c1-.9 3.3-.5 3.7 1 1.3.2 2 1.7 1.3 3"/><path d="M8.5 13v5M12 13v5"/>',
    mountain: '<path d="M2.5 19.5L9.5 6.5l4.5 7.5 2.5-3.5 5 9z"/>',
    bed: '<path d="M2 19V6M2 15h20v4M22 15v-2a3 3 0 0 0-3-3h-7v5"/><circle cx="7" cy="11" r="2"/>',
    scan: '<path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2"/><line x1="7" y1="12" x2="17" y2="12"/>',
    open: '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>'
  };
  function ic(n, s) {
    return '<svg class="ic" width="' + (s || 22) + '" height="' + (s || 22) + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + ICONS[n] + '</svg>';
  }
  function icInline(n, s) { return ic(n, s).replace('class="ic"', 'class="ic" style="display:inline;vertical-align:-3px"'); }

  /* ---------- Shared fragments ---------- */
  /* Every inner page: back on the left; on the right a ⋮ menu with options that suit the page, and the member's avatar (name, tier, quick links) */
  var HELP = ['support', 'headset', 'Help & support'], SHOP = ['tea', 'leaf', 'Shop tea'], ORDERS = ['tea-orders', 'receipt', 'My orders'], NUMS = ['my-numbers', 'gift', 'My lucky numbers'], WINS = ['my-wins', 'crown', 'My wins'],
    DRAW = ['draw', 'crown', 'Lucky Draw'], OFFERS = ['offers', 'tag', 'Offers & events'], TIERS = ['tiers', 'crown', 'Membership tiers'], VENUES = ['explore', 'pin', 'All venues'], ADDRS = ['addresses', 'pin', 'Delivery addresses'], ACT = ['activity', 'receipt', 'Activity'];
  var LUCKY = [DRAW, NUMS, WINS, ORDERS, SHOP, HELP];
  var PAGE_MENU = {
    tea: LUCKY, 'tea-orders': LUCKY, 'my-numbers': LUCKY, draw: LUCKY, 'my-wins': LUCKY,
    'tea-address': [ORDERS, HELP], 'tea-pay': [ORDERS, HELP], addresses: [ORDERS, HELP], address: [ORDERS, HELP],
    explore: [OFFERS, TIERS, HELP], card: [TIERS, OFFERS, HELP], biz: [OFFERS, VENUES, TIERS, HELP], outlet: [OFFERS, VENUES, HELP], book: [VENUES, HELP],
    support: [['grievance', 'clip', 'Raise a complaint'], ['card', 'card', 'My card'], ACT], grievance: [HELP, ACT], ticket: [HELP, ACT],
    activity: [TIERS, DRAW, HELP], tiers: [OFFERS, ACT, HELP], offers: [TIERS, DRAW, VENUES], profile: [HELP, TIERS, ADDRS, DRAW]
  };
  function avatarMini() { var ph = memberPhoto(); return ph ? '<img src="' + esc(ph) + '" alt="">' : '<span>' + initials(BC_MEMBER.name) + '</span>'; }
  function menuItem(m) { return '<button role="menuitem" data-go="' + m[0] + '">' + ic(m[1], 16) + m[2] + '</button>'; }
  function topbarMenu(name) {
    var items = (PAGE_MENU[name] || []).filter(function (m) { return m[0] !== name; }), open = ui.pageMenu, bd = '<div class="kmenu-bd" data-act="pageMenu" data-id=""></div>';
    var kebab = '<button class="iconbtn" data-act="pageMenu" data-id="more" aria-label="More options" aria-haspopup="menu" aria-expanded="' + (open === 'more') + '">' + ic('more', 20) + '</button>';
    var av = name === 'profile' ? '' : '<button class="tb-av" data-act="pageMenu" data-id="user" aria-label="Account" aria-haspopup="menu" aria-expanded="' + (open === 'user') + '">' + avatarMini() + '</button>';
    var menu = '';
    if (open === 'more') menu = bd + '<div class="kmenu" role="menu">' + items.map(menuItem).join('') + '</div>';
    else if (open === 'user' && av) menu = bd + '<div class="kmenu kuser" role="menu"><div class="ku-h"><span class="tb-av ku-av">' + avatarMini() + '</span><div><b>' + esc(BC_MEMBER.name) + '</b><small>' + esc(curTier().name) + ' member · ' + esc(BC_MEMBER.id) + '</small></div></div>' +
      [['profile', 'user', 'My profile'], ['card', 'card', 'My card'], TIERS].map(menuItem).join('') + '<button role="menuitem" class="ku-out" data-act="logout">' + ic('logout', 16) + 'Log out</button></div>';
    return '<div class="tb-r">' + kebab + av + '</div>' + menu;
  }
  function topbar(title, parent, right) {
    var name = parse().name;
    return '<header class="topbar">' +
      (parent ? '<button class="iconbtn" data-act="back" data-id="' + parent + '" aria-label="Back">' + ic('back') + '</button>' : '') +
      '<h2>' + esc(title) + '</h2>' + (right || (title && SES.authed && PAGE_MENU[name] ? topbarMenu(name) : '')) + '</header>';
  }
  function brandMark() { return 'BOCHE'; }
  function cardFront(tierId, extraCls, bare, brandImg) {
    var t = byId(BC_TIERS, tierId || curTier().id);
    return '<div class="mcard t-' + t.id + (bare ? ' bare ' : ' ') + (extraCls || '') + '">' +
      '<div class="mc-top"><div class="mc-brand">' + brandMark() + '</div><span class="mc-tier">' + esc(t.name) + '</span></div>' +
      '<div class="mc-chip"></div>' + photoTag('mc-photo', brandImg) +
      '<div class="mc-num">' + esc(BC_MEMBER.cardNo) + '</div>' +
      '<div class="mc-bottom"><div><div class="mc-label">Member</div><div class="mc-val">' + esc(BC_MEMBER.name) + '</div></div>' +
      '<div class="mc-right"><div class="mc-label">Valid thru</div><div class="mc-val">' + esc(BC_MEMBER.validThru) + '</div></div></div>' +
      '</div>';
  }
  function cardBack() {
    var C = 2 * Math.PI * 11;
    return '<div class="mcard mback">' +
      '<div class="mb-left"><div class="qrbox"><div id="qrSvg"></div><span class="qr-logo"><img src="/img/portrait.webp" alt=""></span></div>' +
      '<div class="mb-idrow"><span class="mc-label">Member ID</span><b class="mb-id">' + esc(BC_MEMBER.id) + '</b></div></div>' +
      '<div class="mb-right">' + photoTag('mb-photo') + '<div class="mb-name">' + esc(BC_MEMBER.name) + '</div>' +
      '<div class="mb-row"><span class="mb-tier">' + esc(curTier().name) + ' member</span>' +
      '<span class="mb-timer"><svg class="ring" viewBox="0 0 26 26"><circle class="bg" cx="13" cy="13" r="11"/><circle class="fg" id="qrRing" cx="13" cy="13" r="11" stroke-dasharray="' + C + '" stroke-dashoffset="0"/></svg><span><span id="qrCount">30</span>s</span></span></div>' +
      '</div></div>';
  }
  function eventRow(e) {
    var d = new Date(e.date + 'T00:00:00'), o = outlet(e.outlet);
    return '<button class="event-row" data-go="outlet/' + e.outlet + '">' +
      '<div class="datebox"><b>' + d.getDate() + '</b><span>' + d.toLocaleDateString('en-GB', { month: 'short' }) + '</span></div>' +
      '<div class="li-main"><div class="li-t">' + esc(e.title) + '</div><div class="li-s">' + esc(o.name) + ' · ' + esc(e.time) + '</div>' +
      '<div class="li-s gold-text">' + esc(e.price) + '</div></div>' +
      '<span class="li-chev">' + ic('chev', 18) + '</span></button>';
  }
  function offerCard(o) {
    var on = S.activated.indexOf(o.id) > -1, allowed = o.tiers.indexOf(curTier().id) > -1, b = biz(o.biz);
    var lockTier = byId(BC_TIERS, o.tiers[0]).name;
    return '<div class="surface offer"><div class="chips"><span class="badge">' + esc(o.kind) + '</span><span class="badge plain">' + esc(b.name) + '</span></div>' +
      '<h4>' + esc(o.title) + '</h4><p>' + esc(o.desc) + '</p>' +
      '<div class="offer-foot"><div class="offer-meta">' + esc(outletsLabel(o)) + '<br>' + esc(o.valid) + '</div>' +
      (allowed ? '<button class="btn btn-sm ' + (on ? 'btn-soft' : 'btn-gold') + '" data-act="activate" data-id="' + o.id + '">' + (on ? ic('check', 16) + 'Activated' : 'Activate') + '</button>'
        : '<a class="btn btn-sm btn-line" href="/tiers">' + ic('lock', 15) + esc(lockTier) + ' & above</a>') + '</div></div>';
  }
  function outletCard(o) {
    var under = ageState(o) === 'under', b = biz(o.biz), offers = BC_OFFERS.filter(function (x) { return x.outlets !== 'all' && x.outlets.indexOf(o.id) > -1; });
    return '<div class="surface pubcard" data-go="outlet/' + o.id + '">' +
      '<div class="pub-hero tone-' + o.tone + '">' + (o.logo ? '<span class="pub-logo"><img src="' + esc(o.logo) + '" alt=""></span>' : '') + '<span class="pub-city">' + esc(o.city) + '</span><span class="pub-rating">' + ic('star', 12) + o.rating + '</span></div>' +
      '<div class="pub-body"><div class="pub-name">' + esc(o.name) + '</div>' +
      '<div class="pub-area">' + ic('pin', 13) + esc(o.area) + ' · ' + esc(o.distance) + '</div>' +
      '<div class="pub-tags"><span class="badge plain">' + ic(b.icon, 12) + esc(o.kind) + '</span>' +
      (o.ageGate ? '<span class="badge plain">' + BC_STATES[o.state].drinkingAge + '+</span>' : '') +
      o.tags.map(function (t) { return '<span class="badge">' + esc(t) + '</span>'; }).join('') + '</div>' +
      (offers.length ? '<div class="pub-offer">' + ic('tag', 15) + esc(offers[0].title) + '</div>' : '') +
      '</div>' + (!under ? '' : '<div class="pub-lock">' + ic('lock', 20) + 'Available from age ' + BC_STATES[o.state].drinkingAge + '</div>') + '</div>';
  }
  function otpBoxes(n) { var s = ''; for (var i = 0; i < (n || BC_BRAND.otpLength); i++) s += '<input inputmode="numeric" maxlength="1"' + (i ? '' : ' autocomplete="one-time-code"') + ' aria-label="Digit ' + (i + 1) + '">'; return s; }

  /* ============================================================
     MEMBER SCREENS
     ============================================================ */
  var SCREENS = {}, AFTER = {};

  SCREENS.welcome = function () {
    return '<div class="welcome">' +
      '<div class="wl-hero"><div class="wl-mark">BOCHE</div>' +
      '<div class="wl-cards">' + cardFront('gold', '', false, '/img/portrait.webp') + '</div>' +
      '<p class="wl-tag">One card. Every Boche experience.</p>' +
      '<div class="wl-perks"><span>' + ic('sparkle', 13) + 'Rewards</span><span>' + ic('gift', 13) + 'Offers</span><span>' + ic('users', 13) + 'Events</span></div></div>' +
      '<div class="wl-sheet"><h1>Welcome</h1>' +
      '<p class="wl-sub">Sign in or join with your Google account</p>' +
      '<div class="gsi-slot" id="gsiBtn"><span class="mini-spin" aria-label="Loading Google sign-in"></span></div>' +
      '<div class="err-text" id="mobErr">' + esc(ui.signInErr || '') + '</div>' +
      '<p class="wl-legal"><a class="link" href="/staff">Admin login</a> · <a class="link" href="/verify-draw">Verify past draws</a></p></div></div>';
  };
  SCREENS.login = SCREENS.welcome;
  function wireMobile(inpId, btnId, errId, onEnter, noFocus) {
    var inp = $(inpId), btn = $(btnId);
    function check() {
      inp.value = inp.value.replace(/\D/g, '').slice(0, 10);
      btn.disabled = !/^[6-9]\d{9}$/.test(inp.value);
      $(errId).textContent = inp.value.length === 10 && btn.disabled ? 'Enter a valid Indian mobile number' : '';
      return inp.value;
    }
    inp.addEventListener('input', function () { var v = check(); if (inpId === 'mobile') ui.mobile = v; else ui.staffMobile = v; });
    inp.addEventListener('keydown', function (e) { if (e.key === 'Enter' && !btn.disabled) onEnter(); });
    check(); if (!noFocus) inp.focus();
  }
  /* Sign in with Google (Google Identity Services). The button is Google's own, as its branding rules
     require; the server checks the ID token and sets an httpOnly session cookie. */
  AFTER.welcome = AFTER.login = function () { mountGoogleButton('gsiBtn', 'mobErr', onGoogleCredential); };
  /* Renders Google's button into a slot once the GIS library and the client ID are ready */
  function mountGoogleButton(slotId, errId, onCredential) {
    var tries = 0;
    function ready() {
      var slot = $(slotId);
      if (!slot) return true;
      var gid = window.google && window.google.accounts && window.google.accounts.id;
      if (!gid || !BOOT.googleClientId) return false;
      gid.initialize({ client_id: BOOT.googleClientId, callback: onCredential, ux_mode: 'popup', auto_select: false, cancel_on_tap_outside: true });
      /* Google draws a stand-in button, then swaps in its own frame. Render it hidden behind the spinner and
         fade it in once that frame has loaded, so the swap is never seen. */
      slot.classList.remove('ready');
      slot.innerHTML = '<span class="mini-spin" aria-label="Loading Google sign-in"></span><div class="gsi-btn"></div>';
      var holder = slot.querySelector('.gsi-btn'), shown = false;
      function show() { if (shown) return; shown = true; slot.classList.add('ready'); }
      gid.renderButton(holder, { type: 'standard', theme: 'outline', size: 'large', shape: 'pill', text: 'continue_with', logo_alignment: 'center', width: Math.min(400, slot.clientWidth || 320) });
      var waited = 0, look = setInterval(function () {   /* Google may add its frame a moment later */
        var f = holder.querySelector('iframe');
        if (f) { clearInterval(look); f.addEventListener('load', function () { timers.push(setTimeout(show, 150)); }); }
        else if ((waited += 50) >= 1500) { clearInterval(look); show(); }
      }, 50);
      timers.push(look, setTimeout(show, 3000));   /* never leave the button hidden */
      return true;
    }
    if (ready()) return;
    var t = setInterval(function () {
      if (ready()) { clearInterval(t); return; }
      if (++tries > 80) { clearInterval(t); var e = $(errId); if (e) e.textContent = BOOT.googleClientId ? 'Google sign-in could not load. Check your connection and reload.' : 'Sign-in is not available right now. Please try again later.'; }
    }, 100);
    timers.push(t);
  }
  function onGoogleCredential(resp) {
    var slot = $('gsiBtn'); if (slot) slot.innerHTML = '<span class="mini-spin" aria-label="Signing in"></span>';
    ui.signInErr = '';
    BCAPI.post('/auth/google', { credential: resp.credential }).then(function (u) {
      ME = u; applyProfile(); SES.authed = true; SES.pending = null; saveSes(); refreshOrders(true);
      go('home'); toast('Welcome, ' + BC_MEMBER.firstName);
    }).catch(function (e) {
      ui.signInErr = e.status === 503 ? 'Google sign-in is unavailable right now. Please try again.' : 'Sign-in failed. Please try again.';
      rerender();
    });
  }

  function wireOtp(onFull) {
    var wrap = $('otp'), ins = wrap.querySelectorAll('input'), btn = wrap.parentNode.querySelector('[data-otp-btn]');
    function code() { return Array.prototype.map.call(ins, function (x) { return x.value; }).join(''); }
    Array.prototype.forEach.call(ins, function (inp, i) {
      inp.addEventListener('input', function () {
        var v = inp.value.replace(/\D/g, '');
        if (v.length > 1) { v.split('').slice(0, ins.length).forEach(function (ch, k) { if (ins[k]) ins[k].value = ch; }); ins[Math.min(ins.length - 1, v.length - 1)].focus(); }
        else { inp.value = v; if (v && ins[i + 1]) ins[i + 1].focus(); }
        wrap.classList.remove('bad'); $('otpErr').textContent = '';
        btn.disabled = code().length !== ins.length;
        if (code().length === ins.length) onFull(code());
      });
      inp.addEventListener('keydown', function (e) { if (e.key === 'Backspace' && !inp.value && ins[i - 1]) ins[i - 1].focus(); });
    });
    ins[0].focus();
    var left = 30;
    function tick() {
      var r = $('resend'); if (!r) return;
      if (left > 0) { r.textContent = 'Resend OTP in ' + left + 's'; left--; }
      else r.innerHTML = '<a class="link" href="javascript:void(0)" data-act="resendOtp">Resend OTP</a>';
    }
    tick(); timers.push(setInterval(tick, 1000));
  }
  function otpFail() {
    var ins = $('otp').querySelectorAll('input');
    $('otp').classList.add('bad');
    Array.prototype.forEach.call(ins, function (x) { x.value = ''; }); ins[0].focus();
    $('otp').parentNode.querySelector('[data-otp-btn]').disabled = true;
  }
  function otpScreen(back, mobile, btnAct, extra) {
    return topbar('', back) + '<div class="auth"><h1>Verify OTP</h1>' +
      '<p class="lead">Sent to +91 ' + esc(mobile.replace(/(\d{5})(\d{5})/, '$1 $2')) + ' · <a class="link" href="/' + back + '">Change</a></p>' +
      '<div class="otp mt24" id="otp">' + otpBoxes() + '</div><div class="err-text" id="otpErr"></div>' +
      '<div class="demo-hint">Demo OTP: <b>' + esc(BC_BRAND.demoOtp) + '</b></div>' +
      (extra || '') +
      '<button class="btn btn-gold mt16" data-otp-btn data-act="' + btnAct + '" disabled>Verify & continue</button>' +
      '<p class="fine center mt16" id="resend"></p></div>';
  }
  SCREENS.otp = function () { return otpScreen('login', ui.mobile, 'verifyOtp'); };
  AFTER.otp = function () { if (!ui.mobile) { go('login'); return; } wireOtp(function () { ACTIONS.verifyOtp(); }); };

  /* ============================================================
     SIGN-IN & ONBOARDING
     OTP → SIM check (number must be in this phone) → new phone? email check → first time? name → welcome
     ============================================================ */
  function deviceId() {
    var id; try { id = localStorage.getItem(DEV_KEY); } catch (e) {}
    if (!id) { id = 'D' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8); try { localStorage.setItem(DEV_KEY, id); } catch (e) {} }
    return id;
  }
  function deviceLabel() {
    var u = navigator.userAgent;
    return /iphone/i.test(u) ? 'iPhone' : /ipad/i.test(u) ? 'iPad' : /android/i.test(u) ? 'Android phone' : /windows/i.test(u) ? 'Windows PC' : /mac/i.test(u) ? 'Mac' : 'Phone';
  }
  function myDevices() { var d = dyn(BC_MEMBER.id); return d.devices = d.devices || []; }
  function bindDevice() {
    var id = deviceId();
    if (!myDevices().some(function (x) { return x.id === id; })) { myDevices().push({ id: id, label: deviceLabel(), added: todayLabel() }); save(); }
  }
  function maskEmail(e) { var p = String(e).split('@'); return p[0].slice(0, 1) + '•••' + (p[0].length > 1 ? p[0].slice(-1) : '') + '@' + (p[1] || ''); }
  function fmtMobile(m) { return String(m).replace(/\D/g, '').replace(/(\d{5})(\d{5})/, '$1 $2'); }
  function setPending(step) { SES.pending = step; saveSes(); }
  function finishLogin() {
    bindDevice();
    if (!dyn(BC_MEMBER.id).profile) { setPending('name'); go('name'); return; }
    setPending(null); go('home'); toast('Welcome back, ' + BC_MEMBER.firstName);
  }
  function afterSim() {
    var known = myDevices().some(function (x) { return x.id === deviceId(); });
    if (myDevices().length && !known) { ui.dev = { sent: false }; setPending('device'); go('device'); }
    else finishLogin();
  }

  SCREENS.sim = function () {
    var m = fmtMobile(ui.mobile || BC_MEMBER.mobile);
    return '<div class="auth ob"><div class="ob-ic">' + ic('phone', 24) + '</div><h1>Verifying your SIM</h1>' +
      '<p class="lead">Your account works only on a phone with this number’s SIM.</p>' +
      '<ul class="steps ob-steps" id="simSteps">' + ['Reading the SIM in this phone', 'Matching +91 ' + m, 'SIM verified'].map(function (s) {
        return '<li><span class="st"></span>' + esc(s) + '</li>';
      }).join('') + '</ul></div>';
  };
  AFTER.sim = function () { runSteps($('simSteps').children, afterSim, 650); };

  SCREENS.device = function () {
    var last = myDevices()[myDevices().length - 1], p = dyn(BC_MEMBER.id).profile || {}, email = p.email || BC_MEMBER.email;
    return '<div class="auth ob"><div class="ob-ic warn">' + ic('shield', 24) + '</div><h1>New phone detected</h1>' +
      '<p class="lead">+91 ' + esc(fmtMobile(BC_MEMBER.mobile)) + ' is registered on ' + esc(last ? last.label : 'another phone') + '. Confirm it’s you with the code we email to <b>' + esc(maskEmail(email)) + '</b>.</p>' +
      (ui.dev && ui.dev.sent
        ? '<div class="otp mt16" id="otp">' + otpBoxes(BC_SECURITY.emailOtpLength) + '</div><div class="err-text" id="otpErr"></div>' +
          '<div class="demo-hint">Demo email code: <b>' + esc(BC_BRAND.demoEmailOtp) + '</b></div>' +
          '<button class="btn btn-gold mt16" data-otp-btn data-act="verifyEmail" disabled>Verify & add this phone</button>' +
          '<p class="fine center mt12" id="resend"></p>'
        : '<button class="btn btn-gold mt24" data-act="sendEmailCode">' + ic('doc', 16) + 'Email me a code</button>') +
      '<button class="btn-text" data-act="logout">Not you? Cancel</button></div>';
  };
  AFTER.device = function () { if (ui.dev && ui.dev.sent) wireOtp(function () { ACTIONS.verifyEmail(); }); };

  SCREENS.name = function () {
    return '<div class="flow"><div class="auth ob"><div class="ob-ic">' + ic('user', 24) + '</div><h1>What should we call you?</h1>' +
      '<div class="field-l">Full name</div><input id="obName" class="input" autocomplete="name" placeholder="Your name" value="' + esc(ui.ob.name) + '">' +
      '<div class="field-l">Email</div><input id="obEmail" class="input" type="email" inputmode="email" autocomplete="email" placeholder="you@example.com" value="' + esc(ui.ob.email) + '">' +
      '<p class="fine">Used only to confirm it’s you on a new phone.</p></div>' +
      '<div class="sticky-cta"><button class="btn btn-gold" id="obGo" data-act="saveName"' + (obOk() ? '' : ' disabled') + '>Continue</button></div></div>';
  };
  function obOk() { return ui.ob.name.trim().length >= 2 && /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(ui.ob.email.trim()); }
  AFTER.name = function () {
    [['obName', 'name'], ['obEmail', 'email']].forEach(function (f) {
      var el = $(f[0]);
      el.addEventListener('input', function () { ui.ob[f[1]] = el.value; $('obGo').disabled = !obOk(); });
      el.addEventListener('keydown', function (e) { if (e.key === 'Enter') { if (f[0] === 'obName') $('obEmail').focus(); else if (obOk()) ACTIONS.saveName(); } });
    });
    $('obName').focus();
  };

  SCREENS.hi = function () {
    return '<button class="hi" data-go="home"><span class="hi-ic">' + ic('sparkle', 28) + '</span><span class="hi-k">Welcome</span><span class="hi-n">' + esc(BC_MEMBER.firstName) + '</span></button>';
  };
  AFTER.hi = function () { timers.push(setTimeout(function () { if (parse().name === 'hi') go('home'); }, 1600)); };

  /* ----- Age check with Aadhaar number + UIDAI OTP: asked only for pubs and toddy shops ----- */
  var VH_D = [[0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],[3,4,0,1,2,8,9,5,6,7],[4,0,1,2,3,9,5,6,7,8],[5,9,8,7,6,0,4,3,2,1],[6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],[8,7,6,5,9,3,2,1,0,4],[9,8,7,6,5,4,3,2,1,0]];
  var VH_P = [[0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],[8,9,1,6,0,4,3,5,2,7],[9,4,5,3,1,2,6,8,7,0],[4,2,8,6,5,7,3,9,0,1],[2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8]];
  /* 12 digits, can't start with 0 or 1, Verhoeff check digit must match */
  function aadhaarOk(n) {
    if (!/^[2-9]\d{11}$/.test(n)) return false;
    var c = 0; n.split('').reverse().forEach(function (x, i) { c = VH_D[c][VH_P[i % 8][+x]]; });
    return c === 0;
  }
  function fmtAadhaar(n) { return n.replace(/(\d{4})(?=\d)/g, '$1 '); }
  function kycReset() { ui.kyc = { no: '', consent: false, step: 'no' }; }

  SCREENS.kyc = function (back) {
    ui.kycBack = back || 'profile';
    var k = ui.kyc;
    if (k.step === 'otp') {
      return topbar('', ui.kycBack) + '<div class="auth">' +
        '<h1>Enter Aadhaar OTP</h1><p class="lead">Sent by UIDAI to the mobile linked with Aadhaar XXXX XXXX ' + esc(k.no.slice(-4)) + ' · <a class="link" href="javascript:void(0)" data-act="kycEdit">Change</a></p>' +
        '<div class="otp mt16" id="otp">' + otpBoxes(BC_KYC.otpLength) + '</div><div class="err-text" id="otpErr"></div>' +
        '<div class="demo-hint">Demo Aadhaar OTP: <b>' + esc(BC_KYC.demoOtp) + '</b></div>' +
        '<button class="btn btn-gold mt16" data-otp-btn data-act="kycVerify" disabled>Verify my age</button>' +
        '<p class="fine center mt12" id="resend"></p></div>';
    }
    return topbar('', ui.kycBack) + '<div class="auth">' +
      '<div class="kyc-ic">' + ic('shield', 22) + '</div><h1>Verify your age</h1>' +
      '<p class="lead">Pubs and toddy shops need a minimum age by law. Verify once with Aadhaar.</p>' +
      '<div class="field-l">Aadhaar number</div>' +
      '<input id="kycNo" class="input aad-input" inputmode="numeric" maxlength="14" autocomplete="off" placeholder="XXXX XXXX XXXX" value="' + esc(fmtAadhaar(k.no)) + '">' +
      '<div class="err-text" id="kycErr"></div>' +
      '<label class="check"><input type="checkbox" id="kycConsent"' + (k.consent ? ' checked' : '') + '><span>' + esc(BC_KYC.consent) + '</span></label>' +
      '<button class="btn btn-gold mt16" id="kycGo" data-act="kycSendOtp"' + (aadhaarOk(k.no) && k.consent ? '' : ' disabled') + '>Send OTP</button>' +
      '<div class="demo-hint">Demo Aadhaar: <b>' + esc(BC_KYC.demoAadhaar) + '</b></div>' +
      '<button class="btn-text" data-act="kycCancel">Not now</button></div>';
  };
  AFTER.kyc = function () {
    if (ui.kyc.step === 'otp') { wireOtp(function () { ACTIONS.kycVerify(); }); return; }
    var inp = $('kycNo'), k = ui.kyc;
    function check() {
      $('kycGo').disabled = !(aadhaarOk(k.no) && k.consent);
      $('kycErr').textContent = k.no.length === 12 && !aadhaarOk(k.no) ? 'That isn’t a valid Aadhaar number. Please check it.' : '';
    }
    inp.addEventListener('input', function () {
      k.no = inp.value.replace(/\D/g, '').slice(0, 12);
      inp.value = fmtAadhaar(k.no); check();
    });
    $('kycConsent').addEventListener('change', function (e) { k.consent = e.target.checked; check(); });
    if (!k.no) inp.focus();
  };


  SCREENS['kyc-done'] = function (back) {
    var a = ageOf(BC_MEMBER.dob), keys = Object.keys(BC_STATES);
    var all = keys.every(function (k) { return a >= BC_STATES[k].drinkingAge; });
    return '<div class="auth tea-page"><div class="verified-hero"><div class="big-check">' + ic('check', 36) + '</div>' +
      '<h1>You’re verified</h1><p class="lead">' + (all ? 'You can book, reserve and enter every Boche pub.' : 'Here’s where you can enter today.') + '</p></div>' +
      (all ? '' : '<div class="list mt16">' + keys.map(function (k) {
        var ok = a >= BC_STATES[k].drinkingAge;
        return '<div class="li"><div class="li-main"><div class="li-t">' + esc(BC_STATES[k].name) + ' pubs</div><div class="li-s">' + BC_STATES[k].drinkingAge + '+ by law</div></div>' +
          '<span class="badge ' + (ok ? 'ok' : 'err') + '">' + (ok ? 'Eligible' : 'Not yet') + '</span></div>';
      }).join('') + '</div>') +
      '<p class="fine center mt12">Only the last 4 digits and a verified-age flag are kept.</p>' +
      '<button class="btn btn-gold mt24" data-go="' + esc(back || 'home') + '">Continue</button></div>';
  };

  /* ----- Home (hub): flip card + business icons ----- */
  /* ---------- Promo illustrations (inline SVG, one per promo / business) ---------- */
  var SPARK = function (x, y, s, f, o) { return '<path transform="translate(' + x + ' ' + y + ') scale(' + s + ')" d="M0-10C1.4-3 3-1.4 10 0 3 1.4 1.4 3 0 10-1.4 3-3 1.4-10 0-3-1.4-1.4-3 0-10Z" fill="' + f + '" opacity="' + (o || 1) + '"/>'; };
  var ART = {
    draw: '<svg viewBox="0 0 220 220" aria-hidden="true">' +
      '<defs><linearGradient id="dgG" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFF0B0"/><stop offset=".55" stop-color="#F2C75A"/><stop offset="1" stop-color="#C9962E"/></linearGradient>' +
      '<linearGradient id="dgR" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#E23A58"/><stop offset="1" stop-color="#8A1028"/></linearGradient>' +
      '<linearGradient id="dgB" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#FFE9A0" stop-opacity="0"/><stop offset="1" stop-color="#FFE9A0" stop-opacity=".55"/></linearGradient>' +
      '<radialGradient id="dgO"><stop offset="0" stop-color="#FFD76A" stop-opacity=".75"/><stop offset="1" stop-color="#FFD76A" stop-opacity="0"/></radialGradient></defs>' +
      '<circle cx="112" cy="134" r="96" fill="url(#dgO)"/>' +
      '<path d="M86 112L22 0h176L134 112z" fill="url(#dgB)"/>' +
      '<g class="ill-f"><circle cx="60" cy="66" r="17" fill="url(#dgG)"/><circle cx="60" cy="66" r="13" fill="none" stroke="#9A6B16" stroke-width="2" opacity=".7"/><text x="60" y="73" text-anchor="middle" font-size="20" font-weight="800" fill="#7A4F0C" font-family="DM Sans,sans-serif">&#8377;</text></g><g class="ill-f"><circle cx="158" cy="52" r="20" fill="url(#dgG)"/><circle cx="158" cy="52" r="16" fill="none" stroke="#9A6B16" stroke-width="2" opacity=".7"/><text x="158" y="60" text-anchor="middle" font-size="24" font-weight="800" fill="#7A4F0C" font-family="DM Sans,sans-serif">&#8377;</text></g><g class="ill-f"><circle cx="112" cy="26" r="13" fill="url(#dgG)"/><circle cx="112" cy="26" r="9" fill="none" stroke="#9A6B16" stroke-width="2" opacity=".7"/><text x="112" y="31" text-anchor="middle" font-size="15" font-weight="800" fill="#7A4F0C" font-family="DM Sans,sans-serif">&#8377;</text></g><g class="ill-f"><circle cx="184" cy="104" r="12" fill="url(#dgG)"/><circle cx="184" cy="104" r="8" fill="none" stroke="#9A6B16" stroke-width="2" opacity=".7"/><text x="184" y="108" text-anchor="middle" font-size="14" font-weight="800" fill="#7A4F0C" font-family="DM Sans,sans-serif">&#8377;</text></g><g class="ill-f"><circle cx="34" cy="112" r="11" fill="url(#dgG)"/><circle cx="34" cy="112" r="7" fill="none" stroke="#9A6B16" stroke-width="2" opacity=".7"/><text x="34" y="116" text-anchor="middle" font-size="13" font-weight="800" fill="#7A4F0C" font-family="DM Sans,sans-serif">&#8377;</text></g>' +
      '<rect x="68" y="128" width="88" height="72" rx="9" fill="url(#dgR)"/><rect x="104" y="128" width="16" height="72" fill="url(#dgG)"/><rect x="68" y="128" width="88" height="6" fill="#000" opacity=".18"/>' +
      '<ellipse cx="112" cy="124" rx="42" ry="9" fill="#FFE9A0"/><ellipse cx="112" cy="124" rx="30" ry="5" fill="#fff" opacity=".85"/>' +
      '<g transform="rotate(-16 70 118)"><rect x="56" y="92" width="108" height="28" rx="8" fill="#F04A68"/><rect x="102" y="92" width="16" height="28" fill="url(#dgG)"/><rect x="56" y="92" width="108" height="6" rx="3" fill="#fff" opacity=".25"/>' +
      '<path d="M110 92C92 62 66 72 82 92Z" fill="url(#dgG)"/><path d="M110 92C128 62 154 72 138 92Z" fill="#E7C15F"/></g>' +
      '<g class="ill-t">' + SPARK(28, 60, 1.3, '#FFF6D0') + SPARK(196, 66, 1.1, '#FFF6D0') + SPARK(88, 14, .8, '#FFD76A') + SPARK(206, 150, .8, '#FFF6D0') + SPARK(18, 156, .7, '#FFD76A') + '</g>' +
      '<rect x="44" y="40" width="9" height="4" rx="2" fill="#FF5C7A" transform="rotate(-30 48 42)"/><rect x="178" y="30" width="9" height="4" rx="2" fill="#7FE3D0" transform="rotate(35 182 32)"/><rect x="150" y="86" width="8" height="4" rx="2" fill="#FFD66B" transform="rotate(60 154 88)"/><rect x="26" y="84" width="8" height="4" rx="2" fill="#fff" transform="rotate(20 30 86)"/><rect x="128" y="6" width="8" height="4" rx="2" fill="#FF5C7A" transform="rotate(-50 132 8)"/><circle cx="190" cy="130" r="3.5" fill="#FF5C7A"/><circle cx="14" cy="132" r="3" fill="#7FE3D0"/><circle cx="64" cy="26" r="3" fill="#FFD66B"/>' +
      '</svg>',

    pub: '<svg viewBox="0 0 220 220" aria-hidden="true">' +
      '<defs><linearGradient id="pbB" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFD46A"/><stop offset="1" stop-color="#E0841A"/></linearGradient>' +
      '<linearGradient id="pbB2" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFC24E"/><stop offset="1" stop-color="#C96A10"/></linearGradient>' +
      '<radialGradient id="pbO"><stop offset="0" stop-color="#FFB347" stop-opacity=".7"/><stop offset="1" stop-color="#FFB347" stop-opacity="0"/></radialGradient></defs>' +
      '<circle cx="112" cy="130" r="98" fill="url(#pbO)"/>' +
      '<path d="M4 30C50 62 150 4 216 40" fill="none" stroke="#7A5224" stroke-width="1.6"/>' +
      '<g class="pb-b"><circle cx="24" cy="44" r="4.5" fill="#FFD66B"/><circle cx="24" cy="44" r="11" fill="#FFD66B" opacity=".25"/></g>' +
      '<g class="pb-b"><circle cx="62" cy="48" r="4.5" fill="#FFD66B"/><circle cx="62" cy="48" r="11" fill="#FFD66B" opacity=".25"/></g>' +
      '<g class="pb-b"><circle cx="104" cy="36" r="4.5" fill="#FFD66B"/><circle cx="104" cy="36" r="11" fill="#FFD66B" opacity=".25"/></g>' +
      '<g class="pb-b"><circle cx="148" cy="26" r="4.5" fill="#FFD66B"/><circle cx="148" cy="26" r="11" fill="#FFD66B" opacity=".25"/></g>' +
      '<g class="pb-b"><circle cx="188" cy="32" r="4.5" fill="#FFD66B"/><circle cx="188" cy="32" r="11" fill="#FFD66B" opacity=".25"/></g>' +
      '<g transform="translate(110 184) scale(.86) translate(-110 -184)">' +
      '<g class="pb-l"><g transform="rotate(14 57 184)"><path d="M30 104h-14a13 13 0 0 0 0 42h14" fill="none" stroke="#F1E3C2" stroke-width="7" opacity=".95"/>' +
      '<rect x="26" y="92" width="62" height="92" rx="10" fill="url(#pbB)"/><rect x="26" y="92" width="62" height="92" rx="10" fill="none" stroke="#FFF3D6" stroke-width="3"/>' +
      '<rect x="36" y="112" width="9" height="60" rx="4.5" fill="#FFF3C4" opacity=".6"/>' +
      '<circle class="bub" cx="52" cy="170" r="3" fill="#FFF3C4"/><circle class="bub b2" cx="68" cy="176" r="2.4" fill="#FFF3C4"/><circle class="bub b3" cx="46" cy="176" r="2" fill="#FFF3C4"/>' +
      '<circle cx="36" cy="90" r="14" fill="#FFFBEE"/><circle cx="56" cy="82" r="17" fill="#FFFBEE"/><circle cx="77" cy="90" r="14" fill="#FFFBEE"/><rect x="26" y="90" width="62" height="10" fill="#FFFBEE"/></g></g>' +
      '<g class="pb-r"><g transform="rotate(-14 163 184)"><path d="M190 104h14a13 13 0 0 1 0 42h-14" fill="none" stroke="#F1E3C2" stroke-width="7" opacity=".95"/>' +
      '<rect x="132" y="92" width="62" height="92" rx="10" fill="url(#pbB2)"/><rect x="132" y="92" width="62" height="92" rx="10" fill="none" stroke="#FFF3D6" stroke-width="3"/>' +
      '<rect x="168" y="112" width="9" height="60" rx="4.5" fill="#FFF3C4" opacity=".5"/>' +
      '<circle class="bub b2" cx="156" cy="172" r="3" fill="#FFF3C4"/><circle class="bub" cx="172" cy="178" r="2.4" fill="#FFF3C4"/>' +
      '<circle cx="142" cy="90" r="14" fill="#FFFBEE"/><circle cx="162" cy="82" r="17" fill="#FFFBEE"/><circle cx="183" cy="90" r="14" fill="#FFFBEE"/><rect x="132" y="90" width="62" height="10" fill="#FFFBEE"/></g></g></g>' +
      '<g transform="translate(-2 26)"><g class="pb-s">' + SPARK(112, 82, 1.7, '#FFF6D0') + '<g fill="#FFE29A"><ellipse cx="92" cy="62" rx="3" ry="5" transform="rotate(-25 92 62)"/><ellipse cx="132" cy="58" rx="3" ry="5" transform="rotate(25 132 58)"/><ellipse cx="108" cy="46" rx="2.4" ry="4"/><ellipse cx="120" cy="64" rx="2" ry="3.4"/><circle cx="82" cy="50" r="2.6"/><circle cx="144" cy="48" r="2.6"/><circle cx="100" cy="70" r="2"/><circle cx="126" cy="72" r="2"/></g></g></g></svg>',

    resort: '<svg viewBox="0 0 220 220" aria-hidden="true">' +
      '<defs><radialGradient id="rsS"><stop offset="0" stop-color="#FFF1BE"/><stop offset=".45" stop-color="#FFC56A"/><stop offset="1" stop-color="#FF8A3D" stop-opacity="0"/></radialGradient>' +
      '<linearGradient id="rsM" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#4E9A72"/><stop offset="1" stop-color="#1D4F3A"/></linearGradient>' +
      '<linearGradient id="rsM2" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2F7457"/><stop offset="1" stop-color="#123628"/></linearGradient></defs>' +
      '<g class="rs-sun"><circle cx="132" cy="118" r="100" fill="url(#rsS)"/><circle cx="132" cy="118" r="34" fill="#FFF3C8"/></g>' +
      '<g class="rs-st">' + SPARK(30, 36, .9, '#FFF3C8') + '</g><g class="rs-st s2">' + SPARK(78, 18, .6, '#FFF3C8') + '</g><g class="rs-st s3">' + SPARK(190, 30, .8, '#FFF3C8') + '</g><g class="rs-st s4">' + SPARK(18, 84, .5, '#FFF3C8') + '</g>' +
      '<path class="rs-bd" d="M0 0q6-6 12 0q6-6 12 0" fill="none" stroke="#0E2A1F" stroke-width="2" stroke-linecap="round" transform="translate(40 70)"/>' +
      '<g class="rs-m1"><path d="M-10 160L50 82l34 50 26-30 62 66 58-34v66H-10Z" fill="url(#rsM)"/><path d="M50 82l-16 24 16-8 12 14z" fill="#fff" opacity=".4"/><path d="M-10 160L50 82l8 12L-10 176z" fill="#FFB86B" opacity=".25"/></g>' +
      '<g class="rs-m2"><path d="M-10 182l66-36 40 24 44-28 90 44v34H-10Z" fill="url(#rsM2)"/>' +
      '<g fill="#0E2A1F"><path d="M20 196l11-34 11 34z"/><path d="M28 180l7-22 7 22z"/><path d="M176 200l10-30 10 30z"/><path d="M188 188l8-24 8 24z"/></g></g>' +
      '<ellipse class="rs-fl" cx="108" cy="186" rx="34" ry="10" fill="#FFC56A" opacity=".4"/>' +
      '<g transform="translate(82 140)"><path d="M0 48L26 6l26 42z" fill="#FFF1D2"/><path class="rs-fl" d="M12 48L26 22l14 26z" fill="#FFB347"/><path d="M26 6V-2" stroke="#FFF1D2" stroke-width="3"/></g>' +
      '<circle class="rs-sp" cx="150" cy="170" r="3" fill="#FFB347"/><circle class="rs-sp s2" cx="156" cy="170" r="2" fill="#FFD66B"/><circle class="rs-sp s3" cx="146" cy="170" r="1.8" fill="#FFD66B"/></svg>',

    friend: '<svg viewBox="0 0 220 220" aria-hidden="true">' +
      '<defs><linearGradient id="frG" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFF0B0"/><stop offset=".55" stop-color="#F2C75A"/><stop offset="1" stop-color="#C9962E"/></linearGradient>' +
      '<linearGradient id="frP" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFC2D2"/><stop offset="1" stop-color="#FF6F96"/></linearGradient>' +
      '<radialGradient id="frO"><stop offset="0" stop-color="#FF5C8A" stop-opacity=".6"/><stop offset="1" stop-color="#FF5C8A" stop-opacity="0"/></radialGradient></defs>' +
      '<circle cx="112" cy="130" r="98" fill="url(#frO)"/>' +
      '<g transform="translate(70 120)"><path class="fr-up" d="M0 0c-3-6-12-4-11 3 1 5 7 8 11 12 4-4 10-7 11-12 1-7-8-9-11-3z" fill="#FF8FB0"/></g>' +
      '<g transform="translate(150 120)"><path class="fr-up u2" d="M0 0c-3-6-12-4-11 3 1 5 7 8 11 12 4-4 10-7 11-12 1-7-8-9-11-3z" fill="#FFC2D2"/></g>' +
      '<g transform="translate(110 112)"><path class="fr-up u3" d="M0 0c-3-6-12-4-11 3 1 5 7 8 11 12 4-4 10-7 11-12 1-7-8-9-11-3z" fill="#FF6F96"/></g>' +
      '<g transform="translate(92 118)"><path class="fr-up u4" d="M0 0c-3-6-12-4-11 3 1 5 7 8 11 12 4-4 10-7 11-12 1-7-8-9-11-3z" fill="#FFD66B"/></g>' +
      '<g class="fr-h"><path d="M112 78c-8-16-34-12-32 8 2 14 20 24 32 34 12-10 30-20 32-34 2-20-24-24-32-8z" fill="url(#frP)"/><path d="M96 74c4-4 10-4 14 0" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" opacity=".6"/></g>' +
      '<g class="fr-c"><circle cx="176" cy="60" r="22" fill="url(#frG)"/><circle cx="176" cy="60" r="18" fill="none" stroke="#9A6B16" stroke-width="2" opacity=".7"/><text x="176" y="66" text-anchor="middle" font-size="15" font-weight="800" fill="#7A4F0C" font-family="DM Sans,sans-serif">+500</text></g>' +
      '<g class="fr-a1"><circle cx="76" cy="138" r="25" fill="url(#frG)"/><path d="M28 214c0-32 21-52 48-52s48 20 48 52z" fill="url(#frG)"/><path d="M58 172c8 6 20 6 28 0" fill="none" stroke="#9A6B16" stroke-width="2.5" stroke-linecap="round" opacity=".5"/></g>' +
      '<g class="fr-a2"><circle cx="150" cy="144" r="23" fill="#FFE6EC"/><path d="M104 214c0-30 20-48 46-48s46 18 46 48z" fill="#FFE6EC"/><path d="M134 176c8 6 20 6 28 0" fill="none" stroke="#C94A70" stroke-width="2.5" stroke-linecap="round" opacity=".5"/></g>' +
      '<rect x="48" y="30" width="9" height="4" rx="2" fill="#FFD66B" transform="rotate(-30 52 32)"/><rect x="186" y="96" width="9" height="4" rx="2" fill="#fff" transform="rotate(40 190 98)"/></svg>',

    tea: '<svg viewBox="0 0 220 220" aria-hidden="true">' +
      '<defs><radialGradient id="teO"><stop offset="0" stop-color="#B8F060" stop-opacity=".55"/><stop offset="1" stop-color="#B8F060" stop-opacity="0"/></radialGradient>' +
      '<linearGradient id="teC" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="#DDE9C6"/></linearGradient>' +
      '<linearGradient id="teL" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#B8F060"/><stop offset="1" stop-color="#5FA52A"/></linearGradient></defs>' +
      '<circle cx="112" cy="134" r="98" fill="url(#teO)"/>' +
      '<g fill="none" stroke="#D8F79A" stroke-width="4.5" stroke-linecap="round"><path class="te-st" pathLength="100" d="M80 96c-12-14 12-22 0-40s10-24 4-38"/><path class="te-st s2" pathLength="100" d="M110 92c-12-14 12-22 0-42s10-26 4-42"/><path class="te-st s3" pathLength="100" d="M140 96c-12-14 12-22 0-40s10-24 4-38"/></g>' +
      '<path d="M40 108h144v26a64 56 0 0 1-72 56 64 56 0 0 1-72-56z" fill="url(#teC)"/>' +
      '<path d="M184 116h14a18 18 0 0 1 0 38h-22" fill="none" stroke="#F1F6E4" stroke-width="10" stroke-linecap="round"/>' +
      '<ellipse cx="112" cy="108" rx="72" ry="11" fill="#C98A3E"/><ellipse cx="112" cy="108" rx="72" ry="11" fill="none" stroke="#F1D88A" stroke-width="4"/><ellipse class="te-sh" cx="100" cy="106" rx="30" ry="3.4" fill="#F5CC8A" opacity=".8"/>' +
      '<path d="M54 134c4 28 26 42 54 44" fill="none" stroke="#7BBF3A" stroke-width="6" stroke-linecap="round" opacity=".65"/><path d="M60 126h104" stroke="#F1D88A" stroke-width="3" opacity=".8"/>' +
      '<ellipse cx="112" cy="198" rx="92" ry="11" fill="#06190B" opacity=".55"/><ellipse cx="112" cy="194" rx="90" ry="10" fill="#EAF3D2"/><ellipse cx="112" cy="192" rx="62" ry="5" fill="#fff" opacity=".6"/>' +
      '<g class="te-lf"><path d="M14 74c22-6 36 6 38 26-22 6-38-6-38-26z" fill="url(#teL)"/><path d="M18 78c10 4 20 12 28 20" stroke="#2E6A14" stroke-width="1.6" fill="none" opacity=".6"/></g>' +
      '<g class="te-lf l2"><path d="M50 40c16 6 24 20 16 36-16-6-24-20-16-36z" fill="#8FD14A"/></g>' +
      '<g class="te-lf l3"><path d="M186 82c-22-2-34 12-32 30 22 0 34-12 32-30z" fill="url(#teL)"/><path d="M182 88c-10 6-18 14-24 22" stroke="#2E6A14" stroke-width="1.6" fill="none" opacity=".6"/></g>' +
      '<path class="te-fl" d="M0 0c10-3 17 3 18 12-10 3-18-3-18-12z" fill="#B8F060" transform="translate(150 10)"/>' +
      '<g class="te-tw">' + SPARK(190, 36, .9, '#EAF9C4') + '</g></svg>',

    gold: '<svg viewBox="0 0 220 220" aria-hidden="true">' +
      '<defs><radialGradient id="goO"><stop offset="0" stop-color="#FFD76A" stop-opacity=".7"/><stop offset="1" stop-color="#FFD76A" stop-opacity="0"/></radialGradient>' +
      '<linearGradient id="goA" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="#F6E3B0"/></linearGradient>' +
      '<linearGradient id="goB" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFE9A0"/><stop offset="1" stop-color="#D6A33C"/></linearGradient>' +
      '<clipPath id="goCl"><path d="M56 56h108l34 44-88 106L22 100z"/></clipPath></defs>' +
      '<circle cx="112" cy="124" r="100" fill="url(#goO)"/>' +
      '<g class="go-gem"><path d="M56 56h108l34 44-88 106L22 100z" fill="url(#goA)"/>' +
      '<path d="M22 100h176M56 56l26 44 30 106 30-106 26-44M82 100l30-44 30 44" fill="none" stroke="#C9962E" stroke-width="3" stroke-linejoin="round"/>' +
      '<path d="M56 56l26 44-60 0z" fill="url(#goB)"/><path d="M164 56l-26 44h60z" fill="#E7C46A"/><path d="M82 100h60l-30 106z" fill="#F6DD8C"/><path d="M82 100l30-44 30 44z" fill="#fff"/>' +
      '<g clip-path="url(#goCl)"><g class="go-gl"><rect x="-40" y="20" width="30" height="220" fill="#fff" opacity=".9" transform="rotate(22 0 100)"/></g></g></g>' +
      '<g class="go-p">' + SPARK(36, 50, 1.4, '#FFF6D0') + '</g><g class="go-p p2">' + SPARK(196, 54, 1.1, '#FFF6D0') + '</g><g class="go-p p3">' + SPARK(206, 150, .9, '#FFD76A') + '</g><g class="go-p p4">' + SPARK(18, 150, .8, '#FFD76A') + '</g><g class="go-p p5">' + SPARK(112, 14, .8, '#FFF6D0') + '</g>' +
      '<circle cx="44" cy="190" r="3" fill="#FFD76A"/><circle cx="184" cy="196" r="3.4" fill="#FFF6D0"/></svg>'
  };
  function ill(key) { return ART[key] ? '<span class="hm-ill">' + ART[key] + '</span>' : ''; }

  SCREENS.home = function () {
    return '<div class="hm"><div class="home-head"><div class="hh-left"><div class="avatar">' + initials(BC_MEMBER.name) + '</div>' +
      '<div><div class="hh-greet">' + greeting() + '</div><div class="hh-name">' + esc(BC_MEMBER.firstName) + '</div></div></div>' +
      '<div class="hh-actions"><button class="iconbtn" data-go="support" aria-label="Customer support">' + ic('headset') + '</button>' +
      '<button class="iconbtn" data-act="notifs" aria-label="Notifications">' + ic('bell') + '<span class="dot"></span></button></div></div>' +
      '<div class="hm-promos" id="promos">' + BC_PROMOS.map(function (p) {
        var b = biz(p.biz), icn = p.icon || (b ? b.icon : 'users'), live = !b || b.live;
        return '<button class="hm-slide th-' + p.biz + (p.art ? ' has-ill art-' + p.art : '') + '" ' + (live ? 'data-go="' + p.go + '"' : 'data-act="soonBiz" data-id="' + p.biz + '"') + '>' +
          (p.art ? ill(p.art) : '<span class="hm-art">' + ic(icn, 150) + '</span>') +
          (p.logo ? '<span class="hm-logo"><img src="' + esc(p.logo) + '" alt="Shakesbierre Brewpub &amp; Club by Boche"></span>' : '') +
          '<span class="hm-eyebrow">' + ic(icn, 14) + esc(b ? b.label : BC_BRAND.name) + '</span>' +
          '<span class="hm-title">' + esc(p.title) + '</span><span class="hm-text">' + esc(p.text) + '</span>' +
          '<span class="hm-cta">' + esc(p.cta) + (live ? ic('chev', 14) : '') + '</span></button>';
      }).join('') + '</div>' +
      '<div class="hm-dots" id="promoDots">' + BC_PROMOS.map(function (p, i) { return '<i' + (i ? '' : ' class="on"') + '></i>'; }).join('') + '</div>' +
      '<div class="hm-fam"><div class="sec-h"><h3>Boche family</h3></div><div class="pad"><div class="hm-biz">' +
      BC_BUSINESSES.map(function (b) {
        var act = b.live ? 'data-go="' + (b.route || 'biz/' + b.id) + '"' : 'data-act="soonBiz" data-id="' + b.id + '"';
        return '<button class="hm-tile' + (b.live ? '' : ' is-soon') + '" ' + act + '>' +
          ic(b.icon, 24) + esc(b.label) + (b.live ? '' : '<span class="hm-soon">Soon</span>') + '</button>';
      }).join('') + '</div></div></div></div>';
  };
  function smsCheck() {
    var p = S.pendingOtp;
    if (!SES.authed || !p || p.memberId !== BC_MEMBER.id || p.status !== 'sent' || ui.seenOtp === p.ts) return;
    ui.seenOtp = p.ts;
    toast('SMS · ' + p.code + ' is your Boche check-in OTP for ' + outlet(p.outlet).name, 7000);
  }
  function wireCodeEntry() {
    var wrap = $('code4'), ins = wrap.querySelectorAll('input'), btn = $('codeGo');
    function code() { return Array.prototype.map.call(ins, function (x) { return x.value; }).join(''); }
    Array.prototype.forEach.call(ins, function (inp, i) {
      inp.addEventListener('input', function () {
        var v = inp.value.replace(/\D/g, '');
        if (v.length > 1) { v.split('').slice(0, 4).forEach(function (ch, k) { if (ins[k]) ins[k].value = ch; }); ins[Math.min(3, v.length - 1)].focus(); }
        else { inp.value = v; if (v && ins[i + 1]) ins[i + 1].focus(); }
        wrap.classList.remove('bad'); btn.disabled = code().length !== 4;
      });
      inp.addEventListener('keydown', function (e) {
        if (e.key === 'Backspace' && !inp.value && ins[i - 1]) ins[i - 1].focus();
        if (e.key === 'Enter' && code().length === 4) ACTIONS.codeEnter();
      });
    });
  }
  AFTER.home = function () { smsCheck(); wireRail(); };

  AFTER.profile = function () {
    var f = $('photoIn'); if (!f) return;
    f.addEventListener('change', function () {
      var file = f.files && f.files[0]; if (!file) return;
      var img = new Image(), url = URL.createObjectURL(file);
      img.onload = function () {
        var n = 320, c = document.createElement('canvas'), side = Math.min(img.width, img.height);
        c.width = c.height = n;
        c.getContext('2d').drawImage(img, (img.width - side) / 2, (img.height - side) / 3, side, side, 0, 0, n, n);
        URL.revokeObjectURL(url);
        var d = dyn(BC_MEMBER.id); d.profile = d.profile || {}; d.profile.photo = c.toDataURL('image/jpeg', .85); save(); rerender(); toast('Photo updated');
      };
      img.onerror = function () { URL.revokeObjectURL(url); toast('Could not read that image'); };
      img.src = url;
    });
  };

  /* ----- Card ----- */
  SCREENS.card = function () {
    var t = curTier(), hp = outlet(BC_MEMBER.homeOutlet);
    return topbar('Membership card', '') + '<div class="pad">' +
      /* QR side first: it's what members show at the venue; tap to see the card front */
      '<div class="flip" id="flip" data-act="flip"><div class="flip-inner"><div class="face front">' + cardBack() + '</div><div class="face back">' + cardFront() + '</div></div></div>' +
      '<p class="hint">Show this QR at any Boche venue · tap the card to flip</p>' +
      '<div class="surface otp-panel"><div class="op-h"><b>Venue OTP</b><span>Code sent to your mobile at check-in</span></div>' +
        '<div class="code-row"><div class="code4" id="code4">' + [0, 1, 2, 3].map(function (i) { return '<input inputmode="numeric" maxlength="1" autocomplete="' + (i ? 'off' : 'one-time-code') + '" aria-label="OTP digit ' + (i + 1) + '">'; }).join('') + '</div>' +
        '<button class="btn btn-gold" id="codeGo" data-act="codeEnter" disabled>Enter</button></div>' +
        '<button class="btn-text otp-demo" data-act="demoOtp">Demo: simulate the venue sending my code</button></div>' +
      '<details class="fold mt16"><summary><span>Card details</span><span class="li-s">' + esc(t.name) + ' · ' + esc(BC_MEMBER.id) + '</span>' + ic('chev', 16) + '</summary>' +
      '<div class="surface" style="padding:4px 16px">' +
      '<div class="kv"><span>Member ID</span><span>' + esc(BC_MEMBER.id) + '</span></div>' +
      '<div class="kv"><span>Mobile</span><span>+91 ' + esc(BC_MEMBER.mobile) + '</span></div>' +
      '<div class="kv"><span>Tier</span><span>' + esc(t.name) + '</span></div>' +
      '<div class="kv"><span>Member since</span><span>' + esc(BC_MEMBER.memberSince) + '</span></div>' +
      '<div class="kv"><span>Valid thru</span><span>' + esc(BC_MEMBER.validThru) + '</span></div>' +
      '<div class="kv"><span>Home venue</span><span>' + esc(hp.city) + '</span></div>' +
      '<div class="kv"><span>Age verification</span>' + (kycOf() ? '<span class="pos">Verified</span>' : '<a class="link" href="/' + verifyRoute('card') + '">Verify</a>') + '</div></div></details></div>';
  };
  function startQr() {
    var left = 30, C = 2 * Math.PI * 11;
    function draw() { $('qrSvg').innerHTML = BCQR.svg(BC_MEMBER.id + ':' + Math.floor(Date.now() / 30000), 200); left = 30 - Math.floor((Date.now() % 30000) / 1000); }
    function tick() {
      if (!$('qrCount')) return;
      left--; if (left <= 0) draw();
      $('qrCount').textContent = left; $('qrRing').style.strokeDashoffset = (C * (1 - left / 30)).toFixed(2);
    }
    draw(); $('qrCount').textContent = left; timers.push(setInterval(tick, 1000));
  }
  AFTER.card = function () { startQr(); wireCodeEntry(); };

  /* ----- Explore (all outlets) ----- */
  SCREENS.explore = function () {
    var f = ui.exploreFilter, list = BC_OUTLETS.filter(function (o) { return f === 'all' || o.biz === f; });
    return topbar('Explore', '') + '<div class="pad">' +
      '<p class="sub">Your card works at every Boche venue below.</p>' +
      '<div class="chips scroll-x" style="margin-bottom:14px"><button class="chip' + (f === 'all' ? ' on' : '') + '" data-act="exploreFilter" data-id="all">All</button>' +
      liveBiz().filter(function (b) { return BC_OUTLETS.some(function (o) { return o.biz === b.id; }); }).map(function (b) { return '<button class="chip' + (f === b.id ? ' on' : '') + '" data-act="exploreFilter" data-id="' + b.id + '">' + esc(b.name) + '</button>'; }).join('') + '</div>' +
      list.map(outletCard).join('') +
      '<div class="sec-h" style="padding:0;margin-top:8px"><h3>Coming soon</h3></div><div class="biz-grid">' +
      soonBiz().map(function (b) {
        return '<button class="biz-tile soon-t" data-act="soonBiz" data-id="' + b.id + '"><span class="badge plain">Coming soon</span><span class="li-ic">' + ic(b.icon, 20) + '</span><b>' + esc(b.name) + '</b><span class="bt-sub">' + esc(b.blurb) + '</span></button>';
      }).join('') + '</div></div>';
  };

  /* ----- Business page ----- */
  /* ----- Business sub-home: live promos · points ready to redeem · open the business's own app ----- */
  SCREENS.biz = function (id) {
    var b = biz(id); if (!b || !b.live) return SCREENS.home();
    var pts = pointsOf(BC_MEMBER.id, b.id), t = curTier();
    var offers = BC_OFFERS.filter(function (o) { return o.biz === b.id; });
    var rewards = BC_REWARDS.filter(function (r) { return r.biz === b.id; });
    var ready = pts >= b.minRedeem ? rewards.filter(function (r) { return pts >= r.pts; }) : [];
    var next = rewards.filter(function (r) { return pts < r.pts; }).sort(function (x, y) { return x.pts - y.pts; })[0];
    var myV = dyn(BC_MEMBER.id).vouchers.filter(function (v) { return v.biz === b.id && !v.used; });
    var gated = BC_OUTLETS.filter(function (o) { return o.biz === b.id; }).every(function (o) { return o.ageGate; });
    return '<div class="flow">' + topbar(b.name, 'home') +
      (offers.length ? '<div class="hm-promos bz-promos" id="promos">' + offers.map(function (o) {
        var on = S.activated.indexOf(o.id) > -1, allowed = o.tiers.indexOf(t.id) > -1;
        return '<div class="hm-slide th-' + b.id + (ART[b.id] ? ' has-ill' : '') + '">' + (ART[b.id] ? ill(b.id) : '<span class="hm-art">' + ic(b.icon, 150) + '</span>') +
          '<span class="hm-eyebrow">' + esc(o.kind) + ' · ' + esc(o.valid) + '</span>' +
          '<span class="hm-title">' + esc(o.title) + '</span><span class="hm-text">' + esc(o.desc) + '</span>' +
          (allowed ? '<button class="hm-cta" data-act="activate" data-id="' + o.id + '">' + (on ? ic('check', 14) + 'Activated' : 'Activate offer') + '</button>'
            : '<a class="hm-cta" href="/tiers">' + ic('lock', 13) + esc(byId(BC_TIERS, o.tiers[0]).name) + ' & above</a>') + '</div>';
      }).join('') + '</div><div class="hm-dots" id="promoDots">' + offers.map(function (o, i) { return '<i' + (i ? '' : ' class="on"') + '></i>'; }).join('') + '</div>' : '') +
      '<div class="pad">' +
      '<div class="bz-pts"><div><div class="bz-k">' + esc(b.short) + ' points</div><div class="bz-v">' + num(pts) + '</div>' +
        '<div class="bz-s">Worth ' + inr(pts * b.rupeeValue) + ' · ' + b.earn[t.id] + ' pts per ₹100</div></div>' +
        '<span class="bz-ready">' + (ready.length ? '<b>' + ready.length + '</b>' + (ready.length > 1 ? 'rewards' : 'reward') + ' ready' : '<b>0</b>ready') + '</span></div>' +
      (b.expiring && b.expiring.points ? '<div class="alert">' + ic('clock', 16) + '<span><b>' + num(b.expiring.points) + ' points</b> expire on ' + esc(b.expiring.date) + '</span></div>' : '') +
      (gated && !kycOf() ? '<button class="alert alert-btn" data-go="' + verifyRoute('biz/' + b.id) + '">' + ic('shield', 16) + '<span>Verify your age once to book and enter</span>' + ic('chev', 14) + '</button>' : '') +
      (myV.length ? '<div class="field-l">Your vouchers</div>' + myV.map(function (v) {
        return '<div class="voucher"><div class="li-t">' + esc(v.title) + '</div><div class="code">' + esc(v.code) + '</div><div class="li-s">Show at the counter · issued ' + esc(v.date) + '</div></div>';
      }).join('') : '') +
      '<div class="field-l">Redeem now</div>' +
      (ready.length ? '<div class="list">' + ready.map(function (r) {
        return '<div class="reward"><span class="li-ic">' + ic(r.icon, 16) + '</span><div class="li-main"><div class="li-t">' + esc(r.title) + '</div><div class="li-s"><span class="pts">' + num(r.pts) + ' pts</span></div></div>' +
          '<button class="btn btn-sm btn-soft" data-act="redeem" data-id="' + r.id + '">Redeem</button></div>';
      }).join('') + '</div>'
        : '<div class="surface bz-none">' + (next ? '<span>' + num(next.pts - pts) + ' more points for <b>' + esc(next.title) + '</b></span><i style="width:' + Math.round(pts / next.pts * 100) + '%"></i>' : '<span>Earn points on every bill</span>') + '</div>') +
      '</div><div class="sticky-cta"><button class="btn btn-gold" data-act="openApp" data-id="' + b.id + '">' + ic('open', 16) + 'Open ' + esc(b.appName) + '</button></div></div>';
  };
  AFTER.biz = function () { if ($('promos')) wireRail(); };
  var railMemo = {};
  /* Swipeable promo rail with dots; auto-advances until the user touches it */
  function wireRail() {
    var rail = $('promos'), dots = $('promoDots').children, slides = rail.children, cur = 0, paused = false, key = location.pathname;
    if (slides.length < 2) return;
    if (railMemo[key]) { rail.scrollLeft = railMemo[key]; cur = Math.min(slides.length - 1, Math.round(railMemo[key] / (slides[1].offsetLeft - slides[0].offsetLeft))); Array.prototype.forEach.call(dots, function (d, i) { d.className = i === cur ? 'on' : ''; }); }
    function at() { var step = slides[1].offsetLeft - slides[0].offsetLeft; return step > 0 ? Math.round(rail.scrollLeft / step) : cur; }
    rail.addEventListener('scroll', function () {
      if (!rail.isConnected) return;
      var i = Math.max(0, Math.min(slides.length - 1, at()));
      railMemo[key] = rail.scrollLeft;
      if (i !== cur) { dots[cur].className = ''; cur = i; dots[cur].className = 'on'; }
    }, { passive: true });
    ['touchstart', 'pointerdown'].forEach(function (ev) { rail.addEventListener(ev, function () { paused = true; }, { passive: true }); });
    if (!matchMedia('(prefers-reduced-motion: reduce)').matches) timers.push(setInterval(function () {
      if (paused || document.hidden) return;
      var n = (cur + 1) % slides.length;
      rail.scrollTo({ left: slides[n].offsetLeft - slides[0].offsetLeft, behavior: 'smooth' });
    }, BC_PROMO_CFG.rotateMs));
  }

  /* ----- Outlet ----- */
  SCREENS.outlet = function (id) {
    var o = outlet(id); if (!o) return SCREENS.explore();
    var b = biz(o.biz), st = ageState(o), offers = BC_OFFERS.filter(function (x) { return x.outlets === 'all' ? x.biz === o.biz : x.outlets.indexOf(o.id) > -1; });
    var events = BC_EVENTS.filter(function (e) { return e.outlet === o.id; });
    return topbar(o.city, 'explore') +
      '<div class="pub-hero detail-hero tone-' + o.tone + '">' + (o.logo ? '<span class="pub-logo big"><img src="' + esc(o.logo) + '" alt=""></span>' : '') + '<span class="pub-city">' + esc(o.name) + '</span><span class="pub-rating">' + ic('star', 12) + o.rating + '</span></div>' +
      '<div class="pad mt16"><div class="list">' +
      '<div class="li"><span class="li-ic">' + ic('pin', 18) + '</span><div class="li-main"><div class="li-t">' + esc(o.area) + '</div><div class="li-s">' + esc(o.city) + ', ' + esc(BC_STATES[o.state].name) + ' · ' + esc(o.distance) + ' away</div></div></div>' +
      '<div class="li"><span class="li-ic">' + ic('clock', 18) + '</span><div class="li-main"><div class="li-t">' + esc(o.hours) + '</div><div class="li-s">' + esc(o.kind) + ' · part of ' + esc(b.name) + '</div></div></div>' +
      '<div class="li"><span class="li-ic">' + ic('phone', 18) + '</span><div class="li-main"><div class="li-t">' + esc(o.phone) + '</div><div class="li-s">Call for groups and enquiries</div></div></div>' +
      '<div class="li"><span class="li-ic">' + ic('shield', 18) + '</span><div class="li-main"><div class="li-t">' + (o.ageGate ? 'Entry ' + BC_STATES[o.state].drinkingAge + '+' : 'All ages welcome') + '</div><div class="li-s">' +
      ({ open: 'No age restriction', ok: 'You’re eligible · age verified', verify: 'One-time Aadhaar check before you visit', under: 'Not available for your age' })[st] + '</div></div></div>' +
      '<div class="li"><span class="li-ic">' + ic('qr', 18) + '</span><div class="li-main"><div class="li-t">' + esc(o.checkinLabel) + ' with your card</div><div class="li-s">Staff scan your Boche QR</div></div></div></div>' +
      '<div class="pub-tags mt12">' + o.tags.map(function (t) { return '<span class="badge">' + esc(t) + '</span>'; }).join('') + '</div>' +
      (offers.length ? '<div class="sec-h" style="padding:0;margin-top:22px"><h3>Offers</h3></div>' + offers.map(offerCard).join('') : '') +
      (events.length ? '<div class="sec-h" style="padding:0;margin-top:22px"><h3>Events</h3></div><div class="list">' + events.map(eventRow).join('') + '</div>' : '') +
      '</div>' +
      (st === 'under' ? '' : '<div class="sticky-cta"><div class="' + (o.bookable || st === 'verify' ? 'btn-row' : '') + '">' +
        '<button class="btn btn-line" data-act="openApp" data-id="' + b.id + '">' + ic('open', 16) + 'Open app</button>' +
        (st === 'verify' ? '<button class="btn btn-gold" data-go="' + verifyRoute(o.bookable ? 'book/' + o.id : 'outlet/' + o.id) + '">' + ic('shield', 16) + (o.bookable ? 'Verify & book' : 'Verify age') + '</button>'
          : o.bookable ? '<button class="btn btn-gold" data-go="book/' + o.id + '">Book a table</button>' : '') + '</div></div>');
  };

  /* ----- Book a table ----- */
  SCREENS.book = function (id) {
    var o = outlet(id); if (!o || !o.bookable || !eligible(o)) return SCREENS.explore();
    var b = ui.book, days = [], d;
    for (var i = 0; i < 7; i++) { d = new Date(); d.setDate(d.getDate() + i); days.push(d); }
    var priority = curTier().id !== 'classic';
    return topbar('Book a table', 'outlet/' + o.id) + '<div class="pad">' +
      '<p class="sub">' + esc(o.name) + ' · ' + esc(o.area) + '</p>' +
      (priority ? '<div class="alert" style="margin-top:0">' + ic('crown', 18) + '<span>' + esc(curTier().name) + ' members get priority confirmation.</span></div>' : '') +
      '<div class="field-l">Date</div><div class="chips scroll-x">' + days.map(function (dd, k) {
        var lbl = k === 0 ? 'Today' : k === 1 ? 'Tomorrow' : dd.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric' });
        return '<button class="chip' + (b.day === k ? ' on' : '') + '" data-act="bookDay" data-id="' + k + '">' + lbl + '</button>';
      }).join('') + '</div>' +
      '<div class="field-l">Time</div><div class="chips">' + BC_BOOKING.times.map(function (t) {
        return '<button class="chip' + (b.time === t ? ' on' : '') + '" data-act="bookTime" data-id="' + esc(t) + '">' + esc(t) + '</button>';
      }).join('') + '</div>' +
      '<div class="field-l">Guests</div><div class="stepper"><button data-act="guests" data-id="-1" aria-label="Fewer">' + ic('minus', 18) + '</button><span class="v">' + b.guests + '</span><button data-act="guests" data-id="1" aria-label="More">' + ic('plus', 18) + '</button></div>' +
      '<div class="field-l">Occasion</div><div class="chips">' + BC_BOOKING.occasions.map(function (oc) {
        return '<button class="chip' + (b.occasion === oc ? ' on' : '') + '" data-act="bookOcc" data-id="' + esc(oc) + '">' + esc(oc) + '</button>';
      }).join('') + '</div>' +
      '<div class="field-l">Note for the team (optional)</div><textarea class="input" id="bookNote" placeholder="e.g. window seat, cake arrangement">' + esc(b.note) + '</textarea>' +
      '<button class="btn btn-gold mt24" data-act="confirmBook" data-id="' + o.id + '"' + (b.time ? '' : ' disabled') + '>Confirm booking</button></div>';
  };
  AFTER.book = function () { var n = $('bookNote'); if (n) n.addEventListener('input', function () { ui.book.note = n.value; }); };

  /* ----- Child app (SSO simulation) ----- */
  SCREENS.app = function (id) {
    var b = biz(id); if (!b || !b.live) return SCREENS.home();
    return '<div class="childapp"><button class="ca-back" data-go="home" aria-label="Back to Boche">' + ic('back', 16) + 'Boche</button><div class="ca-head"><span class="ca-ic">' + ic(b.icon, 22) + '</span><div><div class="ca-t">' + esc(b.name) + '</div><div class="ca-s">' + esc(b.appName) + '</div></div></div>' +
      '<div class="ca-bar">' + ic('shield', 15) + '<span>Signed in as <b>' + esc(BC_MEMBER.name) + '</b> · +91 ' + esc(BC_MEMBER.mobile) + ' · via Boche</span></div></div>' +
      '<div class="pad mt16"><div class="list">' + b.appMenu.map(function (m) {
        return '<button class="li" data-act="childItem" data-id="' + esc(m.title) + '"><span class="li-ic">' + ic(m.icon, 18) + '</span><div class="li-main"><div class="li-t">' + esc(m.title) + '</div><div class="li-s">' + esc(m.sub) + '</div></div><span class="li-chev">' + ic('chev', 18) + '</span></button>';
      }).join('') + '</div>' +
      '<div class="surface mt16" style="padding:4px 16px"><div class="kv"><span>Your ' + esc(b.short) + ' points</span><span>' + num(pointsOf(BC_MEMBER.id, b.id)) + '</span></div>' +
      '<div class="kv"><span>Tier</span><span>' + esc(curTier().name) + '</span></div></div>' +
      '<button class="btn btn-line mt16" data-go="home">' + ic('back', 16) + ' Back to Boche</button></div>';
  };

  /* ============================================================
     BOCHE TEA SHOP: bag → address (pincode first) → review & pay → done
     ============================================================ */
  function teaBag() { return ui.tea.qty; }
  function teaCount() { var n = 0, q = teaBag(); for (var k in q) n += q[k]; return n; }
  function teaItems() { return BC_TEA.packs.filter(function (p) { return teaBag()[p.id] > 0; }).map(function (p) { return { pack: p, qty: teaBag()[p.id] }; }); }
  function teaNumbers() { return teaItems().reduce(function (t, i) { return t + i.pack.numbers * i.qty; }, 0); }
  function teaSubtotal() { return teaItems().reduce(function (t, i) { return t + i.pack.price * i.qty; }, 0); }
  function teaWeight() { var g = teaItems().reduce(function (t, i) { return t + i.pack.grams * i.qty; }, 0); return g < 1000 ? g + ' g' : g / 1000 + ' kg'; }
  function teaLogistics() { return teaItems().reduce(function (t, i) { return t + i.pack.logistics * i.qty; }, 0); }
  function gst(amt, rate) { return Math.round(amt * rate) / 100; }
  /* GST is worked out only at checkout: tea at taxRate, logistics at logisticsTaxRate */
  function teaGst(sub, lg) { var t = gst(sub, BC_TEA.taxRate), l = gst(lg, BC_TEA.logisticsTaxRate); return { tea: t, log: l, total: Math.ceil(Math.round((t + l) * 100) / 100) }; }   /* GST payable is rounded up to the next whole rupee */
  function gstLine(tax, rate, what) { return '<div class="kv"><span>GST' + (what ? ' on ' + what : '') + ' @ ' + rate + '%</span><span>' + inr(tax) + '</span></div>'; }
  /* One GST row; the + opens the split between tea and logistics */
  function gstLines(g) {
    var exact = Math.round((g.tea + g.log) * 100) / 100, total = g.total != null ? g.total : exact, ro = Math.round((total - exact) * 100) / 100;
    return '<details class="gst"><summary class="kv"><span class="gst-l">GST<span class="gst-plus">' + ic('plus', 12) + '</span></span><span>' + inr(total) + '</span></summary>' +
      '<div class="gst-sub">' + gstLine(g.tea, BC_TEA.taxRate, 'tea') + gstLine(g.log, BC_TEA.logisticsTaxRate, 'logistics') +
      (ro > 0 ? '<div class="kv"><span>Rounded up</span><span>' + inr(ro) + '</span></div>' : '') + '</div></details>';
  }
  function teaAddrOk() { return addrOk(ui.tea); }
  function teaSteps(n) {
    return '<div class="tsteps">' + ['Bag', 'Address', 'Payment'].map(function (s, i) {
      return '<span class="' + (i < n ? 'done' : i === n ? 'on' : '') + '"><i>' + (i < n ? ic('check', 11) : i + 1) + '</i>' + s + '</span>';
    }).join('<b></b>') + '</div>';
  }
  /* Start checkout on the default saved address; with none saved, a blank form */
  function teaPrefill() {
    if (ui.tea.pick && (ui.tea.pick === 'new' || addrList().some(function (a) { return a.id === ui.tea.pick; }))) return;
    var def = addrDefault(), A = def ? addrFromSaved(def) : addrBlank();
    ui.tea.addr = A.addr; ui.tea.area = A.area; ui.tea.look = 'idle'; ui.tea.err = ''; ui.tea.pick = def ? def.id : 'new';
  }
  function teaAreaLine(a) { return (a.po && a.po !== a.district ? a.po + ', ' : '') + a.district + ', Kerala ' + a.pin; }

  function orderStatus(o) {
    var days = Math.floor((Date.now() - (o.ts || new Date(o.date).getTime())) / 864e5);
    return days >= 5 ? ['Delivered', 'ok'] : days >= 1 ? ['On the way', ''] : ['Order placed', ''];
  }
  function cardState(c) {
    if (!c.scratched) return { t: 'Not scratched yet', go: 'scratch/' + c.id, cta: 'Scratch' };
    if (!c.submitted) return { t: 'Not entered yet', go: 'scratch/' + c.id, cta: 'Enter' };
    var res = drawResults(c.drawDate);
    if (!res) return { t: c.included === false ? 'Not in ' + dayLabel(c.drawDate).toLowerCase() + '’s sealed list'
      : c.included ? 'In ' + dayLabel(c.drawDate).toLowerCase() + '’s sealed list · results ' + resultsTimeLabel(c.drawDate)
      : 'In ' + dayLabel(c.drawDate).toLowerCase() + '’s draw · ' + drawTimeLabel() };
    var won = res.filter(function (w) { return c.nos.indexOf(w.no) > -1; });
    if (!won.length) return { t: dayLabel(c.drawDate) + '’s draw · no win this time' };
    var amt = won.reduce(function (t, w) { return t + w.amount; }, 0), wn = won.map(function (w) { return w.no; });
    return c.claimed ? { t: inr(amt) + ' claim submitted', win: true, wn: wn, amount: amt }
      : { t: 'Won ' + inr(amt) + ' · ' + won[0].rank, win: true, wn: wn, amount: amt, claim: true };
  }

  /* One-word Lucky Draw result for an order: Won > To enter > Pending > Next time */
  function orderDraw(o) {
    var cards = o.cards || [], won = false, toEnter = false, pending = false;
    cards.forEach(function (c) {
      if (!c.submitted) { toEnter = true; return; }
      if (!drawResults(c.drawDate)) { pending = true; return; }
      if (cardState(c).win) won = true;
    });
    if (!cards.length) return ['—', 'plain'];
    return won ? ['Won', 'ok'] : toEnter ? ['To enter', 'warn'] : pending ? ['Pending', 'plain'] : ['Next time', 'plain'];
  }
  SCREENS['tea-orders'] = function () {
    var orders = teaOrders();
    return topbar('My orders', 'tea') + '<div class="pad tea-page">' +
      (orders.length ? '<div class="otable"><div class="ot-row ot-h"><span>#</span><span>Date</span><span>Order ID</span><span>Draw</span><span></span></div>' +
        orders.map(function (o, i) {
          var st = orderStatus(o), cards = o.cards || [], dr = orderDraw(o);
          return '<details class="ot-item"><summary class="ot-row"><span>' + (orders.length - i) + '</span><span>' + esc(o.date.replace(/ \d{4}$/, '')) + '</span><span>' + esc(o.id) + '</span><span><span class="badge ' + dr[1] + '">' + dr[0] + '</span></span>' + ic('chev', 14) + '</summary>' +
            '<div class="ot-body">' +
            '<div class="kv"><span>Status</span><span><span class="badge ' + st[1] + '">' + st[0] + '</span></span></div>' +
            o.items.map(function (it) { return '<div class="kv"><span>' + esc(it.size) + ' × ' + it.qty + '</span><span>' + inr(it.price * it.qty) + '</span></div>'; }).join('') +
            '<div class="kv"><span>Logistics</span><span>' + inr(o.logistics) + '</span></div>' +
            (o.gst ? gstLines(o.gst) : o.tax ? gstLine(o.tax, o.taxRate) : '') +
            '<div class="kv total"><span>Paid</span><span>' + inr(o.total) + '</span></div>' +
            '<div class="kv"><span>Deliver to</span><span class="ord-addr">' + esc(o.addr.house + ', ' + o.addr.street + ', ' + teaAreaLine({ po: o.area.po, district: o.area.district, pin: o.addr.pin })) + '</span></div>' +
            '<div class="kv"><span>Lucky Draw</span><a class="link" href="/my-numbers">' + cards.length + (cards.length === 1 ? ' card' : ' cards') + ' · ' + numsLabel(cards.reduce(function (t, c) { return t + c.nos.length; }, 0)) + '</a></div>' +
            cards.map(function (c) {
              var cs = cardState(c);
              return '<div class="kv ot-card' + (cs.win ? ' win' : '') + '"><span>' + (c.pack ? esc(c.pack) + ' card' : 'Card') + '</span><span>' +
                (cs.win ? ic('crown', 13) : '') + esc(cs.t) + (cs.go ? ' · <a class="link" href="/' + cs.go + '">' + cs.cta + '</a>' : '') +
                (cs.claim ? ' · <a class="link" href="/claim/' + c.id + '">Claim</a>' : '') + '</span></div>';
            }).join('') +
            '</div></details>';
        }).join('') + '</div>'
        : '<div class="surface sp-empty">' + ic('receipt', 18) + '<span>No orders yet</span></div>') + '</div>';
  };

  /* Grouped by day: date on the left; on the right a one-line summary, then a row per pack.
     When every pack that day has the same plain status it is said once in the summary, not on each row. */
  SCREENS['my-numbers'] = function () {
    var days = [];
    allCards().forEach(function (x) {
      var d = days.filter(function (g) { return g.date === x.o.date; })[0];
      if (!d) days.push(d = { date: x.o.date, items: [] });
      d.items.push(x);
    });
    return topbar('My lucky numbers', 'tea') + '<div class="pad tea-page">' +
      (days.length ? days.map(function (g) {
        var p = String(g.date).split(' '), st = g.items.map(function (x) { return cardState(x.c); }),
          same = st.every(function (q) { return !q.go && !q.win && q.t === st[0].t; }),
          cnt = g.items.reduce(function (t, x) { return t + x.c.nos.length; }, 0);
        return '<div class="mn-day"><div class="mn-date"><b>' + esc(p[0]) + '</b><span>' + esc(p[1] || '') + '</span><span>' + esc(p[2] || '') + '</span></div>' +
          '<div class="surface mn-list"><div class="mn-top"><span>' + numsLabel(cnt).replace('lucky ', '') + '</span>' + (same ? '<span class="mn-st">' + esc(st[0].t) + '</span>' : '') + '</div>' +
          g.items.map(function (x, k) {
            var c = x.c, q = st[k];
            return '<div class="mn-row' + (q.win ? ' win' : '') + '"><span class="mn-pk">' + (c.pack ? esc(c.pack) : 'Card') + '</span><div class="mn-body">' +
              (c.scratched ? '<div class="mn-nos">' + c.nos.map(function (no) { return '<span class="lno' + (q.wn && q.wn.indexOf(no) > -1 ? ' won' : '') + '">' + esc(no) + '</span>'; }).join('') + '</div>'
                : '<span class="li-s">' + numsLabel(c.nos.length) + ' under the foil</span>') +
              (same ? '' : '<div class="mn-st' + (q.claim ? ' mn-claim' : '') + '"><span>' + (q.win ? ic('crown', 13) : '') + esc(q.t) + '</span>' +
                (q.claim ? '<button class="btn btn-sm btn-gold" data-act="claimPrize" data-id="' + c.id + '">Claim</button>' : '') + '</div>') + '</div>' +
              (q.go ? '<a class="btn btn-sm btn-soft" href="/' + q.go + '">' + q.cta + '</a>' : '') + '</div>';
          }).join('') + '</div></div>';
      }).join('') : '<div class="surface sp-empty">' + ic('gift', 18) + '<span>Buy any tea pack to get lucky numbers</span></div>') + '</div>';
  };

  /* Every win in one table: #, Date, Type, Lucky No, Amount, Status. A win not yet claimed opens the claim page. */
  SCREENS['my-wins'] = function () {
    var rows = [];
    allCards().forEach(function (x) {
      var c = x.c, q = c.submitted && cardState(c); if (!q || !q.win) return;
      drawResults(c.drawDate).forEach(function (w) { if (c.nos.indexOf(w.no) > -1) rows.push({ c: c, w: w }); });
    });
    rows.sort(function (a, b) { return a.c.drawDate < b.c.drawDate ? 1 : -1; });
    function st(c) { return !c.claimed ? ['Claim', ''] : Date.now() - c.claimed.ts >= 864e5 ? ['Received', 'ok'] : ['Claimed', 'plain']; }
    return topbar('My wins', 'draw') + '<div class="pad tea-page">' +
      (rows.length ? '<div class="otable"><div class="wn-row ot-h"><span>#</span><span>Date</span><span>Type</span><span>Lucky No</span><span>Amount</span><span>Status</span></div>' +
        rows.map(function (r, i) {
          var s = st(r.c), d = new Date(r.c.drawDate + 'T12:00:00').toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
          return '<a class="wn-row wn-item" href="/claim/' + r.c.id + '"><span>' + (rows.length - i) + '</span><span>' + d + '</span><span>Tea</span><span>' + esc(r.w.no) + '</span><span>' + inr(r.w.amount) + '</span>' +
            '<span><span class="badge ' + s[1] + (s[0] === 'Claim' ? ' warn' : '') + '">' + s[0] + '</span></span></a>';
        }).join('') + '</div>'
        : '<div class="surface sp-empty">' + ic('crown', 18) + '<span>No wins yet. Your luck is coming</span></div>') + '</div>';
  };

  /* Claim a win: one page, a ready-made message with User ID, Invoice No and Lucky No, Submit at the bottom */
  SCREENS.claim = function (cid) {
    var x = cardById(cid), q = x && cardState(x.c);
    if (!x || !q || !q.win) return SCREENS['tea-orders']();
    var c = x.c, done = !!c.claimed, lucky = q.wn.join(', ');
    var rows = [['User ID', BC_MEMBER.id], ['Invoice No', x.o.id], ['Lucky No', lucky]];
    return '<div class="flow tea-page">' + topbar('Claim your prize', 'tea-orders') + '<div class="pad">' +
      '<div class="cl-hero">' + ic('crown', 26) + '<span>You won</span><b>' + inr(q.amount) + '</b></div>' +
      '<div class="field-l">Your claim</div>' +
      '<div class="surface cl-msg"><p>Hello Boche, I won the Lucky Draw and would like to claim my prize.</p>' +
        rows.map(function (r) { return '<div class="kv"><span>' + r[0] + '</span><span>' + esc(r[1]) + '</span></div>'; }).join('') + '</div>' +
      (done ? '<div class="cl-done">' + ic('check', 16) + '<span>Claim submitted · ref ' + esc(c.claimed.ref) + '. We’ll verify and pay you within 24 hours.</span></div>'
        : '<p class="cl-note">Details are filled in for you. Just submit.</p>') +
      '</div><div class="sticky-cta">' + (done ? '<button class="btn btn-soft" data-go="tea-orders">Back to orders</button>'
        : '<button class="btn btn-gold" data-act="claimSubmit" data-id="' + c.id + '">Submit claim</button>') + '</div></div>';
  };

  SCREENS.tea = function () {
    var t = curTier(), n = teaCount(), b = biz('tea');
    return '<div class="flow tea-page">' + topbar('Boche Tea', 'home') + '<div class="pad">' +
      '<a class="tea-ban" href="/draw"><span class="tn-art">' + ic('gift', 70) + '</span><span class="tn-k">' + ic('sparkle', 12) + 'Lucky Draw</span>' +
        '<span class="tn-t">Win up to <b>' + inr(BC_DRAW.prizes[0].amount) + '</b> every day</span><span class="tn-s">Every pack includes a scratch card</span></a>' +
      (function () {
        var seen = ui.teaSeen; setTimeout(function () { ui.teaSeen = true; }, 900);
        var best = BC_TEA.packs.slice().sort(function (x, y) { return x.price / x.numbers - y.price / y.numbers; })[0].id;
        return BC_TEA.packs.map(function (p, i) {
          var q = teaBag()[p.id];
          return '<div class="tea-pack' + (q ? ' on' : '') + (p.id === best ? ' best' : '') + (ui.teaSeen ? '' : ' tp-anim') + '" style="--i:' + i + '">' + (p.id === best ? '<span class="tp-flag">Best value</span>' : '') +
                        '<div class="tp-mid"><div class="tp-name">' + esc(p.size) + '</div><span class="tp-nos">' + ic('gift', 12) + numsLabel(p.numbers) + '</span></div>' +
            '<div class="tp-right"><div class="tp-price">' + inr(p.price) + '</div>' +
            (q ? '<div class="qty"><button data-act="teaQty" data-id="' + p.id + '" data-d="-1" aria-label="Remove one">' + ic('minus', 16) + '</button><b>' + q + '</b>' +
                '<button data-act="teaQty" data-id="' + p.id + '" data-d="1" aria-label="Add one"' + (q >= BC_TEA.maxQty ? ' disabled' : '') + '>' + ic('plus', 16) + '</button></div>'
              : '<button class="btn btn-gold tp-buy" data-act="teaQty" data-id="' + p.id + '" data-d="1">Buy</button>') + '</div></div>';
        }).join('');
      })() +
      '<p class="fine">Delivered across Kerala in ' + esc(BC_TEA.eta) + '. GST added at checkout.</p></div>' +
      '<div class="sticky-cta">' +
      '<div class="tea-bar"><div><div class="tb-k">' + (n ? n + (n > 1 ? ' packs' : ' pack') + ' · ' + numsLabel(teaNumbers()) : 'Choose a pack') + '</div><div class="tb-v">' + inr(teaSubtotal()) + '</div></div>' +
      '<button class="btn btn-gold" data-go="tea-address"' + (n ? '' : ' disabled') + '>Continue ' + ic('chev', 16) + '</button></div></div></div>';
  };


  /* ----- Shared address form (pincode first, Kerala only): Tea checkout and Profile ----- */
  function addrBlank() { return { addr: { pin: '', name: BC_MEMBER.name, house: '', street: '' }, area: null, look: 'idle', err: '', focusNext: false }; }
  function addrFromSaved(sv) {
    return { addr: JSON.parse(JSON.stringify(sv.addr)), area: { district: sv.area.district, places: sv.area.po ? [sv.area.po] : [], po: sv.area.po }, look: 'idle', err: '', focusNext: false };
  }
  function addrToSaved(A) { return { addr: JSON.parse(JSON.stringify(A.addr)), area: { po: A.area.po, district: A.area.district } }; }
  function addrOk(A) { var a = A.addr; return !!(A.area && a.name.trim().length > 1 && a.house.trim() && a.street.trim()); }
  function addrForm(A) {
    var a = A.addr, area = A.area, look = A.look;
    var res = look === 'loading' ? '<div class="pin-res"><span class="mini-spin"></span>Finding your area…</div>'
      : look === 'err' ? '<div class="err-text">' + esc(A.err) + '</div>'
      : area ? '<div class="pin-res ok">' + ic('pin', 16) + '<span>' + esc(area.district) + ', Kerala</span></div>' +
          (area.places.length > 1 ? '<div class="field-l">Post office / locality</div><div class="chips">' + area.places.map(function (p) {
            return '<button class="chip' + (p === area.po ? ' on' : '') + '" data-act="addrPo" data-id="' + esc(p) + '">' + esc(p) + '</button>';
          }).join('') + '</div>' : '')
      : '<p class="fine" style="margin-top:8px">We deliver anywhere in Kerala. Your area and district fill in automatically.</p>';
    return '<div class="field-l">Pincode</div>' +
      '<input id="adPin" class="input pin-input" inputmode="numeric" maxlength="6" placeholder="6-digit pincode" autocomplete="postal-code" value="' + esc(a.pin) + '">' +
      '<div>' + res + '</div>' +
      (area ? '<div class="field-l">Full name</div><input id="adName" class="input" autocomplete="name" value="' + esc(a.name) + '">' +
        '<div class="field-l">House name / no.</div><input id="adHouse" class="input" autocomplete="address-line1" placeholder="e.g. Rose Villa, 12/345" value="' + esc(a.house) + '">' +
        '<div class="field-l">Street / road</div><input id="adStreet" class="input" autocomplete="address-line2" placeholder="e.g. Seaport–Airport Road" value="' + esc(a.street) + '">' +
        '<div class="addr-auto">' + ic('pin', 15) + '<span>' + esc(teaAreaLine({ po: area.po, district: area.district, pin: a.pin })) + '</span></div>' : '');
  }
  /* Wires the form on the current screen; onDone runs on Enter in the last field once valid */
  function wireAddr(A, route, onDone) {
    var pin = $('adPin'), a = A.addr;
    pin.addEventListener('input', function () {
      pin.value = pin.value.replace(/\D/g, '').slice(0, 6);
      if (pin.value === a.pin) return;
      a.pin = pin.value;
      var had = A.area || A.look !== 'idle';
      A.area = null; A.look = 'idle';
      if (a.pin.length === 6) pinLookup(A, a.pin, route);
      else if (had) { rerender(); var p = $('adPin'); p.focus(); p.setSelectionRange(p.value.length, p.value.length); }
    });
    [['adName', 'name'], ['adHouse', 'house'], ['adStreet', 'street']].forEach(function (f) {
      var el = $(f[0]); if (!el) return;
      el.addEventListener('input', function () { a[f[1]] = el.value; $('adGo').disabled = !addrOk(A); });
      el.addEventListener('keydown', function (e) { if (e.key === 'Enter') { var nx = { adName: 'adHouse', adHouse: 'adStreet' }[f[0]]; if (nx) $(nx).focus(); else if (addrOk(A)) onDone(); } });
    });
    if (!A.area) { if (A.look !== 'loading') pin.focus(); }
    else if (A.focusNext) { A.focusNext = false; var h = $('adHouse'); if (h) h.focus(); }
  }
  /* Kerala only: prefix check first, then India Post lookup for district + post offices.
     If the lookup service can't be reached, fall back to the district from the prefix. */
  function pinLookup(A, pin, route) {
    var n = +pin, cache = ui.pinCache;
    function done() { if (parse().name === route) rerender(); }
    function fail(msg) { A.look = 'err'; A.err = msg; done(); }
    function ok(district, places) { A.look = 'idle'; A.area = { district: district, places: places, po: places[0] || '' }; A.focusNext = true; done(); }
    if (n < 670000 || n > 695999) return fail('We deliver only within Kerala right now (pincodes 670001 – 695xxx).');
    var cached = cache[pin]; if (cached) return cached.err ? fail(cached.err) : ok(cached.district, cached.places);
    A.look = 'loading'; done();
    var fallback = function () { var d = BC_TEA.districts[pin.slice(0, 3)]; return d ? ok(d, []) : fail('We couldn’t find this pincode in Kerala.'); };
    var ctl = window.AbortController ? new AbortController() : null, tm = setTimeout(function () { if (ctl) ctl.abort(); }, 6000);
    fetch(BC_TEA.pincodeApi + pin, ctl ? { signal: ctl.signal } : {}).then(function (r) { return r.json(); }).then(function (j) {
      clearTimeout(tm);
      if (A.addr.pin !== pin) return;
      var pos = (j && j[0] && j[0].Status === 'Success' && j[0].PostOffice) || [];
      if (!pos.length) { cache[pin] = { err: 'That pincode doesn’t exist. Please check it.' }; return fail(cache[pin].err); }
      var kl = pos.filter(function (p) { return p.State === 'Kerala'; });
      if (!kl.length) { cache[pin] = { err: 'This pincode is in ' + pos[0].State + '. We deliver only within Kerala.' }; return fail(cache[pin].err); }
      var del = kl.filter(function (p) { return p.DeliveryStatus === 'Delivery'; }), use = del.length ? del : kl;
      cache[pin] = { district: kl[0].District, places: use.map(function (p) { return p.Name; }) };
      ok(cache[pin].district, cache[pin].places);
    }).catch(function () { clearTimeout(tm); if (A.addr.pin === pin) fallback(); });
  }

  SCREENS['tea-address'] = function () {
    var l = addrList(), picking = l.length && ui.tea.pick !== 'new';
    return '<div class="flow tea-page">' + topbar('Delivery address', 'tea') + '<div class="pad">' + teaSteps(1) +
      (picking ? '<div class="field-l">Deliver to</div>' + l.map(function (a) {
          return '<button class="method' + (ui.tea.pick === a.id ? ' on' : '') + '" data-act="teaPickAddr" data-id="' + a.id + '"><span class="radio"></span><span class="li-main">' +
            '<span class="li-t" style="display:block">' + esc(a.label || 'Home') + ' · ' + esc(a.addr.name) + '</span><span class="li-s" style="display:block">' + esc(addrLine(a)) + '</span></span></button>';
        }).join('') + '<button class="link mt8" data-act="teaNewAddr">' + ic('plus', 13) + ' Deliver to a new address</button>'
        : (l.length ? '<button class="link mt8" data-act="teaPickAddr" data-id="' + addrDefault().id + '">' + ic('back', 13) + ' Choose a saved address</button>' : '') + addrForm(ui.tea)) +
      '</div><div class="sticky-cta"><button class="btn btn-gold" id="adGo" data-go="tea-pay"' + (teaAddrOk() ? '' : ' disabled') + '>Continue to payment</button></div></div>';
  };
  AFTER['tea-address'] = function () { if ($('adPin')) wireAddr(ui.tea, 'tea-address', function () { go('tea-pay'); }); };

  /* ----- Profile: saved delivery address ----- */
  SCREENS.address = function () {
    var A = ui.addrEd;
    return '<div class="flow">' + topbar(A.id ? 'Edit address' : 'Add address', 'addresses') + '<div class="pad">' +
      '<div class="field-l" style="margin-top:4px">Save as</div><div class="chips">' + ADDR_LABELS.map(function (l) {
        return '<button class="chip' + (A.label === l ? ' on' : '') + '" data-act="addrLabel" data-id="' + l + '">' + l + '</button>';
      }).join('') + '</div>' + addrForm(A) +
      '</div><div class="sticky-cta"><button class="btn btn-gold" id="adGo" data-act="saveAddress"' + (addrOk(A) ? '' : ' disabled') + '>Save address</button></div></div>';
  };
  AFTER.address = function () { wireAddr(ui.addrEd, 'address', function () { ACTIONS.saveAddress(); }); };

  /* ----- Saved delivery addresses (many, one default) ----- */
  function addrList() { var d = dyn(BC_MEMBER.id); return d.addresses = d.addresses || []; }
  function addrDefault() { var d = dyn(BC_MEMBER.id), l = addrList(); return l.filter(function (a) { return a.id === d.defaultAddr; })[0] || l[0]; }
  function addrLine(sv) { return sv.addr.house + ', ' + sv.addr.street + ', ' + teaAreaLine({ po: sv.area.po, district: sv.area.district, pin: sv.addr.pin }); }
  /* Adds or updates; the same house + street + pincode is treated as the same address */
  function addrUpsert(sv) {
    var l = addrList(), d = dyn(BC_MEMBER.id);
    var same = l.filter(function (a) { return a.id === sv.id || (a.addr.pin === sv.addr.pin && a.addr.house.trim().toLowerCase() === sv.addr.house.trim().toLowerCase() && a.addr.street.trim().toLowerCase() === sv.addr.street.trim().toLowerCase()); })[0];
    if (same) { sv.id = same.id; l[l.indexOf(same)] = sv; }
    else { sv.id = 'A' + Date.now().toString(36); l.push(sv); }
    if (!d.defaultAddr || !l.some(function (a) { return a.id === d.defaultAddr; })) d.defaultAddr = sv.id;
    save(); return sv;
  }
  var ADDR_LABELS = ['Home', 'Work', 'Other'];

  SCREENS.addresses = function () {
    var l = addrList(), def = addrDefault();
    return '<div class="flow">' + topbar('Delivery addresses', 'profile') + '<div class="pad">' +
      (l.length ? l.map(function (a) {
        var isDef = def && a.id === def.id;
        return '<div class="surface adr' + (isDef ? ' def' : '') + '"><div class="adr-h"><span class="badge plain">' + ic(a.label === 'Work' ? 'doc' : 'home', 11) + esc(a.label || 'Home') + '</span>' +
          (isDef ? '<span class="badge ok">Default</span>' : '') + '</div>' +
          '<div class="li-t">' + esc(a.addr.name) + '</div><div class="li-s">' + esc(addrLine(a)) + '</div>' +
          '<div class="adr-act"><button class="link" data-act="editAddress" data-id="' + a.id + '">Edit</button>' +
          (isDef ? '' : '<button class="link" data-act="defAddress" data-id="' + a.id + '">Set as default</button>') +
          '<button class="link danger" data-act="delAddress" data-id="' + a.id + '">Delete</button></div></div>';
      }).join('') : '<div class="surface sp-empty">' + ic('pin', 18) + '<span>No saved addresses yet</span></div>') +
      '</div><div class="sticky-cta"><button class="btn btn-gold" data-act="editAddress" data-id="new">' + ic('plus', 16) + 'Add address</button></div></div>';
  };

  /* ----- Email: verify with a code; changing it needs a fresh verification ----- */
  SCREENS.email = function () {
    var e = ui.em, p = dyn(BC_MEMBER.id).profile || {};
    if (e.step === 'code') {
      return topbar('Verify email', 'email') + '<div class="auth">' +
        '<h1>Enter the code</h1><p class="lead">Sent to <b>' + esc(e.email) + '</b> · <a class="link" href="javascript:void(0)" data-act="emailEdit">Change</a></p>' +
        '<div class="otp mt16" id="otp">' + otpBoxes(BC_SECURITY.emailOtpLength) + '</div><div class="err-text" id="otpErr"></div>' +
        '<div class="demo-hint">Demo email code: <b>' + esc(BC_BRAND.demoEmailOtp) + '</b></div>' +
        '<button class="btn btn-gold mt16" data-otp-btn data-act="emailVerify" disabled>Verify email</button>' +
        '<p class="fine center mt12" id="resend"></p></div>';
    }
    var same = e.email.trim().toLowerCase() === String(p.email || '').toLowerCase(), done = same && p.emailVerified;
    return '<div class="flow">' + topbar('Email', 'profile') + '<div class="auth">' +
      '<div class="field-l" style="margin-top:4px">Email address</div>' +
      '<input id="emIn" class="input" type="email" inputmode="email" autocomplete="email" value="' + esc(e.email) + '">' +
      '<div class="em-st ' + (done ? 'ok' : '') + '" id="emSt">' + (done ? ic('check', 14) + 'Verified' : same ? 'Not verified yet' : 'New email · needs verification') + '</div>' +
      '<p class="fine">Used to confirm it’s you when you sign in on a new phone.</p></div>' +
      '<div class="sticky-cta"><button class="btn btn-gold" id="emGo" data-act="emailSend"' + (done || !emailOk(e.email) ? ' disabled' : '') + '>' + (done ? 'Email verified' : 'Send verification code') + '</button></div></div>';
  };
  function emailOk(v) { return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(String(v).trim()); }
  AFTER.email = function () {
    if (ui.em.step === 'code') { wireOtp(function () { ACTIONS.emailVerify(); }); return; }
    var inp = $('emIn'), p = dyn(BC_MEMBER.id).profile || {};
    inp.addEventListener('input', function () {
      ui.em.email = inp.value;
      var same = inp.value.trim().toLowerCase() === String(p.email || '').toLowerCase(), done = same && p.emailVerified;
      $('emSt').className = 'em-st ' + (done ? 'ok' : '');
      $('emSt').innerHTML = done ? ic('check', 14) + 'Verified' : same ? 'Not verified yet' : 'New email · needs verification';
      $('emGo').disabled = done || !emailOk(inp.value); $('emGo').textContent = done ? 'Email verified' : 'Send verification code';
    });
  };


  SCREENS['tea-pay'] = function () {
    var a = ui.tea.addr, area = ui.tea.area, sub = teaSubtotal(), lg = teaLogistics(), g = teaGst(sub, lg), tot = Math.round((sub + lg + g.total) * 100) / 100, cards = teaCount(), nos = teaNumbers();
    return '<div class="flow tea-page">' + topbar('Review & pay', 'tea-address') + '<div class="pad">' + teaSteps(2) +
      '<div class="surface pay-card"><div class="pc-h"><span>Deliver to</span><button class="link" data-go="tea-address">Change</button></div>' +
      '<div class="li-t">' + esc(a.name) + '</div><div class="li-s">' + esc(a.house) + ', ' + esc(a.street) + '<br>' + esc(teaAreaLine({ po: area.po, district: area.district, pin: a.pin })) + '</div>' +
      '<div class="li-s">+91 ' + esc(BC_MEMBER.mobile) + '</div></div>' +
      '<div class="surface pay-card"><div class="pc-h"><span>Your order</span><button class="link" data-go="tea">Edit</button></div>' +
      teaItems().map(function (i) { return '<div class="kv"><span>' + esc(BC_TEA.product.name) + ' · ' + esc(i.pack.size) + ' × ' + i.qty + '</span><span>' + inr(i.pack.price * i.qty) + '</span></div>'; }).join('') +
      (teaItems().length > 1 ? '<div class="kv"><span>Tea subtotal</span><span>' + inr(sub) + '</span></div>' : '') +
      '<div class="kv"><span>Logistics · ' + teaWeight() + ' to ' + esc(area.district) + '</span><span>' + inr(lg) + '</span></div>' +
      gstLines(g) +
      '<div class="kv total"><span>Total payable</span><span>' + inr(tot) + '</span></div></div>' +
      '<div class="earn-note">' + ic('gift', 16) + '<span><b>' + cards + (cards > 1 ? ' scratch cards' : ' scratch card') + '</b> with ' + numsLabel(nos) + ' for the Lucky Draw</span></div>' +
      '<p class="fine center">Arrives in ' + esc(BC_TEA.eta) + '</p></div>' +
      '<div class="sticky-cta"><button class="btn btn-gold" data-act="teaPay">' + ic('lock', 16) + 'Pay ' + inr(tot) + '</button></div></div>';
  };

  SCREENS['tea-done'] = function (id) {
    var o = teaOrders().filter(function (x) { return x.id === id; })[0];
    if (!o) return SCREENS.home();
    return '<div class="auth"><div class="verified-hero"><div class="big-check">' + ic('check', 36) + '</div>' +
      '<h1>Order placed</h1><p class="lead">Arriving in ' + esc(BC_TEA.eta) + ' at ' + esc(o.area.po || o.area.district) + '.</p></div>' +
      '<div class="surface mt16" style="padding:4px 16px">' +
      '<div class="kv"><span>Order</span><span>' + esc(o.id) + '</span></div>' +
      '<div class="kv"><span>Paid</span><span>' + inr(o.total) + '</span></div>' +
      '</div>' +
      '<p class="fine center mt12">We’ll send delivery updates to +91 ' + esc(BC_MEMBER.mobile) + '.</p>' +
      (function (open) {
        var n = (o.cards || []).length, nos = (o.cards || []).reduce(function (t, c) { return t + c.nos.length; }, 0);
        return open ? '<div class="sc-promo">' + ic('gift', 22) + '<div><b>You’ve won ' + (n > 1 ? n + ' scratch cards' : 'a scratch card') + '!</b><span>' + numsLabel(nos) + ' for today’s ' + inr(BC_DRAW.prizes[0].amount) + ' Lucky Draw.</span></div></div>' +
          '<button class="btn btn-gold mt16" data-go="scratch/' + open.id + '">' + ic('sparkle', 18) + 'Scratch now</button><button class="btn-text" data-go="home">Back to Home</button></div>'
          : '<button class="btn btn-gold mt24" data-go="home">' + ic('home', 18) + 'Back to Home</button></div>';
      })((o.cards || []).filter(function (c) { return !c.scratched; })[0]);
  };

  /* ============================================================
     LUCKY DRAW: scratch card per Tea order → submit number → daily 9 PM draw
     Prototype: shared localStorage stands in for the server.
     ============================================================ */
  function dayKey(d) { d = d || new Date(); return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2); }
  function dayShift(key, n) { var d = new Date(key + 'T12:00:00'); d.setDate(d.getDate() + n); return dayKey(d); }
  function dayLabel(key) {
    var t = dayKey();
    if (key === t) return 'Today';
    if (key === dayShift(t, -1)) return 'Yesterday';
    if (key === dayShift(t, 1)) return 'Tomorrow';
    return new Date(key + 'T12:00:00').toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' });
  }
  function drawTimeLabel() { var h = BC_DRAW.drawHour; return (h % 12 || 12) + (h < 12 ? ' AM' : ' PM'); }
  /* Lucky numbers are issued by the server after a confirmed payment (backend/app/ticketing.py) */
  function drawWinnerCount() { return BC_DRAW.prizes.reduce(function (t, p) { return t + p.count; }, 0); }
  /* Published results come from the server (/api/public/days): the ten Winners the draw engine picked from
     the sealed list and drand. A day with no published result returns null. There is no simulated draw. */
  var RESULTS = {}, PUBLIC_DAYS = null, resultsAt = 0;
  function myNumbers() { var s = {}; allCards().forEach(function (x) { x.c.nos.forEach(function (n) { s[n] = 1; }); }); return s; }
  function drawResults(key) {
    var list = RESULTS[key]; if (!list) return null;
    var mine = myNumbers();
    var cardOf = {}; allCards().forEach(function (x) { x.c.nos.forEach(function (no) { cardOf[no] = x.c; }); });
    return list.map(function (w, i) { var n = +w.rank || i + 1; return { card: cardOf[w.ticket] || null, place: n, rank: n + ({ 1: 'st', 2: 'nd', 3: 'rd' }[n] || 'th') + ' prize', amount: w.amount, no: w.ticket, name: w.name, mob: w.mobile, member: mine[w.ticket] ? BC_MEMBER.id : null }; });
  }
  /* When a closed day's results go public: 8:30 PM IST, or right after the draw if an Admin ran it early (Skip) */
  function publishAt(key) {
    var d = (PUBLIC_DAYS || []).filter(function (x) { return x.label === key; })[0];
    return d ? new Date(d.publishNotBefore) : new Date(key + 'T20:30:00+05:30');
  }
  function resultsTimeLabel(key) { return istTime(publishAt(key).toISOString()).toUpperCase(); }
  function refreshResults(force) {
    if (!force && Date.now() - resultsAt < 15000) return Promise.resolve();
    resultsAt = Date.now();
    var before = JSON.stringify(RESULTS);
    return BCAPI.get('/public/days').then(function (days) {
      var next = {}; days.forEach(function (d) { if (d.winners) next[d.label] = d.winners; });
      RESULTS = next; PUBLIC_DAYS = days;
      if (JSON.stringify(RESULTS) !== before && (ORDER_SCREENS[parse().name] || parse().name === 'verify-draw') && parse().name !== 'scratch') rerender();
    }).catch(function () {});
  }
  /* Every tea pack bought = one scratch card; the card carries that pack's count of lucky numbers */
  function allCards() {
    var out = [];
    teaOrders().forEach(function (o) { (o.cards || []).forEach(function (c) { out.push({ o: o, c: c }); }); });
    return out;
  }
  /* Orders, cards, lucky numbers, entries, inclusion in the sealed list and claims all come from the server */
  var ORDERS = null, ordersAt = 0;
  var ORDER_SCREENS = { 'tea-orders': 1, 'tea-done': 1, 'my-numbers': 1, 'my-wins': 1, draw: 1, scratch: 1, claim: 1 };
  function teaOrders() { return ORDERS || []; }
  function fromServerOrder(o) {
    function r(p) { return p / 100; }
    var d = o.delivery || {};
    return {
      id: o.id, ts: o.ts, date: new Date(o.ts).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }),
      items: o.items.map(function (i) { return { size: i.size, qty: i.qty, price: r(i.unitPricePaise) }; }),
      tea: r(o.subtotalPaise), logistics: r(o.logisticsPaise), gst: { tea: r(o.teaGstPaise), log: r(o.logisticsGstPaise), total: r(o.gstPaise) },
      tax: r(o.gstPaise), taxRate: o.teaGstRate, total: r(o.totalPaise),
      addr: { pin: d.pin, name: d.name, house: d.house, street: d.street }, area: { po: d.po, district: d.district },
      cards: o.cards.map(function (c) {
        return { id: c.id, pack: c.size, nos: c.numbers, scratched: c.scratched, submitted: !!c.entered, drawDate: c.drawDay || null, included: c.included, claimed: c.claim || null };
      })
    };
  }
  function setOrders(list) { ORDERS = list.map(fromServerOrder); ordersAt = Date.now(); }
  /* Fetch my orders; re-draw the screen only if something changed and the member isn't mid-scratch */
  function refreshOrders(force) {
    if (!SES.authed || (!force && Date.now() - ordersAt < 10000)) return Promise.resolve();
    ordersAt = Date.now();
    var before = JSON.stringify(ORDERS);
    return BCAPI.get('/me/orders').then(function (list) {
      setOrders(list);
      if (JSON.stringify(ORDERS) !== before && ORDER_SCREENS[parse().name] && parse().name !== 'scratch') rerender();
    }).catch(function (e) { if (e.status === 401) ACTIONS.logout(); });
  }
  function markScratched(cid) { BCAPI.post('/cards/' + encodeURIComponent(cid) + '/scratch').catch(function () {}); }
  function cardById(cid) { return allCards().filter(function (x) { return x.c.id === cid; })[0]; }
  function nextDrawKey() { return new Date().getHours() < BC_DRAW.drawHour ? dayKey() : dayShift(dayKey(), 1); }
  function numsLabel(n) { return n === 1 ? '1 lucky number' : n + ' lucky numbers'; }

  /* What sits under the card: hint → (once partly scratched) Enter button → entered / next card */
  function scratchBody(x) {
    var c = x.c, cards = x.o.cards, i = cards.indexOf(c), next = cards.slice(i + 1).concat(cards.slice(0, i)).filter(function (k) { return !k.submitted; })[0];
    return !c.scratched
      ? '<p class="sc-hint">' + ic('sparkle', 15) + 'Scratch to reveal your ' + (c.nos.length > 1 ? c.nos.length + ' numbers' : 'lucky number') + '</p>'
      : !c.submitted
        ? '<button class="btn btn-gold mt16" data-act="drawSubmit" data-id="' + c.id + '">' + ic('gift', 18) + 'Enter ' + esc(dayLabel(nextDrawKey()).toLowerCase()) + '’s Lucky Draw</button>' +
          '<p class="fine center">' + (c.nos.length > 1 ? 'All ' + c.nos.length + ' numbers go in · ' : '') + 'Draw at ' + drawTimeLabel() + '</p>'
        : '<div class="sc-luck"><span class="sl-ic">' + ic('sparkle', 22) + '</span>' +
            '<h2>Good luck, ' + esc(BC_MEMBER.firstName) + '!</h2>' +
            '<p>' + (c.nos.length > 1 ? 'All ' + c.nos.length + ' numbers are' : 'Your number is') + ' in <b>' + esc(dayLabel(c.drawDate).toLowerCase()) + '’s Lucky Draw</b>.</p>' +
            '<div class="sl-sms">' + ic('phone', 15) + '<span>Results at ' + drawTimeLabel() + '. If you win, we’ll SMS <b class="nowrap">+91 ' + esc(BC_MEMBER.mobile) + '</b></span></div></div>' +
          (next ? '<button class="btn btn-gold mt16" data-go="scratch/' + next.id + '">Next card (' + (cards.indexOf(next) + 1) + ' of ' + cards.length + ')</button>'
            : '<button class="btn btn-gold mt16" data-go="draw">See Lucky Draw</button>');
  }
  /* Welcome splash after a verified venue check-in: access granted, with a short fanfare (Web Audio) */
  function playWelcome() {
    if (!S.notif.sound) return;
    try {
      var AC = window.AudioContext || window.webkitAudioContext; if (!AC) return;
      var ac = playWelcome.ac = playWelcome.ac || new AC(), t0 = ac.currentTime + .03, out = ac.createGain();
      if (ac.state === 'suspended') ac.resume();
      out.gain.value = .2; out.connect(ac.destination);
      function tone(f, at, dur, type, vol, attack) {
        var o = ac.createOscillator(), g = ac.createGain();
        o.type = type; o.frequency.value = f;
        g.gain.setValueAtTime(0, at); g.gain.linearRampToValueAtTime(vol, at + (attack || .015)); g.gain.exponentialRampToValueAtTime(.0001, at + dur);
        o.connect(g); g.connect(out); o.start(at); o.stop(at + dur + .05);
      }
      /* 1. door unlocking: two short wooden clicks */
      tone(180, t0, .07, 'square', .5); tone(120, t0 + .11, .09, 'square', .6);
      /* 2. whoosh: filtered noise sweeping up as the splash opens */
      var len = ac.sampleRate * 1.1, buf = ac.createBuffer(1, len, ac.sampleRate), d = buf.getChannelData(0);
      for (var i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / len);
      var ns = ac.createBufferSource(), bp = ac.createBiquadFilter(), ng = ac.createGain();
      ns.buffer = buf; bp.type = 'bandpass'; bp.Q.value = 1.2; bp.frequency.setValueAtTime(300, t0 + .2); bp.frequency.exponentialRampToValueAtTime(4200, t0 + 1);
      ng.gain.setValueAtTime(0, t0 + .2); ng.gain.linearRampToValueAtTime(.5, t0 + .6); ng.gain.exponentialRampToValueAtTime(.001, t0 + 1.25);
      ns.connect(bp); bp.connect(ng); ng.connect(out); ns.start(t0 + .2);
      /* 3. warm welcome chord swelling in */
      [261.63, 329.63, 392, 493.88, 523.25].forEach(function (f) { tone(f, t0 + .45, 2.6, 'sine', .22, .5); tone(f / 2, t0 + .45, 2.6, 'triangle', .1, .6); });
      /* 4. bell arpeggio sparkle on top */
      [1046.5, 1318.5, 1568, 2093, 2637].forEach(function (f, i) { tone(f, t0 + .95 + i * .11, 1.1, 'sine', .2); tone(f * 2, t0 + .95 + i * .11, .5, 'sine', .05); });
    } catch (e) {}
    try { if (navigator.vibrate) navigator.vibrate([30, 60, 30, 60, 90]); } catch (e) {}
  }
  function showWelcome(o, b, need) {
    var old = $('wx'); if (old) old.remove();
    var el = document.createElement('div');
    el.id = 'wx'; el.className = 'wx'; el.setAttribute('role', 'dialog'); el.setAttribute('aria-label', 'Welcome to the Boche experience');
    el.innerHTML = '<div class="wx-rays"></div><div class="wx-glow"></div><i class="wx-ring r1"></i><i class="wx-ring r2"></i><i class="wx-ring r3"></i>' + confetti() +
      '<div class="wx-body"><div class="wx-photo">' + photoTag('wx-img') + '<span class="wx-check">' + ic('check', 20) + '</span></div>' +
      '<div class="wx-k">' + ic('shield', 13) + 'Access granted</div>' +
      '<h2 class="wx-t"><span>Welcome,</span><b>' + esc(BC_MEMBER.firstName) + '</b></h2>' +
      '<p class="wx-s">to the Boche experience</p>' +
      '<div class="wx-card"><div class="wx-r"><span class="wx-ic">' + ic(b.icon, 16) + '</span><div><b>' + esc(o.name) + '</b><small>' + esc(o.checkinLabel) + ' confirmed at ' + esc(timeLabel()) + '</small></div></div>' +
      (need ? '<div class="wx-r"><span class="wx-ic">' + ic('check', 16) + '</span><div><b>Age verified ' + need + '+</b><small>One-time check done</small></div></div>' : '') +
      '<div class="wx-r"><span class="wx-ic">' + ic('sparkle', 16) + '</span><div><b>Earn ' + esc(b.short) + ' points</b><small>Show your card when you pay your bill</small></div></div></div>' +
      '<button class="btn btn-gold wx-go" data-act="wxClose">Enjoy your visit</button></div>';
    $('device').appendChild(el);
    playWelcome();
  }
  /* Soft gold chime for the Lucky Draw entry: a rising C-major arpeggio with a sparkle on top, made with Web Audio */
  function playChime() {
    if (!S.notif.sound) return;
    try {
      var AC = window.AudioContext || window.webkitAudioContext; if (!AC) return;
      var ac = playChime.ac = playChime.ac || new AC(), t0 = ac.currentTime + .02, out = ac.createGain();
      if (ac.state === 'suspended') ac.resume();
      out.gain.value = .16; out.connect(ac.destination);
      function tone(f, at, dur, type, vol) {
        var o = ac.createOscillator(), g = ac.createGain();
        o.type = type; o.frequency.value = f;
        g.gain.setValueAtTime(0, at); g.gain.linearRampToValueAtTime(vol, at + .015); g.gain.exponentialRampToValueAtTime(.0001, at + dur);
        o.connect(g); g.connect(out); o.start(at); o.stop(at + dur + .05);
      }
      [523.25, 659.25, 783.99, 1046.5].forEach(function (f, i) { tone(f, t0 + i * .09, .9, 'sine', 1); tone(f * 2, t0 + i * .09, .5, 'triangle', .18); });
      [2093, 2637, 3136].forEach(function (f, i) { tone(f, t0 + .42 + i * .06, .35, 'sine', .22); });
    } catch (e) {}
  }
  function confetti() {
    var cols = ['#D9B45A', '#F5E2A8', '#8C6420', '#C9A04A', '#2F7A4C', '#FFF6DD'], h = '';
    for (var i = 0; i < 28; i++) h += '<i style="left:' + Math.round(Math.random() * 100) + '%;background:' + cols[i % cols.length] + ';animation-delay:' + (Math.random() * .5).toFixed(2) + 's;animation-duration:' + (1.6 + Math.random() * 1.2).toFixed(2) + 's;transform:rotate(' + Math.round(Math.random() * 360) + 'deg)"></i>';
    return '<div class="confetti" aria-hidden="true">' + h + '</div>';
  }
  SCREENS.scratch = function (cid) {
    var x = cardById(cid); if (!x) return SCREENS.draw();
    var c = x.c, n = c.nos.length, cards = x.o.cards;
    return '<div class="flow">' + topbar('Lucky Draw', 'home') + '<div class="pad">' +
      '<p class="sc-lead">' + (cards.length > 1 ? '<b>Card ' + (cards.indexOf(c) + 1) + ' of ' + cards.length + '</b> · ' : '') + 'Win up to <b>' + inr(BC_DRAW.prizes[0].amount) + '</b> today</p>' +
      '<div class="scard n' + (n === 1 ? 1 : n <= 3 ? 3 : 12) + '" id="scard"><div class="sc-face"><span class="sc-k">' + (n === 1 ? 'Your lucky number' : 'Your ' + n + ' lucky numbers') + '</span>' +
        '<div class="sc-nos">' + c.nos.map(function (no) { return '<span class="sc-no">' + esc(no) + '</span>'; }).join('') + '</div>' +
        '<span class="sc-s">' + (c.pack ? esc(c.pack) + ' pack · ' : '') + esc(x.o.date) + '</span></div>' +
        (c.submitted ? '<span class="sc-stamp">' + ic('check', 13) + 'Entered</span>' : '') +
        (c.scratched ? '' : '<canvas id="scCanvas" aria-hidden="true"></canvas><button class="sc-reveal" data-act="scratchReveal" data-id="' + c.id + '">Reveal without scratching</button>') + '</div>' +
      (ui.justEntered === c.id ? confetti() : '') +
      '<div id="scBody">' + scratchBody(x) + '</div></div>' +
      (c.submitted ? '' : '<div class="sticky-cta"><button class="btn-text" data-go="draw">Later</button></div>') + '</div>';
  };
  AFTER.scratch = function (id) {
    var cv = $('scCanvas'); if (!cv) return;
    var box = $('scard').getBoundingClientRect(), dpr = window.devicePixelRatio || 1, ctx = cv.getContext('2d'), w = box.width, h = box.height;
    cv.width = w * dpr; cv.height = h * dpr; ctx.scale(dpr, dpr);
    var g = ctx.createLinearGradient(0, 0, w, h);
    g.addColorStop(0, '#8C6420'); g.addColorStop(.35, '#D9B45A'); g.addColorStop(.5, '#F5E2A8'); g.addColorStop(.7, '#C9A04A'); g.addColorStop(1, '#8C6420');
    ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = 'rgba(255,255,255,.18)'; ctx.lineWidth = 1;
    for (var x = -h; x < w; x += 10) { ctx.beginPath(); ctx.moveTo(x, h); ctx.lineTo(x + h, 0); ctx.stroke(); }
    ctx.fillStyle = 'rgba(46,33,8,.78)'; ctx.textAlign = 'center';
    ctx.font = '700 13px "DM Sans", sans-serif'; ctx.fillText('B O C H E . C L U B   ·   L U C K Y   D R A W', w / 2, h / 2 - 16);
    ctx.font = '600 22px "Playfair Display", serif'; ctx.fillText('Scratch here', w / 2, h / 2 + 18);
    ctx.globalCompositeOperation = 'destination-out';
    var down = false, last = null, moves = 0, finished = false, seen = false;
    function pt(e) { var r = cv.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; }
    function scratch(p) {
      ctx.strokeStyle = '#000'; ctx.lineWidth = 36; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
      ctx.beginPath(); ctx.moveTo((last || p).x, (last || p).y); ctx.lineTo(p.x, p.y); ctx.stroke();
      last = p; if (++moves % 8 === 0) check();
    }
    function check() {
      if (finished) return;
      var d = ctx.getImageData(0, 0, cv.width, cv.height).data, clear = 0, n = 0;
      for (var i = 3; i < d.length; i += 64) { n++; if (d[i] < 40) clear++; }
      if (!seen && clear / n > 0.12) {
        seen = true;
        var x = cardById(id); if (!x.c.scratched) { x.c.scratched = true; markScratched(id); }
        $('scBody').innerHTML = scratchBody(x);
        var rv = document.querySelector('.sc-reveal'); if (rv) rv.remove();
      }
      if (clear / n > 0.55) { finished = true; cv.classList.add('gone'); setTimeout(function () { ACTIONS.scratchReveal({ dataset: { id: id } }); }, 450); }
    }
    cv.addEventListener('pointerdown', function (e) { down = true; last = null; cv.setPointerCapture(e.pointerId); scratch(pt(e)); });
    cv.addEventListener('pointermove', function (e) { if (down) scratch(pt(e)); });
    cv.addEventListener('pointerup', function () { down = false; check(); });
    cv.addEventListener('pointercancel', function () { down = false; });
  };

  SCREENS.draw = function () {
    var today = dayKey(), res = drawResults(today), mine = allCards().map(function (x) { return x.c; });
    var pending = mine.filter(function (c) { return !c.submitted; });
    var nosFor = function (pred) { return mine.filter(pred).reduce(function (t, c) { return t.concat(c.nos); }, []); };
    var todayNos = nosFor(function (c) { return c.submitted && c.drawDate === today; });
    var nextNos = nosFor(function (c) { return c.submitted && c.drawDate > today; });
    function winners(list) {
      return '<div class="wl">' + list.map(function (w) {
        var me = w.member === BC_MEMBER.id, ord = w.place + ({ 1: 'st', 2: 'nd', 3: 'rd' }[w.place] || 'th');
        var medal = { 1: ' gold', 2: ' silver', 3: ' bronze' }[w.place] || '';
        return '<div class="wl-r' + (me ? ' me' : '') + '"><span class="wl-p' + medal + '" aria-label="' + ord + ' prize">' + ord + '</span>' +
          '<span class="wl-n">' + esc(w.name) + (me ? ' <span class="badge ok">You</span>' : '') + '</span>' +
          '<span class="lno wl-t">' + esc(w.no) + '</span><b class="wl-a">' + inr(w.amount) + '</b>' + '</div>';
      }).join('') + '</div>';
    }
    /* Today's winners are listed above, so the calendar covers the 30 days before today. Nothing is selected
       until a day is tapped; tapping it again closes its list. */
    /* Shown only if you won today: your total and a Claim button that opens My wins */
    function wonCard(list) {
      var mineW = list.filter(function (w) { return w.member === BC_MEMBER.id; }); if (!mineW.length) return '';
      var total = mineW.reduce(function (t, w) { return t + w.amount; }, 0);
      var open = mineW.some(function (w) { return !(w.card && w.card.claimed); });
      return '<div class="won-card"><span class="wc-ic">' + ic('crown', 20) + '</span><div class="li-main"><div class="wc-t">You won ' + inr(total) + ' today</div>' +
        '<div class="li-s">' + (mineW.length > 1 ? mineW.length + ' winning numbers' : '1 winning number') + '</div></div>' +
        (open ? '<button class="btn btn-sm btn-gold" data-go="my-wins">Claim</button>' : '<span class="badge ok">Claimed</span>') + '</div>';
    }
    var DAYS = 30, sel = ui.drawSel && ui.drawSel < today && ui.drawSel >= dayShift(today, -DAYS) ? ui.drawSel : null;
    var first = dayShift(today, -DAYS), lead = (new Date(first + 'T12:00:00').getDay() + 6) % 7, cells = '', MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    for (var e = 0; e < lead; e++) cells += '<span class="cal-c empty"></span>';
    for (var i = 0; i < DAYS; i++) {
      var k = dayShift(first, i), dn = +k.slice(8), r = drawResults(k), won = r && r.some(function (w) { return w.member === BC_MEMBER.id; });
      cells += '<button class="cal-c' + (r ? '' : ' pending') + (k === sel ? ' on' : '') + (won ? ' won' : '') + '" data-act="drawDay" data-id="' + k + '" aria-label="' + esc(dayLabel(k)) + '"' + (k === sel ? ' aria-pressed="true"' : '') + '>' +
        ((i === 0 || dn === 1) ? '<small>' + MON[+k.slice(5, 7) - 1] + '</small>' : '') + '<b>' + dn + '</b><i></i></button>';
    }
    var selRes = sel ? drawResults(sel) : null;
    var calendar = '<div class="cal"><div class="cal-w">' + ['M', 'T', 'W', 'T', 'F', 'S', 'S'].map(function (d) { return '<span>' + d + '</span>'; }).join('') + '</div><div class="cal-g">' + cells + '</div>' +
      '<div class="cal-key"><span><i class="k-d"></i>Draw held</span><span><i class="k-w"></i>You won</span></div></div>' +
      (!sel ? '<p class="fine center" style="margin-top:10px">Tap a day to see its winners.</p>' :
      '<div class="sec-h" style="padding:0;margin:16px 0 8px"><h3>' + esc(dayLabel(sel)) + (sel === dayShift(today, -1) ? ' · ' + esc(new Date(sel + 'T12:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })) : '') + '</h3><span class="li-s">' + (selRes ? selRes.length + ' winners' : 'No draw') + '</span></div>' +
      (selRes ? winners(selRes) + verifyLink(sel) : '<div class="surface draw-wait"><div class="li-s">No published draw on this day.</div></div>'));
    return topbar('Lucky Draw', 'home') + '<div class="pad">' +
      '<div class="draw-hero"><span class="hm-eyebrow">' + ic('gift', 14) + 'Every day at ' + drawTimeLabel() + '</span>' +
        '<div class="dh-top">' + inr(BC_DRAW.prizes[0].amount) + '</div><div class="dh-s">1st prize · ' + drawWinnerCount() + ' winners daily</div>' +
        '<div class="dh-prizes">' + BC_DRAW.prizes.slice(1).map(function (p) { return '<span>' + (p.count > 1 ? p.count + ' × ' : '') + inr(p.amount) + '</span>'; }).join('') + '</div></div>' +
      (pending.length ? pending.map(function (c) {
        return '<button class="alert alert-btn" data-go="scratch/' + c.id + '">' + ic('sparkle', 18) + '<span>' + (c.scratched ? 'Enter your ' + numsLabel(c.nos.length) : 'Scratch card to open · ' + numsLabel(c.nos.length)) + '</span>' + ic('chev', 16) + '</button>';
      }).join('') : '') +
      '<div class="sec-h" style="padding:0;margin-top:22px"><h3>Today · ' + esc(new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })) + '</h3></div>' +
      (res ? wonCard(res) + winners(res) + verifyLink(today)
        : '<div class="surface draw-wait"><div class="dw-k" id="drawCdK">Results in</div><div class="dw-v" id="drawCd"></div>' +
          '<div class="li-s">' + (todayNos.length ? 'Your ' + (todayNos.length > 1 ? todayNos.length + ' numbers' : 'number') + ' in today’s draw' : 'No entries from you yet. Order tea to get a scratch card.') + '</div>' +
          (todayNos.length ? '<div class="chips mt8">' + todayNos.map(function (no) { return '<span class="lno big">' + esc(no) + '</span>'; }).join('') + '</div>' : '') +
          '</div>') +
      (nextNos.length ? '<p class="fine">Also entered for tomorrow: ' + nextNos.map(esc).join(', ') + '</p>' : '') +
      '<div class="sec-h" style="padding:0;margin-top:24px"><h3>Last 30 days</h3></div>' + calendar +
      '<p class="fine center mt16">Winners are contacted on their registered mobile. Prizes are subject to applicable taxes and the Lucky Draw terms.</p></div>';
  };
  AFTER.draw = function () {
    refreshResults();
    maybeReveal();
    /* An Admin can close today's draw early (Skip), run it or delete it at any moment, so while this page is open
       it checks every 10 s (and at once when the tab is shown again, see below). New winners play the reveal. */
    timers.push(setInterval(function () { if (!document.hidden) refreshResults(true); }, 10000));
    var el = $('drawCd'); if (!el) return;
    function tick() {   /* results are published at 8:30 PM IST, or right after an early (Skip) draw */
      var ms = publishAt(dayKey()) - new Date();
      if (ms <= 0) {
        el.textContent = 'Waiting for the draw to run'; el.classList.add('sm');
        var k = $('drawCdK'); if (k) k.textContent = 'Today’s draw';
        return;
      }
      var h = Math.floor(ms / 3600000), m = Math.floor(ms / 60000) % 60, s = Math.floor(ms / 1000) % 60;
      el.textContent = (h ? h + 'h ' : '') + ('0' + m).slice(-2) + 'm ' + ('0' + s).slice(-2) + 's';
    }
    tick(); timers.push(setInterval(tick, 1000));
  };

  /* ----- Results reveal (frontend/reveal.js), over published winners only: plays each time the Lucky Draw page is
     opened while today's result is published. At midnight today's result gives way to the next draw's countdown.
     A data refresh (rerender) never replays the same winners; a result published while the page is open plays then. ----- */
  var REVEAL_STOP = null;
  function prizeAmount(rank) { var r = 0, a = 0; BC_DRAW.prizes.forEach(function (p) { for (var k = 0; k < p.count; k++) { r++; if (r === rank) a = p.amount; } }); return a; }
  function playReveal(label, winners, mine, onDone) {
    if (REVEAL_STOP || !window.BCREVEAL) return;
    REVEAL_STOP = BCREVEAL.play($('device'), {
      winners: winners.map(function (w) { return { rank: w.rank, ticket: w.ticket, name: w.name, label: w.label || prizeLabel(w.rank), amount: w.amount || prizeAmount(w.rank) }; }),
      myNumbers: mine, firstName: BC_MEMBER.firstName, dayLabel: /^\d{4}-/.test(label) ? dayLabel(label) : 'TEST',
      verifyHref: '/verify-draw/' + encodeURIComponent(label), confetti: confetti, chime: playChime,
      onDone: function () { REVEAL_STOP = null; if (onDone) onDone(); }
    });
  }
  function maybeReveal() {
    var key = dayKey(), list = RESULTS[key];
    if (!list || REVEAL_STOP) return;
    var sig = key + ':' + list.map(function (w) { return w.ticket; }).join(',');
    if (!ui.revealDue && ui.revealSig === sig) return;   /* a new winner list (after a deleted draw) plays even mid-visit */
    ui.revealDue = false; ui.revealSig = sig;
    var mine = allCards().filter(function (x) { return x.c.drawDate === key; }).reduce(function (t, x) { return t.concat(x.c.nos); }, []);
    playReveal(key, list, mine);
  }

  /* ----- Verify the draw (public): every closed Draw day's files, its Seal on GitHub, its drand round, and the Verifier ----- */
  var DRAND_CHAIN = '52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971';
  function verifyLink(label, inRow) { return '<a class="btn btn-line btn-sm' + (inRow ? '' : ' mt12') + '" href="/verify-draw/' + encodeURIComponent(label) + '">' + ic('shield', 15) + 'Verify this draw</a>'; }
  SCREENS['verify-draw'] = function (focus) {
    var days = PUBLIC_DAYS, api = '/api/public/days/';
    function dl(href, text) { return '<a class="link" href="' + esc(href) + '" target="_blank" rel="noopener">' + esc(text) + '</a>'; }
    function file(href, text) { return '<a class="link" href="' + esc(href) + '" download>' + esc(text) + '</a>'; }   /* our files download; external links open */
    var guide = '<div class="surface" style="padding:4px 16px"><div class="field-l" style="margin-top:12px">Check any draw yourself</div>' +
      '<ol class="vd-steps"><li>Install Python 3.11 or newer. Nothing else is needed.</li>' +
      '<li>Download ' + dl('/api/public/verifier/verify.py', 'verify.py') + ' (also on GitHub with the source).</li>' +
      '<li>Run <code>python verify.py 2026-11-10</code> with the draw day. It downloads the files below, the Seal from GitHub and the randomness from drand, re-runs the draw and prints <b>VERIFIED</b> or what failed.</li></ol></div>';
    var list = days === null ? '<div class="center mt16"><span class="mini-spin" aria-label="Loading"></span></div>'
      : !days.length ? '<div class="surface sp-empty mt16">' + ic('calendar', 18) + '<span>No draw has closed yet. Each day closes at 8:00 PM IST.</span></div>'
      : days.map(function (d) {
        var pub = d.status === 'published', on = focus && focus === d.label;
        return '<div class="surface mt12' + (on ? ' vd-on' : '') + '" style="padding:4px 16px" id="vd-' + esc(d.label) + '">' +
          '<div class="kv"><span><b>' + esc(d.label) + '</b>' + (d.kind === 'test' ? ' <span class="badge warn">TEST</span>' : '') + '</span><span><span class="badge ' + (pub ? 'ok' : 'plain') + '">' + (pub ? 'Published' : 'Sealed · result at ' + resultsTimeLabel(d.label)) + '</span></span></div>' +
          '<div class="kv"><span>Tickets</span><span>' + num(d.ticketCount || 0) + '</span></div>' +
          '<div class="kv"><span>Fingerprint</span><span class="adm-fp">' + esc(d.fingerprint || '') + '</span></div>' +
          '<div class="kv"><span>Seal</span><span>' + (d.sealUrl ? dl(d.sealUrl, 'On GitHub') : 'Publishing…') + ' · ' + file(api + d.label + '/seal.json', 'seal.json') + '</span></div>' +
          '<div class="kv"><span>Randomness</span><span>' + dl('https://api.drand.sh/' + DRAND_CHAIN + '/public/' + d.drandRound, 'drand round ' + d.drandRound) + '</span></div>' +
          '<div class="kv"><span>Files</span><span>' + file(api + d.label + '/tickets.csv', 'tickets.csv') + (pub ? ' · ' + file(api + d.label + '/result.json', 'result.json') : '') + '</span></div>' +
          '<div class="kv"><span>Command</span><span><code>python verify.py ' + esc(d.label) + '</code></span></div></div>';
      }).join('');
    return topbar('Verify the draw', SES.authed ? 'draw' : 'welcome', ' ') + '<div class="pad">' +
      '<p class="sub">Every night’s winners follow from two public things: the ticket list sealed at 8:00 PM and a random number from drand that nobody knew in advance. You can check both.</p>' +
      guide + '<div class="field-l">Draw days</div>' + list + '</div>';
  };
  AFTER['verify-draw'] = function (focus) {
    refreshResults(true);
    var el = focus && $('vd-' + focus); if (el) el.scrollIntoView({ block: 'center' });
  };

  /* ============================================================
     HELP & SUPPORT: contact options + grievances (business → details → evidence)
     ============================================================ */
  function grvTargets() { return liveBiz().concat([{ id: 'club', label: 'Boche app', name: 'Boche app', icon: 'card' }]); }
  function grvTarget(id) { return grvTargets().filter(function (b) { return b.id === id; })[0]; }
  function grvOk() { var g = ui.grv; return !!(g.biz && g.text.trim().length >= BC_SUPPORT.minChars); }
  function fileSize(n) { return n > 1048576 ? (n / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(n / 1024)) + ' KB'; }

  SCREENS.support = function () {
    var tickets = dyn(BC_MEMBER.id).tickets || [];
    return topbar('Help & support', 'home') + '<div class="pad">' +
      '<div class="sp-contact">' +
        '<a class="sp-tile" href="tel:' + esc(BC_BRAND.supportPhone.replace(/\s/g, '')) + '">' + ic('phone', 22) + '<b>Call us</b><span>' + esc(BC_BRAND.supportPhone) + '</span></a>' +
        '<a class="sp-tile" href="mailto:' + esc(BC_BRAND.supportEmail) + '">' + ic('doc', 22) + '<b>Email</b><span>' + esc(BC_BRAND.supportEmail) + '</span></a></div>' +
      '<p class="fine center">' + esc(BC_SUPPORT.hours) + '</p>' +
      '<button class="sp-raise" data-act="grvNew"><span class="sp-ic">' + ic('chat', 22) + '</span><span class="li-main"><b>Raise a complaint</b><span>Tell us what went wrong at any Boche business</span></span>' + ic('chev', 18) + '</button>' +
      '<div class="sec-h" style="padding:0;margin-top:24px"><h3>Your complaints</h3></div>' +
      (tickets.length ? '<div class="list">' + tickets.map(function (t) {
        var b = grvTarget(t.biz);
        return '<button class="li" data-go="ticket/' + t.id + '"><span class="li-ic">' + ic(b.icon, 18) + '</span><div class="li-main"><div class="li-t clamp1">' + esc(t.text) + '</div>' +
          '<div class="li-s">' + esc(t.id) + ' · ' + esc(b.label) + ' · ' + esc(t.date) + '</div></div><span class="badge">' + esc(t.status) + '</span></button>';
      }).join('') + '</div>'
        : '<div class="surface sp-empty">' + ic('check', 18) + '<span>No complaints raised. We hope it stays that way!</span></div>') +
      '</div>';
  };

  SCREENS.grievance = function () {
    var g = ui.grv, picked = g.biz ? grvTarget(g.biz) : null;
    return '<div class="flow">' + topbar('Raise a complaint', 'support') + '<div class="pad">' +
      '<div class="field-l" style="margin-top:4px">1 · Which business is this about?</div>' +
      '<div class="grv-biz">' + grvTargets().map(function (b) {
        return '<button class="grv-opt' + (g.biz === b.id ? ' on' : '') + '" data-act="grvBiz" data-id="' + b.id + '">' + ic(b.icon, 22) + '<span>' + esc(b.label) + '</span>' + (g.biz === b.id ? '<i>' + ic('check', 12) + '</i>' : '') + '</button>';
      }).join('') + '</div>' +
      (picked ?
        '<div class="field-l">2 · What happened?</div>' +
        '<textarea id="grvText" class="input grv-text" maxlength="' + BC_SUPPORT.maxChars + '" placeholder="Describe the issue with ' + esc(picked.label) + '. Include the date, venue or order number if you have it.">' + esc(g.text) + '</textarea>' +
        '<div class="grv-count"><span id="grvHint">' + (g.text.trim().length < BC_SUPPORT.minChars ? 'At least ' + BC_SUPPORT.minChars + ' characters' : '') + '</span><span id="grvCount">' + g.text.length + '/' + BC_SUPPORT.maxChars + '</span></div>' +
        '<div class="field-l">3 · Evidence <span class="opt">optional</span></div>' +
        (g.files.length ? '<div class="grv-files">' + g.files.map(function (f, i) {
          return '<div class="grv-file">' + (f.thumb ? '<img src="' + f.thumb + '" alt="">' : '<span class="gf-doc">' + ic('doc', 20) + '</span>') +
            '<div class="li-main"><div class="li-t clamp1">' + esc(f.name) + '</div><div class="li-s">' + fileSize(f.size) + '</div></div>' +
            '<button class="gf-x" data-act="grvRemove" data-id="' + i + '" aria-label="Remove ' + esc(f.name) + '">' + ic('x', 16) + '</button></div>';
        }).join('') + '</div>' : '') +
        (g.files.length < BC_SUPPORT.maxFiles ? '<label class="grv-add">' + ic('clip', 18) + '<span>Add photo or PDF</span><small>Up to ' + BC_SUPPORT.maxFiles + ' files · ' + BC_SUPPORT.maxMb + ' MB each</small>' +
          '<input type="file" id="grvFile" accept="image/*,application/pdf" multiple hidden></label>' : '')
        : '<p class="fine">Pick a business to continue.</p>') +
      '</div><div class="sticky-cta"><button class="btn btn-gold" id="grvGo" data-act="grvSubmit"' + (grvOk() ? '' : ' disabled') + '>Submit complaint</button></div></div>';
  };
  AFTER.grievance = function () {
    var ta = $('grvText');
    if (ta) {
      ta.addEventListener('input', function () {
        ui.grv.text = ta.value;
        $('grvCount').textContent = ta.value.length + '/' + BC_SUPPORT.maxChars;
        $('grvHint').textContent = ta.value.trim().length < BC_SUPPORT.minChars ? 'At least ' + BC_SUPPORT.minChars + ' characters' : '';
        $('grvGo').disabled = !grvOk();
      });
      if (ui.grv.focusText) { ui.grv.focusText = false; ta.focus(); }
    }
    var fi = $('grvFile');
    if (fi) fi.addEventListener('change', function () {
      var files = Array.prototype.slice.call(fi.files), room = BC_SUPPORT.maxFiles - ui.grv.files.length, pending = 0;
      if (files.length > room) toast('Only ' + BC_SUPPORT.maxFiles + ' files can be attached');
      files.slice(0, room).forEach(function (f) {
        if (!/^image\/|application\/pdf/.test(f.type)) { toast(f.name + ' isn’t a photo or PDF'); return; }
        if (f.size > BC_SUPPORT.maxMb * 1048576) { toast(f.name + ' is over ' + BC_SUPPORT.maxMb + ' MB'); return; }
        var item = { name: f.name, size: f.size, type: f.type, thumb: '' };
        ui.grv.files.push(item);
        if (f.type.indexOf('image/') === 0) {
          pending++;
          var url = URL.createObjectURL(f), img = new Image();
          img.onload = function () {
            var c = document.createElement('canvas'), s = 96, r = Math.max(s / img.width, s / img.height);
            c.width = c.height = s;
            c.getContext('2d').drawImage(img, (s - img.width * r) / 2, (s - img.height * r) / 2, img.width * r, img.height * r);
            item.thumb = c.toDataURL('image/jpeg', .7); URL.revokeObjectURL(url);
            if (--pending === 0) rerender();
          };
          img.onerror = function () { URL.revokeObjectURL(url); if (--pending === 0) rerender(); };
          img.src = url;
        }
      });
      if (!pending) rerender();
    });
  };

  SCREENS.ticket = function (id) {
    var t = (dyn(BC_MEMBER.id).tickets || []).filter(function (x) { return x.id === id; })[0];
    if (!t) return SCREENS.support();
    var b = grvTarget(t.biz), fresh = ui.grvJustSent === id;
    return (fresh ? '' : topbar('Complaint', 'support')) + '<div class="' + (fresh ? 'auth' : 'pad') + '">' +
      (fresh ? '<div class="verified-hero"><div class="big-check">' + ic('check', 36) + '</div><h1>Complaint registered</h1>' +
        '<p class="lead">We’ll acknowledge it within ' + BC_SUPPORT.ackHours + ' hours and aim to resolve it within ' + BC_SUPPORT.resolveDays + ' days.</p></div>' : '') +
      '<div class="surface mt16" style="padding:4px 16px">' +
        '<div class="kv"><span>Ticket</span><span>' + esc(t.id) + '</span></div>' +
        '<div class="kv"><span>Business</span><span>' + esc(b.label) + '</span></div>' +
        '<div class="kv"><span>Raised on</span><span>' + esc(t.date) + '</span></div>' +
        '<div class="kv"><span>Status</span><span>' + esc(t.status) + '</span></div></div>' +
      '<div class="field-l">Your complaint</div><div class="surface grv-body">' + esc(t.text) + '</div>' +
      (t.files.length ? '<div class="field-l">Evidence</div><div class="grv-files">' + t.files.map(function (f) {
        return '<div class="grv-file">' + (f.thumb ? '<img src="' + f.thumb + '" alt="">' : '<span class="gf-doc">' + ic('doc', 20) + '</span>') +
          '<div class="li-main"><div class="li-t clamp1">' + esc(f.name) + '</div><div class="li-s">' + fileSize(f.size) + '</div></div></div>';
      }).join('') + '</div>' : '') +
      '<p class="fine center mt12">Updates come by SMS to +91 ' + esc(BC_MEMBER.mobile) + '.</p>' +
      (fresh ? '<button class="btn btn-gold mt16" data-act="grvDone">Done</button>' : '') + '</div>';
  };

  /* ----- Activity ----- */
  SCREENS.activity = function () {
    var tab = ui.actTab, d = dyn(BC_MEMBER.id), body;
    if (tab === 'points') {
      var rows = d.history.filter(function (h) { return ui.actBiz === 'all' || h.biz === ui.actBiz; });
      body = '<div class="chips scroll-x mt12"><button class="chip' + (ui.actBiz === 'all' ? ' on' : '') + '" data-act="actBiz" data-id="all">All</button>' +
        liveBiz().filter(function (b) { return b.earn; }).map(function (b) { return '<button class="chip' + (ui.actBiz === b.id ? ' on' : '') + '" data-act="actBiz" data-id="' + b.id + '">' + esc(b.short) + ' · ' + num(pointsOf(BC_MEMBER.id, b.id)) + '</button>'; }).join('') + '</div>' +
        '<div class="list mt12">' + (rows.length ? rows.map(function (h) {
          return '<div class="li"><span class="li-ic">' + ic(h.pts > 0 ? 'plus' : 'minus', 16) + '</span><div class="li-main"><div class="li-t">' + esc(h.title) + '</div><div class="li-s">' + esc(biz(h.biz).short) + ' · ' + esc(h.date) + ' · ' + esc(h.ref) + '</div></div>' +
            '<span class="li-r ' + (h.pts > 0 ? 'pos' : 'neg') + '">' + (h.pts > 0 ? '+' : '−') + num(Math.abs(h.pts)) + '</span></div>';
        }).join('') : '<div class="li"><div class="li-main li-s">No activity yet</div></div>') + '</div>';
    } else if (tab === 'checkins') {
      body = '<div class="list mt12">' + (d.checkins.length ? d.checkins.map(function (c) {
        var o = outlet(c.outlet);
        return '<div class="li"><span class="li-ic">' + ic('qr', 18) + '</span><div class="li-main"><div class="li-t">' + esc(o.name) + '</div><div class="li-s">' + esc(o.checkinLabel) + ' · ' + esc(c.date) + ', ' + esc(c.time) + '</div></div><span class="badge ok">Verified</span></div>';
      }).join('') : '<div class="li"><div class="li-main li-s">No check-ins yet</div></div>') + '</div>';
    } else {
      body = '<div class="mt12">' + (d.vouchers.length ? d.vouchers.map(function (v) {
        return '<div class="voucher"' + (v.used ? ' style="opacity:.55"' : '') + '><div class="chips"><span class="badge plain">' + esc(biz(v.biz).short) + '</span>' + (v.used ? '<span class="badge">Used</span>' : '<span class="badge ok">Active</span>') + '</div>' +
          '<div class="li-t mt8">' + esc(v.title) + '</div><div class="code">' + esc(v.code) + '</div><div class="li-s">Issued ' + esc(v.date) + '</div></div>';
      }).join('') : '<div class="surface center" style="padding:28px 16px"><div class="li-ic" style="margin:0 auto 10px">' + ic('gift', 18) + '</div><div class="li-t">No vouchers yet</div><div class="li-s">Redeem a reward in any business.</div></div>') + '</div>';
    }
    return topbar('Activity', 'profile') + '<div class="pad"><div class="seg">' +
      [['points', 'Points'], ['checkins', 'Check-ins'], ['vouchers', 'Vouchers']].map(function (t) { return '<button class="' + (tab === t[0] ? 'on' : '') + '" data-act="actTab" data-id="' + t[0] + '">' + t[1] + '</button>'; }).join('') + '</div>' + body + '</div>';
  };

  /* ----- Tiers (ecosystem spend) ----- */
  SCREENS.tiers = function () {
    var cur = curTier(), id = BC_MEMBER.id, sp = dyn(id).spend, total = totalSpend(id);
    return topbar('Membership tiers', 'home') + '<div class="pad">' +
      '<p class="sub">Membership is free. Your tier is earned from what you spend across the whole Boche family and applies at every business.</p>' +
      '<div class="surface" style="padding:4px 16px"><div class="field-l" style="margin:12px 0 4px">Your spend this year</div>' +
      BC_BUSINESSES.map(function (b) { return '<div class="kv"><span>' + esc(b.name) + '</span><span>' + (b.live ? inr(sp[b.id] || 0) : 'Coming soon') + '</span></div>'; }).join('') +
      '<div class="kv total"><span>Total</span><span>' + inr(total) + '</span></div></div>' +
      '<div class="mt16">' + BC_TIERS.map(function (t) {
        var isCur = t.id === cur.id, reached = total >= t.minSpend;
        return '<div class="tier-card t-' + t.id + (isCur ? ' current' : '') + '"><div class="tc-head"><span class="tc-name">' + esc(t.name) + '</span><span class="tc-price">' + (t.minSpend ? inr(t.minSpend) + ' spend' : 'Everyone') + '</span></div>' +
          '<ul class="perks">' + t.perks.map(function (p) { return '<li>' + ic('check', 16) + esc(p) + '</li>'; }).join('') + '</ul>' +
          '<div class="chips">' + liveBiz().filter(function (b) { return b.earn; }).map(function (b) { return '<span class="badge plain">' + esc(b.short) + ' · ' + b.earn[t.id] + ' pts/₹100</span>'; }).join('') + '</div>' +
          '<div class="mt12">' + (isCur ? '<span class="badge ok">' + ic('check', 12) + 'Your current tier</span>' : reached ? '<span class="badge">Reached</span>' : '<span class="badge plain">' + inr(t.minSpend - total) + ' to go</span>') + '</div></div>';
      }).join('') + '</div></div>';
  };

  /* ----- Offers & events ----- */
  SCREENS.offers = function () {
    var tab = ui.offersTab, body;
    if (tab === 'offers') body = BC_OFFERS.map(offerCard).join('');
    else body = BC_EVENTS.map(function (e) {
      var d = new Date(e.date + 'T00:00:00'), res = S.reserved.indexOf(e.id) > -1, o = outlet(e.outlet), st = ageState(o);
      return '<div class="surface offer" style="display:flex;gap:14px"><div class="datebox"><b>' + d.getDate() + '</b><span>' + d.toLocaleDateString('en-GB', { month: 'short' }) + '</span></div>' +
        '<div class="li-main"><div class="li-t" style="font-size:15px">' + esc(e.title) + '</div><div class="li-s">' + esc(o.name) + ' · ' + esc(e.time) + ' · ' + e.seats + ' seats left</div>' +
        '<div class="li-s gold-text" style="margin-top:4px">' + esc(e.price) + '</div>' +
        (st === 'verify' && !res ? '<button class="btn btn-sm mt12 btn-gold" data-go="' + verifyRoute('offers') + '">' + ic('shield', 15) + 'Verify age to reserve</button>'
          : '<button class="btn btn-sm mt12 ' + (res ? 'btn-soft' : 'btn-gold') + '" data-act="reserve" data-id="' + e.id + '"' + (st === 'under' ? ' disabled' : '') + '>' + (res ? ic('check', 16) + 'Reserved' : st === 'under' ? 'Age restricted' : 'Reserve a spot') + '</button>') + '</div></div>';
    }).join('');
    return topbar('Offers & events', 'home') + '<div class="pad">' +
      '<div class="seg"><button class="' + (tab === 'offers' ? 'on' : '') + '" data-act="offersTab" data-id="offers">Offers</button><button class="' + (tab === 'events' ? 'on' : '') + '" data-act="offersTab" data-id="events">Events</button></div>' +
      '<p class="fine" style="margin-bottom:12px">Activated offers apply when staff scan your card at the venue.</p>' + body + '</div>';
  };

  /* ----- Profile ----- */
  SCREENS.profile = function () {
    var t = curTier();
    function tg(k, label, sub) {
      return '<div class="li"><div class="li-main"><div class="li-t">' + label + '</div><div class="li-s">' + sub + '</div></div><button class="toggle' + (S.notif[k] ? ' on' : '') + '" data-act="notif" data-id="' + k + '" aria-label="' + label + '"></button></div>';
    }
    function row(icn, title, sub, act, extra) {
      return '<button class="li" ' + act + '><span class="li-ic">' + ic(icn, 18) + '</span><div class="li-main"><div class="li-t">' + title + '</div>' + (sub ? '<div class="li-s">' + sub + '</div>' : '') + '</div>' + (extra == null ? '<span class="li-chev">' + ic('chev', 18) + '</span>' : extra) + '</button>';
    }
    return topbar('Profile', '') +
      '<div class="prof-head"><button class="avatar-btn" data-act="photoPick" aria-label="Change photo">' + avatarHtml() + '<span class="av-cam">' + ic('plus', 12) + '</span></button><input type="file" id="photoIn" accept="image/*" hidden><div><div class="prof-name">' + esc(BC_MEMBER.name) + '</div>' +
      '<div class="li-s">' + esc(BC_MEMBER.id) + '</div><span class="badge mt8">' + ic('crown', 12) + esc(t.name) + ' member</span></div></div>' +
      '<div class="pad"><div class="list">' + row('receipt', 'Activity', 'Points, bills and visits', 'data-go="activity"') + '</div><div class="field-l">Account</div><div class="list">' +
      row('phone', '+91 ' + esc(BC_MEMBER.mobile), 'Mobile · SIM verified on this phone', 'disabled', '<span class="badge ok">Verified</span>') +
      row('shield', 'Trusted phones', myDevices().length + (myDevices().length === 1 ? ' phone' : ' phones') + ' · new phones need email check', 'data-act="devices"') +
      row('doc', esc(BC_MEMBER.email), 'Email', 'data-act="emailOpen"', (dyn(BC_MEMBER.id).profile || {}).emailVerified ? '<span class="badge ok">Verified</span>' : '<span class="badge warn">Verify</span>') +
      (function (l, def) {
        return row('pin', 'Delivery addresses', l.length ? (l.length > 1 ? l.length + ' saved · ' : '') + esc(def.label || 'Home') + ': ' + esc(addrLine(def)) : 'Add an address for Boche Tea and other deliveries', 'data-go="addresses"');
      })(addrList(), addrDefault()) +
      (kycOf() ? row('shield', 'Age verified', 'Aadhaar ' + esc(kycOf().aadhaarMasked) + ' · ' + esc(kycOf().verifiedOn), 'disabled', '<span class="badge ok">Verified</span>')
        : row('shield', 'Verify your age', 'Only needed for pubs and toddy shops', 'data-go="' + verifyRoute('profile') + '"')) +
      row('crown', 'Membership tier', esc(t.name) + ' · earned from spend', 'data-go="tiers"') +
      row('gift', 'Lucky Draw', 'Your entries and daily winners', 'data-go="draw"') + '</div>' +
      '<div class="field-l">My bookings</div><div class="list">' + (S.bookings.length ? S.bookings.map(function (b) {
        return '<div class="li"><span class="li-ic">' + ic('calendar', 18) + '</span><div class="li-main"><div class="li-t">' + esc(b.outlet) + '</div><div class="li-s">' + esc(b.when) + ' · ' + b.guests + ' guests · ' + esc(b.ref) + '</div></div><span class="badge ok">Confirmed</span></div>';
      }).join('') : '<div class="li"><span class="li-ic">' + ic('calendar', 18) + '</span><div class="li-main"><div class="li-t">No upcoming bookings</div><div class="li-s">Book a table from any venue page</div></div></div>') + '</div>' +
      '<div class="field-l">Notifications</div><div class="list">' +
      tg('offers', 'Offers & promotions', 'Deals across the Boche family') + tg('events', 'Events', 'Live nights and member events') + tg('points', 'Points activity', 'Earn, redeem and expiry alerts') + '</div>' +
      '<div class="field-l">Sound</div><div class="list">' + tg('sound', 'Celebration sounds', 'A short chime when you enter the Lucky Draw') + '</div>' +
      '<div class="field-l">App</div><div class="list">' +
      (isStandalone() ? '' : row('download', 'Install app', 'Add to your home screen', 'data-act="install"')) +
      row('help', 'Help & support', 'Contact us or raise a complaint', 'data-go="support"') +
      row('refresh', 'Reset demo', 'Start the prototype from the beginning', 'data-act="resetDemo"', '') +
      row('logout', 'Log out', '', 'data-act="logout"', '') + '</div>' +
      '<p class="group-foot">' + esc(BC_BRAND.name) + ' · ' + esc(BC_BRAND.group) + '</p></div>';
  };

  /* ============================================================
     BUSINESS ADMIN MODULE (staff)
     ============================================================ */
  SCREENS.staff = function () {
    var hint = BC_STAFF.map(function (s) { return '<div>' + esc(s.name) + ' · ' + esc(biz(s.biz).name) + ' — <b>' + esc(s.mobile) + '</b></div>'; }).join('');
    return topbar('', 'welcome') + '<div class="auth"><span class="badge">' + ic('scan', 13) + ' Boche business app</span>' +
      '<h1 class="mt12">Business sign-in</h1><p class="lead">For staff at Boche venues. Verify members, check them in and post bills.</p>' +
      '<div class="field-l">Lucky Draw admin</div>' +
      (ME && ME.role === 'admin'
        ? '<button class="btn btn-gold" data-go="admin-draw">' + ic('crown', 16) + 'Open Tonight’s draw</button>'
        : '<div class="gsi-slot" id="gsiAdmin"><span class="mini-spin" aria-label="Loading Google sign-in"></span></div>' +
          '<div class="err-text" id="adminErr">' + esc(ui.adminErr || '') + '</div>') +
      '<div class="field-l">Venue staff mobile number</div>' +
      '<div class="phone-field"><span class="cc">+91</span><input id="smobile" type="tel" inputmode="numeric" maxlength="10" placeholder="10-digit number" value="' + esc(ui.staffMobile) + '"></div>' +
      '<div class="err-text" id="smobErr"></div>' +
      '<button class="btn btn-gold mt8" id="sendStaffOtp" data-act="sendStaffOtp" disabled>Send OTP</button>' +
      '<div class="demo-hint">Demo staff<br>' + hint + '</div></div>';
  };
  AFTER.staff = function () {
    wireMobile('smobile', 'sendStaffOtp', 'smobErr', function () { ACTIONS.sendStaffOtp(); }, true);
    if ($('gsiAdmin')) mountGoogleButton('gsiAdmin', 'adminErr', onAdminCredential);
  };
  /* Lucky Draw admin: Google sign-in; only emails on the server's Admin list get the admin role */
  function onAdminCredential(resp) {
    var slot = $('gsiAdmin'); if (slot) slot.innerHTML = '<span class="mini-spin" aria-label="Signing in"></span>';
    ui.adminErr = '';
    BCAPI.post('/auth/google', { credential: resp.credential, admin: true }).then(function (u) {
      ME = u; applyProfile(); SES.authed = true; SES.pending = null; saveSes(); refreshOrders(true);
      if (u.role === 'admin') { ui.adm = null; go('admin-draw'); }
      else { ui.adminErr = 'This Google account is not a Lucky Draw admin.'; rerender(); }
    }).catch(function (e) {
      ui.adminErr = e.status === 403 ? 'This Google account is not a Lucky Draw admin.' : e.status === 503 ? 'Google sign-in is unavailable right now. Please try again.' : 'Sign-in failed. Please try again.';
      rerender();
    });
  }

  /* ----- Lucky Draw admin: Tonight's draw (status, Seal, Founder's OTP → the draw runs once) ----- */
  function istTime(iso, secs) { return iso ? new Date(iso).toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit', second: secs ? '2-digit' : undefined, timeZone: 'Asia/Kolkata' }) : '—'; }
  function prizeLabel(rank) { return rank === 1 ? '1st prize' : rank === 2 ? '2nd prize' : rank === 3 ? '3rd prize' : 'Lucky 7'; }
  var ADM_STATUS = { open: ['Taking entries', 'plain'], sealed: ['Sealed · awaiting draw', 'warn'], drawn: ['Drawn', 'ok'], published: ['Published', 'ok'] };
  function admDay() { var A = ui.adm; return A && A.days ? A.days.filter(function (d) { return d.label === A.sel; })[0] : null; }
  function admLoad() {
    var A = ui.adm = ui.adm || { days: null, sel: null, loadedAt: 0 };
    A.loadedAt = Date.now();
    return BCAPI.get('/admin/draw-days').then(function (days) {
      (A.days || []).forEach(function (o) {
        var n = days.filter(function (x) { return x.label === o.label; })[0];
        if (o.seeding && o.seeding.running && n && n.seeding && !n.seeding.running) toast(n.seeding.error || num(n.seeding.done) + ' tickets added');
      });
      A.days = days;
      if (!days.some(function (d) { return d.label === A.sel; })) {
        A.sel = (days.filter(function (d) { return d.status === 'sealed'; })[0] || days[0] || {}).label || null;
      }
      if (parse().name === 'admin-draw' && !$('otp')) rerender();
    }).catch(function (e) {
      if (e.status === 401 || e.status === 403) { ui.adminErr = 'Please sign in with an admin Google account.'; go('staff'); }
    });
  }
  SCREENS['admin-draw'] = function () {
    var A = ui.adm, d = admDay();
    var head = '<div class="staff-head"><span class="ca-ic">' + ic('crown', 22) + '</span><div class="li-main"><div class="ca-t">Lucky Draw admin</div><div class="ca-s">' + esc(ME ? ME.name + ' · ' + ME.email : '') + '</div></div>' +
      '<button class="iconbtn" data-act="logout" aria-label="Sign out">' + ic('logout') + '</button></div>';
    if (!A || !A.days) return head + '<div class="pad center mt24"><span class="mini-spin" aria-label="Loading"></span></div>';
    var testPanel = '<div class="field-l">Test mode</div><div class="surface" style="padding:12px 16px"><p class="fine" style="margin-top:0">Run a whole day now: seed tickets, close entries, send the OTP and draw. Test days are labelled TEST and never touch real draws.</p>' +
      '<button class="btn btn-line btn-sm" data-act="admNewTest">' + ic('plus', 15) + 'New test day</button></div>';
    if (!d) return head + '<div class="pad mt16"><div class="surface sp-empty">' + ic('calendar', 18) + '<span>No draw days yet. A day appears when its first card is entered.</span></div>' + testPanel + '</div>';
    var st = ADM_STATUS[d.status] || [d.status, 'plain'], body;
    var seeding = d.seeding && d.seeding.running ? d.seeding : null;
    if (d.status === 'open' && d.kind === 'test') body = '<div class="btn-row mt16"><button class="btn btn-line" data-act="admSeed"' + (seeding ? ' disabled' : '') + '>' + (seeding ? 'Adding… ' + num(seeding.done) + ' / ' + num(seeding.target) : 'Add 5,000 tickets') + '</button>' +
      '<button class="btn btn-gold" data-act="admClose"' + (seeding || !d.ticketCount ? ' disabled' : '') + '>Close entries now</button></div>' +
      '<p class="fine center">Tickets are bought by 20 test customers through the real paid-order path. Closing seals the list and picks a drand round about 30 s ahead.</p>';
    else if (d.status === 'open') body = '<div class="rule-note mt16">' + ic('clock', 16) + '<span>Entries close at ' + istTime(d.closesAt) + '. The ticket list is then sealed automatically.</span></div>' +
      (!d.canSkip ? (d.kind === 'real' && d.label === dayKey() && (d.ticketCount || 0) < 10 ? '<p class="fine center mt12">Skip the wait appears once today has at least 10 tickets (one per winner).</p>' : '') : A.skipArm === d.label
        ? '<div class="rule-note mt16">' + ic('shield', 16) + '<span>Close today’s entries now? The ' + num(d.ticketCount || 0) + ' tickets entered so far are sealed and drawn; cards entered after this go into tomorrow’s draw. This cannot be undone.</span></div>' +
          '<div class="btn-row mt12"><button class="btn btn-line" data-act="admSkipCancel">Cancel</button><button class="btn btn-gold" data-act="admSkip">Yes, close and draw now</button></div>'
        : '<button class="btn btn-gold mt16" data-act="admSkipArm">' + ic('sparkle', 16) + 'Skip the wait · draw now</button>' +
          '<p class="fine center">Seals today’s list now instead of at 8:00 PM. The founder’s OTP can be sent about 30 s later, and results go public as soon as the draw runs.</p>');
    else if (d.status === 'sealed' && !d.canRequestOtp) body = '<div class="rule-note mt16">' + ic('clock', 16) + '<span>Waiting for drand round ' + d.drandRound + ', released at ' + istTime(d.roundReleasedAt, true) + '. The founder’s OTP can be sent after that.</span></div>';
    else if (d.status === 'sealed' && !d.otpExpiresAt) body = '<button class="btn btn-gold mt16" data-act="admSendOtp">' + ic('phone', 18) + 'Send OTP to founder</button>' +
      '<p class="fine center">The founder gets a 4-digit code by SMS. It runs this draw only, on the sealed list and the drand round above.</p>';
    else if (d.status === 'sealed') body = '<div class="field-l">Founder’s OTP</div><div class="otp" id="otp">' + otpBoxes(4) + '</div><div class="err-text" id="otpErr"></div>' +
      '<button class="btn btn-gold mt16" data-otp-btn data-act="admRun" disabled>' + ic('sparkle', 16) + 'Run the draw</button>' +
      '<p class="fine center mt12">Code sent · valid until ' + istTime(d.otpExpiresAt) + ' · <a class="link" href="javascript:void(0)" data-act="admSendOtp">Send a new code</a></p>';
    else body = '<div class="field-l">Winners · drawn at ' + istTime(d.drawnAt, true) + '</div><div class="list">' + (d.winners || []).map(function (x) {
        return '<div class="li win"><div class="li-main"><div class="li-t">' + x.rank + ({ 1: 'st', 2: 'nd', 3: 'rd' }[x.rank] || 'th') + ' prize</div><div class="li-s">Position ' + x.position + ' in the list</div></div><div class="win-r"><span class="lno">' + esc(x.ticket) + '</span></div></div>';
      }).join('') + '</div><p class="fine center mt12">Results go public at ' + istTime(d.publishNotBefore) + '.</p>' +
      (!d.canDelete ? '' : A.delArm === d.label
        ? '<div class="rule-note mt16">' + ic('shield', 16) + '<span>Delete today’s draw? The winners, their claims and the sealed list are erased, and the ' + num(d.ticketCount || 0) + ' tickets go back to their owners to enter again. Today’s draw reopens empty and closes at 8:00 PM. This cannot be undone.</span></div>' +
          '<div class="btn-row mt12"><button class="btn btn-line" data-act="admDelCancel">Cancel</button><button class="btn btn-gold" data-act="admDel">Yes, delete this draw</button></div>'
        : '<button class="btn btn-line mt16" data-act="admDelArm">' + ic('x', 16) + 'Delete this draw</button>');
    return head + '<div class="pad"><div class="field-l" style="margin-top:16px">Draw day</div><div class="chips scroll-x">' + A.days.map(function (x) {
        return '<button class="chip' + (x.label === A.sel ? ' on' : '') + '" data-act="admPick" data-id="' + esc(x.label) + '">' + (x.kind === 'test' ? 'Test ' + esc(x.label.replace(/^test-/, '')) : esc(x.label)) + '</button>';
      }).join('') + '</div>' +
      '<div class="surface mt12" style="padding:4px 16px">' +
      '<div class="kv"><span>Status</span><span><span class="badge ' + st[1] + '">' + st[0] + '</span>' + (d.kind === 'test' ? ' <span class="badge warn">TEST</span>' : '') + '</span></div>' +
      '<div class="kv"><span>Tickets</span><span>' + num(d.ticketCount || 0) + '</span></div>' +
      '<div class="kv"><span>Fingerprint</span><span class="adm-fp">' + (d.fingerprint ? esc(d.fingerprint.slice(0, 16)) + '…' : '—') + '</span></div>' +
      '<div class="kv"><span>Seal</span><span>' + (d.sealUrl ? '<a class="link" href="' + esc(d.sealUrl) + '" target="_blank" rel="noopener">On GitHub</a>' : d.fingerprint ? 'Publishing to GitHub…' : '—') + '</span></div>' +
      '<div class="kv"><span>Randomness</span><span>' + (d.drandRound ? 'drand round ' + d.drandRound + ' · ' + istTime(d.roundReleasedAt, true) : '—') + '</span></div></div>' +
      body + (d.status === 'published' ? '<div class="btn-row mt12"><button class="btn btn-line btn-sm" data-act="admReveal">' + ic('sparkle', 15) + 'Preview the reveal</button>' + verifyLink(d.label, true) + '</div>' : '') +
      testPanel + '</div>';
  };
  AFTER['admin-draw'] = function () {
    if (!ui.adm || !ui.adm.days || Date.now() - ui.adm.loadedAt > 10000) admLoad();
    if ($('otp')) wireOtp(function () { ACTIONS.admRun(); });
    else { var dd = admDay(); timers.push(setInterval(function () { if (!$('otp')) admLoad(); }, dd && dd.seeding && dd.seeding.running ? 1500 : dd && dd.status === 'sealed' && !dd.canRequestOtp ? 3000 : 15000)); }
  };

  SCREENS['staff-otp'] = function () { return otpScreen('staff', ui.staffMobile, 'verifyStaffOtp'); };
  AFTER['staff-otp'] = function () { if (!ui.staffMobile) { go('staff'); return; } wireOtp(function () { ACTIONS.verifyStaffOtp(); }); };

  function staffHead() {
    var st = staff(), b = biz(st.biz);
    return '<div class="staff-head"><span class="ca-ic">' + ic(b.icon, 22) + '</span><div class="li-main"><div class="ca-t">' + esc(b.name) + '</div><div class="ca-s">' + esc(st.name) + ' · ' + esc(st.role) + '</div></div>' +
      '<button class="iconbtn" data-act="staffLogout" aria-label="Sign out">' + ic('logout') + '</button></div>';
  }
  function outletChips() {
    var st = staff(), cur = staffOutlet();
    return '<div class="chips scroll-x">' + st.outlets.map(function (id) {
      return '<button class="chip' + (id === cur.id ? ' on' : '') + '" data-act="staffOutlet" data-id="' + id + '">' + esc(outlet(id).name.replace(/^Boche Pub /, '').replace(/^1000 Acre /, '')) + '</button>';
    }).join('') + '</div>';
  }

  SCREENS.scan = function () {
    var st = staff(), o = staffOutlet(), log = S.staffLog.filter(function (l) { return l.biz === st.biz; }).slice(0, 6);
    return staffHead() + '<div class="pad"><div class="field-l" style="margin-top:16px">Working at</div>' + outletChips() +
      '<div class="rule-note mt12">' + ic('shield', 16) + '<span>' + (o.ageGate ? esc(o.name) + ' requires age <b>' + BC_STATES[o.state].drinkingAge + '+</b> (' + esc(BC_STATES[o.state].name) + ').' : esc(o.name) + ' has no age restriction.') + '</span></div>' +
      '<div class="scanner mt16"><div class="sc-frame"><i></i><span class="sc-line"></span></div><p>' + esc(BC_STAFF_UI.scanHint) + '</p></div>' +
      '<div class="field-l">Demo: simulate scanning a member</div><div class="list">' + BC_MEMBERS.map(function (m) {
        var t = tierOfMember(m.id);
        return '<button class="li" data-go="verify/' + m.id + '"><span class="avatar" style="width:38px;height:38px;border-radius:12px;font-size:13px">' + initials(m.name) + '</span>' +
          '<div class="li-main"><div class="li-t">' + esc(m.name) + '</div><div class="li-s">Age ' + ageOf(m.dob) + ' · ' + esc(t.name) + '</div></div><span class="li-chev">' + ic('chev', 18) + '</span></button>';
      }).join('') + '</div>' +
      '<div class="field-l">Or find by mobile number</div><div class="inline-field"><input id="lookup" class="input" inputmode="numeric" maxlength="10" placeholder="10-digit mobile"><button class="btn btn-line btn-sm" data-act="lookup">Find</button></div>' +
      '<div class="err-text" id="lookErr"></div>' +
      '<div class="field-l">Recent activity</div><div class="list">' + (log.length ? log.map(function (l) {
        return '<div class="li"><span class="li-ic">' + ic(l.icon, 16) + '</span><div class="li-main"><div class="li-t">' + esc(l.text) + '</div><div class="li-s">' + esc(l.member) + ' · ' + esc(l.outlet) + ' · ' + esc(l.time) + '</div></div></div>';
      }).join('') : '<div class="li"><div class="li-main li-s">Nothing yet today</div></div>') + '</div></div>';
  };
  AFTER.scan = function () { var l = $('lookup'); if (l) l.addEventListener('input', function () { l.value = l.value.replace(/\D/g, ''); }); };

  SCREENS.verify = function (id) {
    var m = memberOf(id); if (!m) return SCREENS.scan();
    var st = staff(), o = staffOutlet(), b = biz(st.biz), d = dyn(id), a = ageOf(m.dob), t = tierOfMember(id);
    var st = ageState(o, id), ok = eligible(o, id), need = o.ageGate ? BC_STATES[o.state].drinkingAge : null;
    var vs = d.vouchers.filter(function (v) { return v.biz === b.id && !v.used; });
    var h = topbar('Verify member', 'scan');
    h += '<div class="pad">' +
      '<div class="verdict ' + (ok ? 'allow' : 'deny') + '"><span class="vd-ic">' + ic(ok ? 'check' : 'x', 30) + '</span><div><div class="vd-t">' + (ok ? 'Allowed' : st === 'verify' ? 'Age check needed' : 'Not allowed') + '</div>' +
      '<div class="vd-s">' + (ok ? (o.ageGate ? 'Age ' + a + ' · meets ' + need + '+ at ' + esc(o.name) : 'Verified member · ' + esc(o.name))
        : st === 'verify' ? 'Age not verified · ask ' + esc(m.firstName) + ' to verify in the Boche app (1 min)'
        : 'Age ' + a + ' · ' + esc(BC_STATES[o.state].name) + ' requires ' + need + '+ at ' + esc(o.name)) + '</div></div></div>' +
      '<div class="surface mt16" style="padding:14px 16px"><div class="hh-left"><div class="avatar">' + initials(m.name) + '</div><div class="li-main"><div class="prof-name" style="font-size:19px">' + esc(m.name) + '</div>' +
      '<div class="li-s">' + esc(m.id) + ' · +91 ' + esc(m.mobile) + '</div></div><span class="badge">' + ic('crown', 12) + esc(t.name) + '</span></div>' +
      '<div class="kv mt12"><span>Identity</span><span class="pos">' + (kycOf(id) ? 'Verified · OTP + Aadhaar' : 'Mobile OTP · age not verified') + '</span></div>' +
      '<div class="kv"><span>Age</span><span>' + (kycOf(id) ? a + ' years' : '—') + '</span></div>' +
      '<div class="kv"><span>' + esc(b.short) + ' points</span><span>' + num(pointsOf(id, b.id)) + '</span></div>' +
      '<div class="kv"><span>Earn rate here</span><span>' + b.earn[t.id] + ' pts per ₹100</span></div></div>';
    if (ok) {
      var p = S.pendingOtp, mine = p && p.memberId === m.id && p.outlet === o.id;
      if (mine && p.status === 'used') {
        h += '<button class="btn btn-soft mt16" disabled>' + ic('check', 18) + ' Checked in · OTP verified</button>';
      } else if (mine && p.status === 'sent') {
        h += '<div class="surface mt16" style="padding:14px 16px"><div class="li-t">' + ic('phone', 16) + ' OTP sent to +91 ' + esc(m.mobile) + '</div>' +
          '<div class="li-s">Waiting for ' + esc(m.firstName) + ' to enter it in the Boche app · valid ' + BC_STAFF_UI.otpValidMinutes + ' min</div>' +
          '<div class="demo-hint" style="margin-top:10px">Demo: the OTP is <b>' + esc(p.code) + '</b></div>' +
          '<button class="btn btn-line btn-sm mt12" data-act="sendCheckinOtp" data-id="' + m.id + '">Resend OTP</button></div>';
      } else {
        h += '<button class="btn btn-gold mt16" data-act="sendCheckinOtp" data-id="' + m.id + '">' + ic('phone', 18) + ' Send check-in OTP · ' + esc(o.checkinLabel) + '</button>' +
          '<p class="fine center">A 4-digit OTP goes to the member’s registered mobile.</p>';
      }
      h += '<div class="field-l">Post a bill — credits ' + esc(b.short) + ' points</div>' +
        '<div class="inline-field"><div class="phone-field" style="flex:1"><span class="cc">₹</span><input id="billAmt" inputmode="numeric" maxlength="7" placeholder="Bill amount" value="' + esc(ui.billAmt) + '"></div>' +
        '<button class="btn btn-gold btn-sm" id="postBill" data-act="postBill" data-id="' + m.id + '" disabled>Post</button></div>' +
        '<p class="fine" id="billPts">Enter the bill amount to see the points.</p>';
      if (vs.length) {
        h += '<div class="field-l">Member’s active vouchers</div>' + vs.map(function (v) {
          return '<div class="voucher"><div class="li-t">' + esc(v.title) + '</div><div class="code">' + esc(v.code) + '</div>' +
            '<button class="btn btn-soft btn-sm mt8" data-act="useVoucher" data-id="' + esc(v.code) + '" data-mem="' + m.id + '">Mark as redeemed</button></div>';
        }).join('');
      }
    } else {
      h += '<p class="fine center mt16">Entry should be declined. No bill can be posted for this member at this outlet.</p>';
    }
    return h + '</div>';
  };
  AFTER.verify = function (id) {
    var inp = $('billAmt'); if (!inp) return;
    var m = memberOf(id), b = biz(staff().biz);
    function upd() {
      inp.value = inp.value.replace(/\D/g, ''); ui.billAmt = inp.value;
      var amt = +inp.value, ok = amt >= BC_STAFF_UI.minBill, t = tierOfMember(id);
      $('postBill').disabled = !ok;
      $('billPts').innerHTML = ok ? 'Credits <b class="gold-text">' + num(earnFor(b.id, t.id, amt)) + ' ' + esc(b.short) + ' points</b> (' + t.name + ' · ' + b.earn[t.id] + ' per ₹100) and adds ' + inr(amt) + ' to the member’s tier spend.' : 'Enter the bill amount (min ' + inr(BC_STAFF_UI.minBill) + ') to see the points.';
    }
    inp.addEventListener('input', upd); upd();
  };

  /* ============================================================
     ACTIONS
     ============================================================ */
  var ACTIONS = {
    sendOtp: function () { if (/^[6-9]\d{9}$/.test(ui.mobile)) go('otp'); },
    sendStaffOtp: function () {
      var s = BC_STAFF.filter(function (x) { return x.mobile === ui.staffMobile; })[0];
      if (!s) { $('smobErr').textContent = 'This number is not registered as Boche business staff.'; return; }
      go('staff-otp');
    },
    resendOtp: function () { toast('OTP resent'); rerender(); },
    verifyOtp: function () {
      var code = Array.prototype.map.call($('otp').querySelectorAll('input'), function (x) { return x.value; }).join('');
      if (code === BC_BRAND.demoOtp) { SES.authed = true; ui.ob = { name: '', email: '' }; setPending('sim'); go('sim'); }
      else { $('otpErr').textContent = 'Incorrect OTP. Please try again.'; otpFail(); }
    },
    verifyStaffOtp: function () {
      var code = Array.prototype.map.call($('otp').querySelectorAll('input'), function (x) { return x.value; }).join('');
      var s = BC_STAFF.filter(function (x) { return x.mobile === ui.staffMobile; })[0];
      if (code === BC_BRAND.demoOtp && s) { SES.staffId = s.id; SES.outlet = s.outlets[0]; saveSes(); go('scan'); }
      else { $('otpErr').textContent = 'Incorrect OTP. Please try again.'; otpFail(); }
    },
    staffOutlet: function (el) { SES.outlet = el.dataset.id; saveSes(); rerender(); },
    staffLogout: function () { SES.staffId = null; saveSes(); ui.staffMobile = ''; go('welcome'); },
    admPick: function (el) { ui.adm.sel = el.dataset.id; ui.adm.skipArm = ui.adm.delArm = null; rerender(); },
    /* Delete today's completed draw: the day reopens empty (ADR-0009); first tap only asks */
    admDelArm: function () { var d = admDay(); if (d && d.canDelete) { ui.adm.delArm = d.label; rerender(); } },
    admDelCancel: function () { ui.adm.delArm = null; rerender(); },
    admDel: function () {
      var d = admDay(); if (!d || ui.adm.busy || ui.adm.delArm !== d.label) return; ui.adm.busy = true;
      BCAPI.post('/admin/draw-days/' + encodeURIComponent(d.label) + '/delete').then(function (day) {
        ui.adm.busy = false; ui.adm.delArm = null;
        ui.adm.days = ui.adm.days.map(function (x) { return x.label === day.label ? day : x; });
        rerender(); toast('Draw deleted · today’s draw is open again');
      }, function (e) { ui.adm.busy = false; ui.adm.delArm = null; toast(e.message || 'Could not delete the draw'); admLoad().then(rerender); });
    },
    /* Skip: a real day is sealed now (drand round ~30 s ahead), then the usual OTP → draw; first tap only asks */
    admSkipArm: function () { var d = admDay(); if (d && d.canSkip) { ui.adm.skipArm = d.label; rerender(); } },
    admSkipCancel: function () { ui.adm.skipArm = null; rerender(); },
    admSkip: function () {
      var d = admDay(); if (!d || ui.adm.busy || ui.adm.skipArm !== d.label) return; ui.adm.busy = true;
      BCAPI.post('/admin/draw-days/' + encodeURIComponent(d.label) + '/skip').then(function (day) {
        ui.adm.busy = false; ui.adm.skipArm = null;
        ui.adm.days = ui.adm.days.map(function (x) { return x.label === day.label ? day : x; });
        rerender(); toast('Entries closed · list sealed · OTP in about 30 s');
      }, function (e) { ui.adm.busy = false; ui.adm.skipArm = null; toast(e.message || 'Could not skip the wait'); admLoad().then(rerender); });
    },
    admReveal: function () { var d = admDay(); if (d && d.winners) playReveal(d.label, d.winners, []); },
    admNewTest: function () {
      if (ui.adm.busy) return; ui.adm.busy = true;
      BCAPI.post('/admin/test-days').then(function (day) { ui.adm.busy = false; ui.adm.sel = day.label; return admLoad().then(rerender); },
        function (e) { ui.adm.busy = false; toast(e.message || 'Could not create a test day'); });
    },
    /* One click = one server job of exactly 5,000 tickets; refreshing the page cannot add more */
    admSeed: function () {
      var d = admDay(); if (!d || (d.seeding && d.seeding.running)) return;
      BCAPI.post('/admin/test-days/' + encodeURIComponent(d.label) + '/seed-job', { count: 5000 }).then(function (job) {
        d.seeding = job; rerender(); admLoad();
      }, function (e) { toast(e.message || 'Could not add tickets'); admLoad(); });
    },
    admClose: function () {
      var d = admDay(); if (!d || ui.adm.busy) return; ui.adm.busy = true;
      BCAPI.post('/admin/test-days/' + encodeURIComponent(d.label) + '/close', { publishGapMinutes: 0 }).then(function (day) {
        ui.adm.busy = false; ui.adm.days = ui.adm.days.map(function (x) { return x.label === day.label ? day : x; }); rerender(); toast('Entries closed · list sealed');
      }, function (e) { ui.adm.busy = false; toast(e.message || 'Could not close'); });
    },
    admSendOtp: function () {
      var d = admDay(); if (!d || ui.adm.busy) return;
      ui.adm.busy = true;
      BCAPI.post('/admin/draw-days/' + encodeURIComponent(d.label) + '/otp').then(function (r) {
        ui.adm.busy = false; toast('OTP sent to the founder'); return admLoad().then(rerender);
      }, function (e) { ui.adm.busy = false; toast(e.message || 'Could not send the OTP'); });
    },
    admRun: function () {
      var d = admDay(); if (!d || ui.adm.busy || !$('otp')) return;
      var code = Array.prototype.map.call($('otp').querySelectorAll('input'), function (x) { return x.value; }).join('');
      if (!/^\d{4}$/.test(code)) return;
      ui.adm.busy = true;
      BCAPI.post('/admin/draw-days/' + encodeURIComponent(d.label) + '/run', { code: code }).then(function (day) {
        ui.adm.busy = false;
        ui.adm.days = ui.adm.days.map(function (x) { return x.label === day.label ? day : x; });
        rerender(); toast('Draw complete · 10 winners picked'); playChime();
      }, function (e) {
        ui.adm.busy = false;
        if ($('otpErr')) { $('otpErr').textContent = e.message || 'The draw could not run'; otpFail(); }
        if (e.status === 429 || e.status === 409 || e.status === 401 && /expired/.test(e.message)) admLoad().then(rerender);
      });
    },
    lookup: function () {
      var v = $('lookup').value, m = BC_MEMBERS.filter(function (x) { return x.mobile.replace(/\s/g, '') === v; })[0];
      if (!m) { $('lookErr').textContent = 'No Boche member with this number.'; return; }
      go('verify/' + m.id);
    },
    sendCheckinOtp: function (el) {
      var m = memberOf(el.dataset.id), o = staffOutlet();
      var code = BC_BRAND.demoOtp;
      S.pendingOtp = { memberId: m.id, outlet: o.id, code: code, ts: Date.now(), status: 'sent' };
      save(); rerender(); toast('OTP sent to +91 ' + m.mobile);
    },
    postBill: function (el) {
      var m = memberOf(el.dataset.id), o = staffOutlet(), st = staff(), b = biz(st.biz), amt = +ui.billAmt;
      if (!(amt >= BC_STAFF_UI.minBill)) return;
      var before = tierOfMember(m.id), pts = earnFor(b.id, before.id, amt), ref = o.id.toUpperCase().slice(0, 3) + '-' + Math.floor(10000 + Math.random() * 89999);
      dyn(m.id).spend[b.id] += amt; dyn(m.id).points[b.id] += pts;
      addHistory(m.id, b.id, 'Bill · ' + o.name, ref, pts);
      S.staffLog.unshift({ biz: st.biz, icon: 'receipt', text: 'Bill ' + inr(amt) + ' · +' + num(pts) + ' pts', member: m.name, outlet: o.city + ' ' + o.kind, time: timeLabel() });
      save(); ui.billAmt = '';
      var after = tierOfMember(m.id);
      rerender();
      toast(after.id !== before.id ? m.firstName + ' reached ' + after.name + '! +' + num(pts) + ' pts' : '+' + num(pts) + ' ' + b.short + ' points credited to ' + m.firstName);
    },
    useVoucher: function (el) {
      var d = dyn(el.dataset.mem), st = staff(), m = memberOf(el.dataset.mem);
      d.vouchers.forEach(function (v) { if (v.code === el.dataset.id) { v.used = true; S.staffLog.unshift({ biz: st.biz, icon: 'gift', text: 'Voucher redeemed · ' + v.title, member: m.name, outlet: staffOutlet().city + ' ' + staffOutlet().kind, time: timeLabel() }); } });
      save(); rerender(); toast('Voucher marked as redeemed');
    },
    kycSendOtp: function () { if (!aadhaarOk(ui.kyc.no) || !ui.kyc.consent) return; ui.kyc.step = 'otp'; rerender(); toast('OTP sent to your Aadhaar-linked mobile'); },
    kycEdit: function () { ui.kyc.step = 'no'; rerender(); },
    kycCancel: function () { var back = ui.kycBack; kycReset(); go(back); },
    kycVerify: function () {
      var code = Array.prototype.map.call($('otp').querySelectorAll('input'), function (x) { return x.value; }).join('');
      if (code !== BC_KYC.demoOtp) { $('otpErr').textContent = 'Incorrect OTP. Please try again.'; otpFail(); return; }
      var last4 = ui.kyc.no.slice(-4);
      ui.sheetLock = true;
      openSheet('<h3>Verifying with UIDAI</h3><ul class="steps" id="kycSteps">' +
        BC_KYC.steps.map(function (s) { return '<li><span class="st"></span>' + esc(s) + '</li>'; }).join('') + '</ul>');
      runSteps($('kycSteps').children, function () {
        ui.sheetLock = false; kycReset();
        dyn(BC_MEMBER.id).kyc = { aadhaarMasked: 'XXXX XXXX ' + last4, method: 'Aadhaar OTP', verifiedOn: todayLabel() }; save();
        go('kyc-done/' + encodeURIComponent(ui.kycBack));
      });
    },
    sendEmailCode: function () { ui.dev = { sent: true }; rerender(); toast('Code sent to ' + maskEmail(BC_MEMBER.email)); },
    verifyEmail: function () {
      var code = Array.prototype.map.call($('otp').querySelectorAll('input'), function (x) { return x.value; }).join('');
      if (code !== BC_BRAND.demoEmailOtp) { $('otpErr').textContent = 'Incorrect code. Please try again.'; otpFail(); return; }
      var pf = dyn(BC_MEMBER.id).profile; if (pf) { pf.emailVerified = true; save(); }
      ui.dev = null; toast('This phone is now trusted'); finishLogin();
    },
    saveName: function () {
      if (!obOk()) return;
      dyn(BC_MEMBER.id).profile = { name: ui.ob.name.trim().replace(/\s+/g, ' '), email: ui.ob.email.trim(), mobile: ui.mobile ? fmtMobile(ui.mobile) : BC_MEMBER.mobile };
      save(); applyProfile(); setPending(null); go('hi');
    },
    devices: function () {
      var me = deviceId();
      openSheet('<h3>Trusted phones</h3><p class="lead">Signing in on any other phone needs SIM and email verification.</p><div class="list mt16">' +
        myDevices().map(function (d) { return '<div class="li"><span class="li-ic">' + ic('phone', 16) + '</span><div class="li-main"><div class="li-t">' + esc(d.label) + (d.id === me ? ' <span class="badge ok">This phone</span>' : '') + '</div><div class="li-s">Added ' + esc(d.added) + '</div></div></div>'; }).join('') +
        '</div><button class="btn btn-line mt16" data-act="demoNewDevice">Demo: sign in as a new phone</button>');
    },
    demoNewDevice: function () { try { localStorage.removeItem(DEV_KEY); } catch (e) {} closeSheet(); ACTIONS.logout(); toast('Sign in again to see the new-phone check'); },
    openApp: function (el) {
      var b = biz(el.dataset.id);
      ui.sheetLock = true;
      openSheet('<h3>Opening ' + esc(b.appName) + '</h3><p class="lead">Single sign-on with your Boche identity</p><ul class="steps" id="ssoSteps">' +
        BC_SSO_STEPS.map(function (s) { return '<li><span class="st"></span>' + esc(s.replace('{app}', b.appName)) + '</li>'; }).join('') + '</ul>');
      runSteps($('ssoSteps').children, function () { ui.sheetLock = false; closeSheet(); go('app/' + b.id); }, 600);
    },
    codeEnter: function () {
      var wrap = $('code4'), ins = wrap.querySelectorAll('input');
      var code = Array.prototype.map.call(ins, function (x) { return x.value; }).join('');
      var p = S.pendingOtp;
      var valid = p && p.memberId === BC_MEMBER.id && p.status === 'sent' && code === p.code && (Date.now() - p.ts) < BC_STAFF_UI.otpValidMinutes * 60000;
      /* Prototype: the demo OTP always works, even if no venue has sent a code */
      if (!valid && code === BC_BRAND.demoOtp) {
        var dv = outlet(BC_MEMBER.homeOutlet); if (!eligible(dv)) dv = BC_OUTLETS.filter(function (x) { return eligible(x); })[0] || dv;
        p = S.pendingOtp = { memberId: BC_MEMBER.id, outlet: dv.id, code: code, ts: Date.now(), status: 'sent' }; valid = true;
      }
      if (!valid) {
        wrap.classList.add('bad'); Array.prototype.forEach.call(ins, function (x) { x.value = ''; }); ins[0].focus(); $('codeGo').disabled = true;
        toast('That OTP isn’t valid or has expired. Ask the venue to resend it.'); return;
      }
      var o = outlet(p.outlet), ok = eligible(o), b = biz(o.biz), need = o.ageGate ? BC_STATES[o.state].drinkingAge : null;
      p.status = 'used';
      if (ok) {
        dyn(BC_MEMBER.id).checkins.unshift({ outlet: o.id, date: todayLabel(), time: timeLabel() });
        S.staffLog.unshift({ biz: o.biz, icon: 'qr', text: o.checkinLabel + ' · check-in (OTP verified)', member: BC_MEMBER.name, outlet: o.city + ' ' + o.kind, time: timeLabel() });
      }
      save();
      if (ok) { showWelcome(o, b, need); return; }
      openSheet('<div class="center"><div class="big-check" style="' + (ok ? '' : 'background:var(--err);color:#fff;box-shadow:none') + '">' + ic(ok ? 'check' : 'x', 34) + '</div>' +
        '<h3>' + (ok ? 'You’re checked in' : ageState(o) === 'verify' ? 'Verify your age first' : 'Entry not allowed') + '</h3><p class="lead">' + esc(o.name) + '</p>' +
        '<p class="fine">' + (ok ? esc(o.checkinLabel) + ' recorded at ' + esc(timeLabel()) + (o.ageGate ? ' · age verified for ' + need + '+' : '') + '. Earn ' + esc(b.short) + ' points on your bill.' : (ageState(o) === 'verify' ? 'This venue is ' + need + '+. Verify once, then ask staff to resend the OTP.' : 'Your verified age does not meet the ' + need + '+ rule in ' + esc(BC_STATES[o.state].name) + '.')) + '</p>' +
        (ageState(o) === 'verify' ? '<button class="btn btn-gold mt16" data-go="' + verifyRoute('card') + '">Verify my age</button>' : '<button class="btn btn-gold mt16" data-act="closeSheetRender">' + (ok ? 'Done' : 'Close') + '</button>') + '</div>');
    },
    teaQty: function (el) {
      var q = ui.tea.qty, id = el.dataset.id; q[id] = Math.max(0, Math.min(BC_TEA.maxQty, q[id] + (+el.dataset.d))); rerender();
    },
    addrPo: function (el) { (parse().name === 'address' ? ui.addrEd : ui.tea).area.po = el.dataset.id; rerender(); },
    editAddress: function (el) {
      var id = el.dataset.id, sv = addrList().filter(function (a) { return a.id === id; })[0];
      if (sv) { ui.addrEd = addrFromSaved(sv); ui.addrEd.id = sv.id; ui.addrEd.label = sv.label || 'Home'; }
      else { ui.addrEd = addrBlank(); ui.addrEd.label = addrList().some(function (a) { return a.label === 'Home'; }) ? 'Other' : 'Home'; }
      go('address');
    },
    addrLabel: function (el) { ui.addrEd.label = el.dataset.id; rerender(); },
    saveAddress: function () {
      var A = ui.addrEd; if (!addrOk(A)) return;
      var sv = addrToSaved(A); sv.id = A.id; sv.label = A.label;
      addrUpsert(sv);
      if (!teaCount()) { ui.tea.addr = { pin: '', name: '', house: '', street: '' }; ui.tea.area = null; ui.tea.pick = null; }
      ui.addrEd = null; toast('Address saved');
      if (navStack.length > 1) history.back(); else go('addresses');
    },
    defAddress: function (el) { dyn(BC_MEMBER.id).defaultAddr = el.dataset.id; save(); rerender(); toast('Default address updated'); },
    delAddress: function (el) {
      openSheet('<h3>Delete this address?</h3><p class="lead">' + esc(addrLine(addrList().filter(function (a) { return a.id === el.dataset.id; })[0])) + '</p>' +
        '<div class="btn-row mt16"><button class="btn btn-line" data-act="closeSheet">Cancel</button><button class="btn btn-gold" data-act="confirmDelAddress" data-id="' + el.dataset.id + '">Delete</button></div>');
    },
    confirmDelAddress: function (el) {
      var d = dyn(BC_MEMBER.id); d.addresses = addrList().filter(function (a) { return a.id !== el.dataset.id; });
      if (d.defaultAddr === el.dataset.id) d.defaultAddr = d.addresses[0] ? d.addresses[0].id : null;
      if (ui.tea.pick === el.dataset.id) { ui.tea.pick = null; ui.tea.addr = { pin: '', name: '', house: '', street: '' }; ui.tea.area = null; }
      save(); closeSheet(); rerender(); toast('Address deleted');
    },
    teaPickAddr: function (el) {
      var sv = addrList().filter(function (a) { return a.id === el.dataset.id; })[0]; if (!sv) return;
      var A = addrFromSaved(sv); ui.tea.addr = A.addr; ui.tea.area = A.area; ui.tea.look = 'idle'; ui.tea.pick = sv.id; rerender();
    },
    teaNewAddr: function () { var A = addrBlank(); ui.tea.addr = A.addr; ui.tea.area = null; ui.tea.look = 'idle'; ui.tea.err = ''; ui.tea.pick = 'new'; rerender(); },
    emailOpen: function () { ui.em = { email: BC_MEMBER.email, step: 'edit' }; go('email'); },
    emailSend: function () { if (!emailOk(ui.em.email)) return; ui.em.email = ui.em.email.trim(); ui.em.step = 'code'; rerender(); toast('Code sent to ' + maskEmail(ui.em.email)); },
    emailEdit: function () { ui.em.step = 'edit'; rerender(); },
    emailVerify: function () {
      var code = Array.prototype.map.call($('otp').querySelectorAll('input'), function (x) { return x.value; }).join('');
      if (code !== BC_BRAND.demoEmailOtp) { $('otpErr').textContent = 'Incorrect code. Please try again.'; otpFail(); return; }
      var d = dyn(BC_MEMBER.id); d.profile = d.profile || { name: BC_MEMBER.name, mobile: BC_MEMBER.mobile };
      d.profile.email = ui.em.email; d.profile.emailVerified = true; save(); applyProfile();
      ui.em = null; toast('Email verified'); if (navStack.length > 1) history.back(); else go('profile');
    },
    /* Pay: the server prices the order first; UPI app chooser → simulated Google Pay screen → UPI PIN →
       mock provider confirms with a signed message → the server issues the scratch cards (nothing is charged) */
    teaPay: function () {
      if (ui.pay && ui.pay.busy) return;
      var sub = teaSubtotal(), lg = teaLogistics(), g = teaGst(sub, lg), items = {};
      teaItems().forEach(function (i) { items[i.pack.id] = i.qty; });
      ui.pay = { sub: sub, lg: lg, g: g, tot: Math.round((sub + lg + g.total) * 100) / 100, app: 'gpay', pin: '', busy: true };
      var a = ui.tea.addr, area = ui.tea.area;
      BCAPI.post('/orders', { items: items, delivery: { name: a.name.trim(), house: a.house.trim(), street: a.street.trim(), pin: a.pin, po: area.po || '', district: area.district } })
        .then(function (o) { ui.pay.orderId = o.id; ui.pay.tot = o.totalPaise / 100; ui.pay.busy = false; ui.sheetLock = false; payChooser(); })
        .catch(function (e) { ui.pay = null; toast(e.status === 401 ? 'Please sign in again' : e.status === 422 ? 'Please check your bag and address' : 'Could not start the payment. Try again.'); if (e.status === 401) ACTIONS.logout(); });
    },
    payApp: function (el) { ui.pay.app = el.dataset.app; payApp(); },
    payPin: function () { ui.pay.pin = ''; payPinSheet(); },
    pinKey: function (el) {
      var P = ui.pay; if (!P || P.pin.length >= 4) return;
      P.pin += el.dataset.k; payDots();
      if (P.pin.length === 4) {
        ui.sheetLock = true;
        setTimeout(function () {
          openSheet('<div class="gp-done" id="gpDone"><span class="gp-spin"></span><b>Processing payment…</b><span>Do not press back</span></div>');
          var minWait = new Promise(function (res) { setTimeout(res, 1300); });
          Promise.all([BCAPI.post('/payments/mock/' + encodeURIComponent(P.orderId) + '/pay'), minWait]).then(function (r) {
            $('gpDone').innerHTML = '<span class="gp-ok">' + ic('check', 30) + '</span><b>Payment successful</b><span>' + inr(P.tot) + ' paid to Boche</span>';
            setTimeout(function () { ui.sheetLock = false; closeSheet(); ACTIONS.teaPlace(r[0]); }, 1100);
          }).catch(function () {
            ui.sheetLock = false; closeSheet(); ui.pay = null; toast('Payment could not be confirmed. Nothing was charged; please try again.');
          });
        }, 250);
      }
    },
    pinDel: function () { var P = ui.pay; if (!P || P.pin.length >= 4) return; P.pin = P.pin.slice(0, -1); payDots(); },
    /* The server has confirmed the payment and issued the cards: show the order it returned */
    teaPlace: function (paid) {
      var sub = ui.pay.sub, d = dyn(BC_MEMBER.id);
      var mine = fromServerOrder(paid);
      ORDERS = [mine].concat(teaOrders().filter(function (o) { return o.id !== mine.id; }));
      if (ui.tea.pick === 'new' || !addrList().length) { var nsv = addrToSaved(ui.tea); nsv.label = addrList().some(function (a) { return a.label === 'Home'; }) ? 'Other' : 'Home'; ui.tea.pick = addrUpsert(nsv).id; }
      d.spend.tea = (d.spend.tea || 0) + sub;
      save();
      ui.tea.qty = teaBlankBag(); ui.pay = null;
      go('tea-done/' + mine.id);
    },
    scratchReveal: function (el) { var x = cardById(el.dataset.id); if (!x || x.c.scratched) return; x.c.scratched = true; markScratched(x.c.id); rerender(); },
    drawSubmit: function (el) {
      var x = cardById(el.dataset.id); if (!x || x.c.submitted) return;
      var c = x.c;
      ui.sheetLock = true;
      openSheet('<h3>Entering the Lucky Draw</h3><p class="lead">' + numsLabel(c.nos.length) + '</p><ul class="steps" id="drawSteps">' +
        ['Sending ' + (c.nos.length > 1 ? 'your numbers' : 'your number') + ' to Boche', 'Checking it’s valid and unused', 'Entry confirmed'].map(function (s) { return '<li><span class="st"></span>' + esc(s) + '</li>'; }).join('') + '</ul>');
      /* The server decides the Draw day by its own IST clock (before 8 PM: today; after: tomorrow) */
      var entry = BCAPI.post('/draw/entries', { cardId: c.id });
      var shown = new Promise(function (res) { runSteps($('drawSteps').children, res, 550); });
      Promise.all([entry, shown]).then(function (r) {
        ui.sheetLock = false; closeSheet();
        var key = r[0].drawDay;
        c.submitted = true; c.drawDate = key; ui.justEntered = c.id; rerender(); ui.justEntered = null; playChime();
      }, function (e) {
        shown.then(function () {
          ui.sheetLock = false; closeSheet();
          toast(e.status === 409 ? (e.message || 'This card can’t be entered') : e.status === 401 ? 'Please sign in again' : 'Could not enter the draw. Please try again.');
          refreshOrders(true);
        });
      });
    },
    /* Claim a Lucky Draw win: confirm payout account → paid (prototype: nothing is really sent) */
    claimPrize: function (el) { go('claim/' + el.dataset.id); },
    claimSubmit: function (el) {
      var x = cardById(el.dataset.id); if (!x || x.c.claimed) return;
      var q = cardState(x.c); if (!q.win) return;
      ui.sheetLock = true;
      openSheet('<h3>Submitting your claim</h3><ul class="steps" id="claimSteps">' +
        ['Sending your details', 'Verifying your lucky number', 'Claim received'].map(function (s) { return '<li><span class="st"></span>' + esc(s) + '</li>'; }).join('') + '</ul>');
      var sent = BCAPI.post('/claims', { cardId: x.c.id });
      var shown = new Promise(function (res) { runSteps($('claimSteps').children, res, 600); });
      Promise.all([sent, shown]).then(function (r) {
        ui.sheetLock = false; x.c.claimed = { ts: r[0].ts, amount: r[0].amount, ref: r[0].ref };
        closeSheet(); rerender(); toast('Claim submitted');
      }, function (e) {
        shown.then(function () { ui.sheetLock = false; closeSheet(); toast(e.message || 'Could not submit the claim. Please try again.'); });
      });
    },
    grvNew: function () { ui.grv = { biz: null, text: '', files: [], focusText: false }; go('grievance'); },
    grvBiz: function (el) { var first = !ui.grv.biz; ui.grv.biz = el.dataset.id; ui.grv.focusText = first; rerender(); },
    grvRemove: function (el) { ui.grv.files.splice(+el.dataset.id, 1); rerender(); },
    grvSubmit: function () {
      if (!grvOk()) return;
      var d = dyn(BC_MEMBER.id), g = ui.grv, id = 'CMP-' + Math.floor(100000 + Math.random() * 899999);
      ui.sheetLock = true;
      openSheet('<h3>Submitting your complaint</h3><ul class="steps" id="grvSteps">' +
        ['Uploading details' + (g.files.length ? ' and ' + g.files.length + (g.files.length > 1 ? ' files' : ' file') : ''), 'Assigning to ' + grvTarget(g.biz).label + ' support', 'Ticket created'].map(function (s) { return '<li><span class="st"></span>' + esc(s) + '</li>'; }).join('') + '</ul>');
      runSteps($('grvSteps').children, function () {
        ui.sheetLock = false;
        d.tickets = d.tickets || [];
        d.tickets.unshift({ id: id, biz: g.biz, text: g.text.trim(), files: g.files, date: todayLabel(), status: 'Open' });
        save(); ui.grv = { biz: null, text: '', files: [], focusText: false }; ui.grvJustSent = id;
        go('ticket/' + id);
      }, 550);
    },
    grvDone: function () { ui.grvJustSent = null; go('support'); },
    pageMenu: function (el) { var v = el.dataset.id; ui.pageMenu = v && ui.pageMenu !== v ? v : false; rerender(); },
    back: function (el) { if (navStack.length > 1) history.back(); else go(el.dataset.id); },
    noop: function () {},
    childItem: function (el) { toast(el.dataset.id + ' opens in the business app'); },
    soonBiz: function (el) { toast(biz(el.dataset.id).name + ' joins Boche soon'); },
    notifs: function () { toast('You’re all caught up'); },
    flip: function () { $('flip').classList.toggle('flipped'); },
    drawDay: function (el) { ui.drawSel = ui.drawSel === el.dataset.id ? null : el.dataset.id; rerender(); },
    photoPick: function () { var f = $('photoIn'); if (f) f.click(); },
    exploreFilter: function (el) { ui.exploreFilter = el.dataset.id; rerender(); },
    actTab: function (el) { ui.actTab = el.dataset.id; rerender(); },
    actBiz: function (el) { ui.actBiz = el.dataset.id; rerender(); },
    redeem: function (el) {
      var r = byId(BC_REWARDS, el.dataset.id), b = biz(r.biz), pts = pointsOf(BC_MEMBER.id, b.id);
      if (pts < b.minRedeem) { toast('Minimum ' + num(b.minRedeem) + ' points to redeem at ' + b.name); return; }
      openSheet('<h3>Redeem reward</h3><p class="lead">' + esc(r.title) + ' · ' + esc(b.name) + '</p><div class="surface mt16" style="padding:4px 16px">' +
        '<div class="kv"><span>Cost</span><span>' + num(r.pts) + ' ' + esc(b.short) + ' pts</span></div><div class="kv"><span>Balance after</span><span>' + num(pts - r.pts) + ' pts</span></div></div>' +
        '<p class="fine">Honoured only at ' + esc(b.name) + '. Show the voucher with your card.</p>' +
        '<div class="btn-row mt16"><button class="btn btn-line" data-act="closeSheet">Cancel</button><button class="btn btn-gold" data-act="confirmRedeem" data-id="' + r.id + '">Redeem</button></div>');
    },
    confirmRedeem: function (el) {
      var r = byId(BC_REWARDS, el.dataset.id), b = biz(r.biz), d = dyn(BC_MEMBER.id);
      if (d.points[b.id] < r.pts) return;
      var code = 'BC-' + rand(6);
      d.points[b.id] -= r.pts; d.vouchers.unshift({ biz: b.id, title: r.title, code: code, date: todayLabel(), used: false });
      addHistory(BC_MEMBER.id, b.id, 'Redeemed · ' + r.title, code, -r.pts); save();
      openSheet('<div class="center"><div class="big-check">' + ic('gift', 32) + '</div><h3>Reward unlocked</h3><p class="lead">' + esc(r.title) + '</p>' +
        '<div class="voucher mt16"><div class="li-s">Voucher code</div><div class="code">' + esc(code) + '</div></div>' +
        '<p class="fine">Show this code with your card at ' + esc(b.name) + '.</p><button class="btn btn-gold mt16" data-act="closeSheetRender">Done</button></div>');
    },
    bookDay: function (el) { ui.book.day = +el.dataset.id; rerender(); },
    bookTime: function (el) { ui.book.time = el.dataset.id; rerender(); },
    bookOcc: function (el) { ui.book.occasion = el.dataset.id; rerender(); },
    guests: function (el) { ui.book.guests = Math.max(1, Math.min(BC_BOOKING.maxGuests, ui.book.guests + (+el.dataset.id))); rerender(); },
    confirmBook: function (el) {
      var o = outlet(el.dataset.id), b = ui.book, d = new Date(); d.setDate(d.getDate() + b.day);
      var when = d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' }) + ', ' + b.time, ref = 'BK-' + rand(5);
      S.bookings.unshift({ ref: ref, outlet: o.name, when: when, guests: b.guests }); save(); resetBook();
      openSheet('<div class="center"><div class="big-check">' + ic('calendar', 32) + '</div><h3>Table booked</h3><p class="lead">' + esc(o.name) + '</p></div>' +
        '<div class="surface mt16" style="padding:4px 16px"><div class="kv"><span>When</span><span>' + esc(when) + '</span></div><div class="kv"><span>Guests</span><span>' + b.guests + '</span></div>' +
        '<div class="kv"><span>Booking ref</span><span>' + esc(ref) + '</span></div></div>' +
        '<p class="fine center">Sent to ' + esc(biz(o.biz).appName) + '. Show your card on arrival.</p><button class="btn btn-gold mt16" data-act="bookDone" data-id="' + o.id + '">Done</button>');
    },
    bookDone: function (el) { closeSheet(); go('outlet/' + el.dataset.id); },
    offersTab: function (el) { ui.offersTab = el.dataset.id; rerender(); },
    openEvents: function () { ui.offersTab = 'events'; go('offers'); },
    activate: function (el) {
      var i = S.activated.indexOf(el.dataset.id);
      if (i > -1) { S.activated.splice(i, 1); toast('Offer deactivated'); }
      else { S.activated.push(el.dataset.id); toast('Offer activated — applies when staff scan your card'); }
      save(); rerender();
    },
    reserve: function (el) {
      var i = S.reserved.indexOf(el.dataset.id);
      if (i > -1) { S.reserved.splice(i, 1); toast('Reservation cancelled'); }
      else { S.reserved.push(el.dataset.id); toast('Spot reserved — see you there!'); }
      save(); rerender();
    },
    notif: function (el) { var k = el.dataset.id; S.notif[k] = !S.notif[k]; save(); el.classList.toggle('on', S.notif[k]); },
    install: function () {
      if (deferredPrompt) { deferredPrompt.prompt(); deferredPrompt.userChoice.then(function () { deferredPrompt = null; }); return; }
      var ios = isIOS();
      openSheet('<h3>Add to home screen</h3><p class="lead">Boche installs straight from your browser — no app store needed.</p>' +
        '<div class="field-l">' + (ios ? 'On iPhone (Safari)' : 'On Android (Chrome)') + '</div><ol class="howto">' +
        (ios ? '<li>Tap the Share button ' + icInline('share', 16) + ' at the bottom of Safari.</li><li>Scroll and tap <b>Add to Home Screen</b>.</li><li>Tap <b>Add</b> — Boche appears with your apps.</li>'
          : '<li>Tap the ⋮ menu at the top right of Chrome.</li><li>Tap <b>Install app</b> or <b>Add to Home screen</b>.</li><li>Confirm — Boche opens full-screen like any app.</li>') +
        '</ol><button class="btn btn-gold mt24" data-act="closeSheet">Got it</button>');
    },
    resetDemo: function () {
      S = freshShared(); save(); SES = { authed: false, pending: null, staffId: null, outlet: null }; saveSes();
      ui.mobile = ''; ui.staffMobile = ''; kycReset(); ui.billAmt = ''; resetBook(); applyProfile(); toast('Demo reset'); go('welcome');
    },
    logout: function () {
      BCAPI.post('/auth/logout').catch(function () {});
      try { window.google.accounts.id.disableAutoSelect(); } catch (e) {}
      ME = null; ORDERS = null; ordersAt = 0; applyProfile(); SES.authed = false; SES.pending = null; saveSes(); go('welcome');
    },
    closeSheet: function () { closeSheet(); },
    wxClose: function () { var w = $('wx'); if (!w) return; w.classList.add('out'); setTimeout(function () { w.remove(); rerender(); }, 350); },
    demoOtp: function () {
      var o = outlet(BC_MEMBER.homeOutlet); if (!eligible(o)) o = BC_OUTLETS.filter(function (x) { return eligible(x); })[0] || o; var code = BC_BRAND.demoOtp;
      S.pendingOtp = { memberId: BC_MEMBER.id, outlet: o.id, code: code, ts: Date.now(), status: 'sent' }; save();
      toast('SMS · ' + code + ' is your Boche check-in OTP for ' + o.name, 9000);
    },
    closeSheetRender: function () { closeSheet(); rerender(); }
  };

  function runSteps(lis, done, gap) {
    var i = 0; gap = gap || 750;
    (function step() {
      if (i > 0) { lis[i - 1].className = 'done'; lis[i - 1].firstChild.innerHTML = ic('check', 14); }
      if (i < lis.length) { lis[i].className = 'active'; i++; timers.push(setTimeout(step, gap)); }
      else timers.push(setTimeout(done, 450));
    })();
  }

  /* ============================================================
     SHELL: router, sheet, toast, tabs
     ============================================================ */
  /* Google sign-in replaced the mobile OTP, SIM and new-phone steps, so the old OTP screen is no longer a way in */
  var MEMBER_PUBLIC = { welcome: 1, login: 1 };
  var STAFF_PUBLIC = { staff: 1, 'staff-otp': 1 };
  var STAFF_APP = { scan: 1, verify: 1 };
  var ADMIN_APP = { 'admin-draw': 1 };
  var TABS = { home: 1, explore: 1, card: 1, activity: 1, profile: 1, tea: 1, 'tea-orders': 1, 'my-numbers': 1, 'my-wins': 1, draw: 1, scratch: 1, 'tea-done': 1 };
  /* Tea screens keep the bottom bar (checkout steps don't, they have their own pay bar); Explore is their home tab */
  var TAB_OF = { tea: 'home', 'tea-orders': 'home', draw: 'draw', 'my-numbers': 'draw', 'my-wins': 'draw', activity: 'profile', scratch: 'draw', 'tea-done': 'home' };
  var timers = [];
  function clearTimers() { timers.forEach(function (t) { clearInterval(t); clearTimeout(t); }); timers = []; }
  /* Clean URLs (/draw, /verify-draw/2026-11-10) through the History API; the server returns the app for any of them */
  function parse() { var p = location.pathname.replace(/^\/+/, '').split('/'); return { name: p[0] || '', arg: decodeURIComponent(p[1] || '') }; }
  function go(path) { var url = '/' + path; if (location.pathname !== url) history.pushState(null, '', url); render(); }
  function resolve(r) {
    if (STAFF_PUBLIC[r.name]) return SES.staffId ? { name: 'scan', arg: '' } : r;
    if (STAFF_APP[r.name]) return SES.staffId ? r : { name: 'staff', arg: '' };
    if (ADMIN_APP[r.name]) return ME && ME.role === 'admin' ? r : { name: 'staff', arg: '' };
    if (r.name === 'verify-draw') return r;   /* public: anyone can check a draw, signed in or not */
    if (!SES.authed) return MEMBER_PUBLIC[r.name] ? r : { name: 'welcome', arg: '' };
    if (SES.pending) return { name: SES.pending, arg: '' };
    if (r.name !== 'tea') ui.teaMenu = false;
    if (MEMBER_PUBLIC[r.name] || !SCREENS[r.name]) return { name: 'home', arg: '' };
    if ((r.name === 'tea-address' || r.name === 'tea-pay') && !teaCount()) return { name: 'tea', arg: '' };
    if (r.name === 'tea-address') teaPrefill();
    if (r.name === 'address' && !ui.addrEd) { ui.addrEd = addrBlank(); ui.addrEd.label = 'Home'; }
    if (r.name === 'email' && !ui.em) ui.em = { email: BC_MEMBER.email, step: 'edit' };
    if (r.name === 'tea-pay' && !teaAddrOk()) return { name: 'tea-address', arg: '' };
    if (r.name === 'biz' && biz(r.arg) && biz(r.arg).route) return { name: biz(r.arg).route, arg: '' };
    if (r.name === 'book' && outlet(r.arg) && ageState(outlet(r.arg)) === 'verify') return { name: 'kyc', arg: 'book/' + r.arg };
    return r;
  }
  /* In-app history so Back returns to the screen the member came from, not a fixed parent */
  var navStack = [];
  function trackNav() {
    var h = location.pathname;
    if (navStack[navStack.length - 1] === h) return;
    if (navStack[navStack.length - 2] === h) navStack.pop(); else navStack.push(h);
  }
  function render(keepScroll) {
    if (!keepScroll) trackNav();
    var r = resolve(parse()), scr = $('screen'), top = scr.scrollTop;
    if (REVEAL_STOP && r.name !== 'draw' && r.name !== 'admin-draw') REVEAL_STOP();
    if (!keepScroll) { clearTimers(); closeSheet(true); ui.pageMenu = false; ui.teaSeen = false; ui.revealDue = r.name === 'draw'; }
    $('device').classList.toggle('has-tabs', !!TABS[r.name]);
    scr.innerHTML = SCREENS[r.name](r.arg);
    scr.scrollTop = keepScroll ? top : 0;
    renderTabs(TAB_OF[r.name] || r.name);
    if (AFTER[r.name]) AFTER[r.name](r.arg);
    if (!keepScroll && ORDER_SCREENS[r.name]) { refreshOrders(); refreshResults(); }   /* pick up orders placed on another device */
  }
  function rerender() { clearTimers(); render(true); }

  function renderTabs(active) {
    var items = [['home', 'Home', 'home'], ['draw', 'Lucky Draw', 'crown'], ['card', 'Card', 'qr'], ['explore', 'Explore', 'pin'], ['profile', 'Profile', 'user']];
    $('tabbar').innerHTML = items.map(function (t) {
      var on = active === t[0] ? ' on' : '';
      if (t[0] === 'card') return '<button class="tab tab-card' + on + '" data-go="card"><span class="fab">' + ic('qr', 26) + '</span><span>Card</span></button>';
      return '<button class="tab' + on + '" data-go="' + t[0] + '">' + ic(t[2]) + '<span>' + t[1] + '</span></button>';
    }).join('');
  }

  /* ----- Simulated UPI payment (prototype only: nothing is charged) ----- */
  var UPI_APPS = [['gpay', 'Google Pay', 'G'], ['phonepe', 'PhonePe', 'P'], ['paytm', 'Paytm', 'P']];
  function upiName() { return (byApp(ui.pay.app) || UPI_APPS[0])[1]; }
  function byApp(id) { return UPI_APPS.filter(function (a) { return a[0] === id; })[0]; }
  function payChooser() {
    openSheet('<h3>Pay ' + inr(ui.pay.tot) + '</h3><p class="lead">Choose a UPI app</p><div class="upi-list">' +
      UPI_APPS.map(function (a) { return '<button class="upi-app" data-act="payApp" data-app="' + a[0] + '"><span class="upi-ic ' + a[0] + '">' + a[2] + '</span><span>' + a[1] + '</span>' + ic('back', 14) + '</button>'; }).join('') + '</div>' +
      '<p class="fine center mt12">' + ic('lock', 12) + ' Secure UPI payment</p>');
  }
  function payApp() {
    openSheet('<div class="gp"><div class="gp-top"><span class="gp-logo">' + (ui.pay.app === 'gpay' ? '<b class="g1">G</b><b class="g2">o</b><b class="g3">o</b><b class="g4">g</b><b class="g5">l</b><b class="g6">e</b> Pay' : esc(upiName())) + '</span><span class="gp-sec">' + ic('lock', 12) + ' Secure</span></div>' +
      '<div class="gp-to"><span class="gp-av">B</span><div><b>Boche</b><span>boche.club@upi</span></div></div>' +
      '<div class="gp-amt">' + inr(ui.pay.tot) + '</div>' +
      '<div class="gp-bank"><span class="gp-bk">' + ic('shield', 16) + '</span><div><b>HDFC Bank ••4321</b><span>Savings account</span></div></div>' +
      '<button class="btn btn-gold" data-act="payPin">Pay ' + inr(ui.pay.tot) + '</button></div>');
  }
  function payPinSheet() {
    openSheet('<div class="gp"><div class="gp-top"><span class="gp-logo">Enter UPI PIN</span><span class="gp-sec">' + inr(ui.pay.tot) + '</span></div>' +
      '<p class="gp-sub">HDFC Bank ••4321 · to Boche</p><div class="gp-dots" id="gpDots"><i></i><i></i><i></i><i></i></div>' +
      '<div class="gp-pad">' + ['1', '2', '3', '4', '5', '6', '7', '8', '9', '', '0', '⌫'].map(function (k) {
        return k === '' ? '<span></span>' : '<button data-act="' + (k === '⌫' ? 'pinDel' : 'pinKey') + '" data-k="' + k + '" aria-label="' + (k === '⌫' ? 'Delete' : k) + '">' + k + '</button>';
      }).join('') + '</div><div class="demo-hint">Demo: enter any 4 digits</div></div>');
  }
  function payDots() { var d = $('gpDots'); if (d) [].forEach.call(d.children, function (e, i) { e.className = i < ui.pay.pin.length ? 'on' : ''; }); }

  function openSheet(html) { $('sheet').innerHTML = '<div class="sheet-grip"></div>' + html; $('sheet').classList.add('open'); $('sheetBackdrop').classList.add('open'); }
  function closeSheet(force) {
    if (ui.sheetLock && !force) return;
    $('sheet').classList.remove('open'); $('sheetBackdrop').classList.remove('open');
  }
  var toastT;
  function toast(msg, ms) {
    var t = $('toast'); t.textContent = msg; t.classList.add('show');
    clearTimeout(toastT); toastT = setTimeout(function () { t.classList.remove('show'); }, ms || 2800);
  }

  document.addEventListener('click', function (e) {
    var a = e.target.closest('[data-act]');
    if (a && !a.disabled && ACTIONS[a.dataset.act]) { e.preventDefault(); e.stopPropagation(); ACTIONS[a.dataset.act](a); return; }
    var g = e.target.closest('[data-go]');
    if (g && !g.disabled) { e.preventDefault(); go(g.dataset.go); return; }
    /* In-app links (<a href="/tiers">) change screens without reloading; files, API and new-tab links load normally */
    var l = e.target.closest('a[href^="/"]');
    if (l && !l.target && !l.hasAttribute('download') && l.getAttribute('href').indexOf('/api/') !== 0 && !e.ctrlKey && !e.metaKey && !e.shiftKey) {
      e.preventDefault(); go(l.getAttribute('href').slice(1));
    }
  });
  $('sheetBackdrop').addEventListener('click', function () { closeSheet(); });
  /* A mouse wheel scrolls sideways rows (.scroll-x) too; trackpads already swipe them */
  document.addEventListener('wheel', function (e) {
    var row = e.target.closest && e.target.closest('.scroll-x');
    if (!row || row.scrollWidth <= row.clientWidth || Math.abs(e.deltaX) > Math.abs(e.deltaY)) return;
    /* Some browsers (Firefox) and mouse drivers report lines or pages, not pixels */
    var px = e.deltaY * (e.deltaMode === 1 ? 40 : e.deltaMode === 2 ? row.clientWidth : 1);
    var max = row.scrollWidth - row.clientWidth, to = Math.max(0, Math.min(max, row.scrollLeft + px));
    if (to === row.scrollLeft) return;
    e.preventDefault(); row.scrollLeft = to;
  }, { passive: false });
  window.addEventListener('popstate', function () { render(); });
  /* Back on the Lucky Draw tab after looking elsewhere: fetch the draw's state now rather than at the next check */
  document.addEventListener('visibilitychange', function () { if (!document.hidden && parse().name === 'draw') refreshResults(true); });
  /* Old links (/#/verify-draw) and /index.html open at their clean URL */
  if (location.hash.indexOf('#/') === 0) history.replaceState(null, '', '/' + location.hash.slice(2));
  else if (location.pathname === '/index.html') history.replaceState(null, '', '/');
  /* Another tab (member app / Business Admin) changed shared data → refresh this one */
  window.addEventListener('storage', function (e) {
    if (e.key !== LS_KEY || !e.newValue) return;
    try { S = JSON.parse(e.newValue); } catch (x) { return; }
    var ae = document.activeElement;
    smsCheck();
    if (ae && /^(INPUT|TEXTAREA)$/.test(ae.tagName)) return;
    rerender();
  });

  /* ---------- PWA ---------- */
  var deferredPrompt = null;
  window.addEventListener('beforeinstallprompt', function (e) { e.preventDefault(); deferredPrompt = e; });
  if (/^https?:$/.test(location.protocol)) {
    var lk = document.createElement('link'); lk.rel = 'manifest'; lk.href = '/manifest.json'; document.head.appendChild(lk);
    if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(function () {});
  }

  /* Boot: the server decides who is signed in. 401 means signed out; a network error (offline) keeps the
     last known state so the cached app shell still opens. */
  Promise.all([
    BCAPI.get('/config').catch(function () { return {}; }),
    BCAPI.get('/me').catch(function (e) { return e.status === 401 ? null : undefined; })
  ]).then(function (r) {
    BOOT.googleClientId = (r[0] && r[0].googleClientId) || '';
    if (r[1]) { ME = r[1]; SES.authed = true; SES.pending = null; }
    else if (r[1] === null) { ME = null; SES.authed = false; SES.pending = null; }
    applyProfile(); saveSes();
    if (!SES.authed) { render(); return; }
    /* Signed in: load my orders before the first screen so cards and numbers are there straight away */
    Promise.all([refreshOrders(true), refreshResults(true)]).then(render, render);
  });
})();

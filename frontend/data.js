/* ============================================================
   Boche — data.js
   SINGLE SOURCE OF TRUTH for every data value in the app.
   UI files (index.html, app.js) hold structure and labels only.

   Model: Boche is the super app. Each business (Pub, Resort,
   Tea, Gold) is a child with its OWN application and database.
   The mobile number is the shared key. Points are per business;
   tier comes from total spend across the ecosystem.
   In production these objects become API responses with the same shape.
   ============================================================ */

var BC_BRAND = {
  name: 'Boche',
  group: 'Chemmannur International Gold & Diamonds',
  tagline: 'One membership. Every Boche experience.',
  intro: 'Sign in once with your mobile number. Earn rewards across the Boche family and unlock higher tiers as you spend.',
  otpLength: 4,
  demoOtp: '1234',
  demoEmailOtp: '1234',
  supportPhone: '1800 000 0000',
  supportEmail: 'care@boche.club'
};

var BC_ONBOARD = [
  { icon: 'card',  text: 'One digital card and QR for every Boche pub, resort and store' },
  { icon: 'gift',  text: 'Rewards from each business, added to your mobile number' },
  { icon: 'crown', text: 'Your tier grows with what you spend across the family' }
];

/* Legal drinking age per state — enforced via Aadhaar age verification */
var BC_STATES = {
  KL: { name: 'Kerala',    drinkingAge: 23 },
  KA: { name: 'Karnataka', drinkingAge: 21 }
};

/* Child businesses. live:false = shown as "coming soon".
   earn = points per ₹100 billed, by member tier (set by each business). */
var BC_BUSINESSES = [
  { id: 'pub', name: 'Boche Pub', short: 'Pub', label: 'Pub', icon: 'beer', live: true,
    blurb: 'Pubs across Kerala & Karnataka', appName: 'Pub Application',
    earn: { classic: 2, gold: 5, diamond: 8 },
    rupeeValue: 0.5, minRedeem: 500, expiryMonths: 12, expiring: { points: 600, date: '30 Nov 2026' },
    appMenu: [
      { icon: 'doc', title: 'Menu & ordering', sub: 'Browse food and drinks' },
      { icon: 'calendar', title: 'Reservations', sub: 'Your table bookings' },
      { icon: 'receipt', title: 'My bills', sub: 'Past bills at Boche pubs' }
    ] },
  { id: 'resort', name: 'Boche 1000 Acre', short: '1000 Acre', label: 'Resort', icon: 'mountain', live: true,
    blurb: 'Resort stays, restaurant & toddy shop', appName: 'Hospitality App',
    earn: { classic: 2, gold: 3, diamond: 5 },
    rupeeValue: 0.5, minRedeem: 1000, expiryMonths: 18, expiring: null,
    appMenu: [
      { icon: 'bed', title: 'Rooms & stays', sub: 'Book and manage your stay' },
      { icon: 'doc', title: 'Restaurant menu', sub: 'In-room and dine-in' },
      { icon: 'receipt', title: 'Folio & bills', sub: 'Charges from your stays' }
    ] },
  { id: 'tea', name: 'Boche Tea', short: 'Tea', label: 'Tea', icon: 'leaf', live: true, route: 'tea',
    blurb: 'Estate-fresh tea, delivered in Kerala', appName: 'Tea Retail App' },  /* no points: every pack carries Lucky Draw numbers instead */
  { id: 'gold', name: 'Boche Gold', short: 'Gold', label: 'Gold', icon: 'gem', live: false,
    blurb: 'Gold & diamond jewellery', appName: 'Gold Business App' }
];

/* Membership tiers — free; earned from total spend across ALL businesses (annual) */
var BC_TIERS = [
  { id: 'classic', name: 'Classic', minSpend: 0,
    perks: ['Free membership for every adult', 'Digital card and QR at every Boche venue', 'Birthday treat at participating businesses', 'Cross-business offers'] },
  { id: 'gold', name: 'Gold', minSpend: 50000,
    perks: ['Higher earn rate at every business', 'Priority table and room requests', 'Member-only events', 'Gold-tier offers'] },
  { id: 'diamond', name: 'Diamond', minSpend: 150000,
    perks: ['Best earn rate at every business', 'Reserved seating and early check-in', 'Private event invitations', 'Diamond-only offers'] }
];

/* Outlets — each belongs to a business. ageGate: alcohol is served, age checked at the door. */
var BC_OUTLETS = [
  { id: 'kochi', biz: 'pub', kind: 'Pub', name: 'Boche Pub Kochi', city: 'Kochi', area: 'MG Road, Ernakulam', state: 'KL',
    hours: '12 PM – 11 PM', phone: '+91 484 000 0101', distance: '2.4 km', rating: 4.6,
    tags: ['Live music Fri', 'Rooftop', 'Craft brews'], tone: 'a', ageGate: true, bookable: true, checkinLabel: 'Entry' },
  { id: 'tvm', biz: 'pub', kind: 'Pub', name: 'Boche Pub Thiruvananthapuram', city: 'Thiruvananthapuram', area: 'Kowdiar', state: 'KL',
    hours: '12 PM – 11 PM', phone: '+91 471 000 0102', distance: '218 km', rating: 4.5,
    tags: ['Quiz nights', 'Sports screening'], tone: 'b', ageGate: true, bookable: true, checkinLabel: 'Entry' },
  { id: 'kozhikode', biz: 'pub', kind: 'Pub', name: 'Boche Pub Kozhikode', city: 'Kozhikode', area: 'Beach Road', state: 'KL',
    hours: '12 PM – 11 PM', phone: '+91 495 000 0103', distance: '186 km', rating: 4.4,
    tags: ['Sea view', 'Malabar kitchen'], tone: 'c', ageGate: true, bookable: true, checkinLabel: 'Entry' },
  { id: 'blr', biz: 'pub', kind: 'Pub', name: 'Shakesbierre Brewpub & Club by Boche', city: 'Bengaluru', area: 'Eva Mall, Brigade Road', state: 'KA',
    hours: '12 PM – 12 AM', phone: '+91 96149 59959', distance: '548 km', rating: 4.7, logo: 'img/shakesbierre.png',
    tags: ['Brewpub', 'Karaoke lounge', 'Live music'], tone: 'd', ageGate: true, bookable: true, checkinLabel: 'Entry' },
  { id: 'mlr', biz: 'pub', kind: 'Pub', name: 'Boche Pub Mangaluru', city: 'Mangaluru', area: 'Lighthouse Hill Road', state: 'KA',
    hours: '12 PM – 11:30 PM', phone: '+91 824 000 0105', distance: '412 km', rating: 4.5,
    tags: ['Coastal grill', 'Open deck'], tone: 'e', ageGate: true, bookable: true, checkinLabel: 'Entry' },
  { id: 'resort', biz: 'resort', kind: 'Resort', name: '1000 Acre Resort', city: 'Idukki', area: 'Hill estate, Kerala', state: 'KL',
    hours: 'Check-in from 2 PM', phone: '+91 486 000 0201', distance: '96 km', rating: 4.8,
    tags: ['Rooms & villas', 'Estate walks', 'Pool'], tone: 'c', ageGate: false, bookable: false, checkinLabel: 'Room check-in' },
  { id: 'restaurant', biz: 'resort', kind: 'Restaurant', name: '1000 Acre Restaurant', city: 'Idukki', area: 'Main lodge', state: 'KL',
    hours: '7 AM – 10 PM', phone: '+91 486 000 0202', distance: '96 km', rating: 4.6,
    tags: ['Kerala cuisine', 'Estate-fresh'], tone: 'a', ageGate: false, bookable: true, checkinLabel: 'Table check-in' },
  { id: 'toddy', biz: 'resort', kind: 'Toddy shop', name: '1000 Acre Toddy Shop', city: 'Idukki', area: 'Estate gate', state: 'KL',
    hours: '11 AM – 9 PM', phone: '+91 486 000 0203', distance: '96 km', rating: 4.4,
    tags: ['Fresh toddy', 'Karimeen fry'], tone: 'b', ageGate: true, bookable: false, checkinLabel: 'Entry' }
];

/* Members. Static profile + per-business points and spend (the dynamic part is copied
   into local state at runtime). BC_MEMBERS[0] is the signed-in demo member;
   the others are for the staff demo. */
var BC_MEMBERS = [
  {
    id: 'BC-KL-240718', cardNo: '7181 2407 0526', name: 'Arun Mathew', firstName: 'Arun',
    mobile: '98470 12345', email: 'arun.mathew@example.com', dob: '1991-03-14', city: 'Kochi',
    homeOutlet: 'kochi', memberSince: 'Jul 2024', validThru: '07/27',
    kyc: { aadhaarMasked: 'XXXX XXXX 4417', method: 'DigiLocker · Aadhaar offline e-KYC', verifiedOn: '18 Jul 2024' },
    points: { pub: 4820, resort: 1350, tea: 0, gold: 0 },
    spend:  { pub: 41200, resort: 21200, tea: 0, gold: 0 },
    vouchers: [ { biz: 'pub', title: 'Starter platter', code: 'BC-K7Q2MX', date: '12 Oct 2026', used: false } ],
    checkins: [
      { outlet: 'kochi', date: '17 Oct 2026', time: '8:12 PM' },
      { outlet: 'blr',   date: '04 Oct 2026', time: '9:40 PM' },
      { outlet: 'resort', date: '20 Sep 2026', time: '3:05 PM' }
    ],
    history: [
      { biz: 'pub',    date: '17 Oct 2026', title: 'Bill · Boche Pub Kochi',       ref: 'KCH-87102', pts: 186 },
      { biz: 'pub',    date: '12 Oct 2026', title: 'Redeemed · Starter platter',    ref: 'VCH-2231',  pts: -900 },
      { biz: 'pub',    date: '05 Oct 2026', title: 'Pub Trail bonus · 3 pubs',      ref: 'PROMO-O1',  pts: 1500 },
      { biz: 'pub',    date: '04 Oct 2026', title: 'Bill · Shakesbierre Bengaluru',    ref: 'BLR-40918', pts: 240 },
      { biz: 'resort', date: '22 Sep 2026', title: 'Stay · 1000 Acre Resort',       ref: 'FOL-30871', pts: 850 },
      { biz: 'resort', date: '20 Sep 2026', title: 'Dining · 1000 Acre Restaurant', ref: 'RST-11902', pts: 500 },
      { biz: 'pub',    date: '28 Sep 2026', title: 'Bill · Boche Pub Mangaluru',    ref: 'MLR-11873', pts: 155 }
    ]
  },
  {
    id: 'BC-KL-261002', cardNo: '7181 2610 0231', name: 'Meera Nair', firstName: 'Meera',
    mobile: '97450 98765', email: 'meera.nair@example.com', dob: '2004-02-09', city: 'Kozhikode',
    homeOutlet: 'blr', memberSince: 'Oct 2026', validThru: '10/29',
    kyc: { aadhaarMasked: 'XXXX XXXX 9021', method: 'DigiLocker · Aadhaar offline e-KYC', verifiedOn: '02 Oct 2026' },
    points: { pub: 120, resort: 0, tea: 0, gold: 0 }, spend: { pub: 6000, resort: 0, tea: 0, gold: 0 },
    vouchers: [], checkins: [], history: []
  },
  {
    id: 'BC-KA-261015', name: 'Sam Joseph', firstName: 'Sam', cardNo: '7181 2610 0488',
    mobile: '90360 55512', email: 'sam.joseph@example.com', dob: '2007-06-21', city: 'Bengaluru',
    homeOutlet: 'blr', memberSince: 'Oct 2026', validThru: '10/29',
    kyc: { aadhaarMasked: 'XXXX XXXX 7733', method: 'DigiLocker · Aadhaar offline e-KYC', verifiedOn: '15 Oct 2026' },
    points: { pub: 0, resort: 0, tea: 0, gold: 0 }, spend: { pub: 0, resort: 0, tea: 0, gold: 0 },
    vouchers: [], checkins: [], history: []
  }
];
var BC_MEMBER = BC_MEMBERS[0];

/* Business staff (Business Admin module) — sign in with mobile OTP */
var BC_STAFF = [
  { id: 'st1', mobile: '9895011111', name: 'Suresh K', role: 'Duty manager', biz: 'pub',
    outlets: ['kochi', 'tvm', 'kozhikode', 'blr', 'mlr'] },
  { id: 'st2', mobile: '9895022222', name: 'Anita Menon', role: 'Front office', biz: 'resort',
    outlets: ['resort', 'restaurant', 'toddy'] }
];

/* Rewards — offered and honoured by each business */
var BC_REWARDS = [
  { id: 'r1', biz: 'pub', title: '₹250 off your bill',            pts: 500,  cat: 'Bill credit', icon: 'receipt' },
  { id: 'r2', biz: 'pub', title: 'Mocktail pitcher',              pts: 700,  cat: 'Beverages',   icon: 'gift' },
  { id: 'r3', biz: 'pub', title: 'Starter platter',               pts: 900,  cat: 'Food',        icon: 'gift' },
  { id: 'r4', biz: 'pub', title: 'Priority table for 6, Friday',  pts: 1200, cat: 'Experience',  icon: 'users' },
  { id: 'r5', biz: 'pub', title: 'Live night event pass',         pts: 1500, cat: 'Events',      icon: 'music' },
  { id: 'r6', biz: 'pub', title: '₹1,500 off your bill',          pts: 3000, cat: 'Bill credit', icon: 'receipt' },
  { id: 'r7', biz: 'pub', title: 'Private lounge for 10 (2 hrs)', pts: 8000, cat: 'Experience',  icon: 'crown' },
  { id: 'q1', biz: 'resort', title: 'Welcome drink for two',        pts: 1000, cat: 'Beverages',  icon: 'gift' },
  { id: 'q2', biz: 'resort', title: '₹500 off restaurant bill',     pts: 1000, cat: 'Bill credit', icon: 'receipt' },
  { id: 'q3', biz: 'resort', title: 'Estate walk with guide',       pts: 1500, cat: 'Experience', icon: 'leaf' },
  { id: 'q4', biz: 'resort', title: 'Late check-out (till 4 PM)',   pts: 2500, cat: 'Stay',       icon: 'clock' },
  { id: 'q5', biz: 'resort', title: 'One night room upgrade',       pts: 6000, cat: 'Stay',       icon: 'bed' }
];

/* Offers — each belongs to a business; cross-business offers drive discovery */
var BC_OFFERS = [
  { id: 'o1', biz: 'pub', kind: 'Cross-pub', title: 'Pub Trail', desc: 'Visit any 3 different Boche pubs this month and earn 1,500 bonus pub points.',
    outlets: 'all', valid: 'Till 31 Dec 2026', tiers: ['classic', 'gold', 'diamond'] },
  { id: 'o2', biz: 'pub', kind: 'Happy hours', title: 'Monday happy hours', desc: 'All-day happy hours every Monday at Shakesbierre, Brigade Road. Craft beers and cocktails. Confirm at the venue.',
    outlets: ['blr'], valid: 'Every Monday', tiers: ['classic', 'gold', 'diamond'] },
  { id: 'o8', biz: 'pub', kind: 'Craft beer', title: 'Craft beer 2 + 1', desc: 'Ask at the bar about the 2 + 1 craft beer offer at Shakesbierre. Show your Boche card.',
    outlets: ['blr'], valid: 'Ask at the bar', tiers: ['classic', 'gold', 'diamond'] },
  { id: 'o3', biz: 'pub', kind: 'Members only', title: 'Free starter over ₹2,500', desc: 'A complimentary starter on food bills above ₹2,500.',
    outlets: ['kozhikode', 'tvm'], valid: 'Mon – Thu', tiers: ['gold', 'diamond'] },
  { id: 'o4', biz: 'pub', kind: 'Refer', title: 'Bring a friend', desc: 'Earn 500 points when a friend joins and makes their first visit.',
    outlets: 'all', valid: 'Always on', tiers: ['classic', 'gold', 'diamond'] },
  { id: 'o5', biz: 'resort', kind: 'Stay & earn', title: 'Weekend stay bonus', desc: 'Stay two nights at 1000 Acre and earn 1,000 bonus resort points.',
    outlets: ['resort'], valid: 'Fri – Sun', tiers: ['classic', 'gold', 'diamond'] },
  { id: 'o6', biz: 'resort', kind: 'Tasting', title: 'Toddy & karimeen tasting', desc: 'A complimentary tasting platter for two for Gold and Diamond members.',
    outlets: ['toddy'], valid: 'Daily, 4 – 7 PM', tiers: ['gold', 'diamond'] },
  { id: 'o7', biz: 'resort', kind: 'Pub to resort', title: 'Pub regulars stay for less', desc: 'Show a Boche Pub bill from the last 30 days and get 10% off your room.',
    outlets: ['resort'], valid: 'Till 31 Dec 2026', tiers: ['classic', 'gold', 'diamond'] }
];

var BC_EVENTS = [
  { id: 'e1', date: '2026-11-06', title: 'Friday Live: Indie Night', outlet: 'kochi', time: '8:00 PM', price: 'Free for members', seats: 18 },
  { id: 'e2', date: '2026-11-14', title: 'Saturday Social', outlet: 'blr', time: '9:00 PM', price: '₹499 · free for Gold & Diamond', seats: 40 },
  { id: 'e3', date: '2026-11-07', title: 'Quiz Night', outlet: 'tvm', time: '7:30 PM', price: 'Free for members', seats: 12 },
  { id: 'e4', date: '2026-11-08', title: 'Estate Brunch', outlet: 'restaurant', time: '11:00 AM', price: '₹799 for members', seats: 24 },
  { id: 'e5', date: '2026-11-14', title: 'Coastal Food Fest', outlet: 'mlr', time: '7:00 PM', price: '₹299 for members', seats: 30 }
];

var BC_BOOKING = {
  times: ['7:00 PM', '7:30 PM', '8:00 PM', '8:30 PM', '9:00 PM', '9:30 PM'],
  occasions: ['Casual', 'Birthday', 'Anniversary', 'Business', 'Celebration'],
  maxGuests: 12
};

/* Age check: Aadhaar number (Verhoeff-validated) + OTP from UIDAI to the Aadhaar-linked mobile.
   Only the last 4 digits and a verified-age flag are stored. Demo values work in the prototype. */
var BC_KYC = {
  otpLength: 4,
  demoAadhaar: '2345 6789 0124',
  demoOtp: '1234',
  steps: ['Verifying OTP with UIDAI', 'Reading your date of birth', 'Saving your verified-age flag'],
  consent: 'I agree to Boche verifying my age with Aadhaar OTP. Only the last 4 digits and a verified-age flag are kept.'
};

/* Account security: SIM must match the mobile number; a new phone also needs an email code */
var BC_SECURITY = { emailOtpLength: 4 };

/* Single sign-on hand-off steps shown before a child app opens */
var BC_SSO_STEPS = ['Verifying your Boche session', 'Sharing your mobile number securely', 'Signing you in to {app}'];

/* Staff scanner */
var BC_STAFF_UI = {
  scanHint: 'Point at the member’s Boche QR',
  minBill: 100,
  otpValidMinutes: 5
};

/* Rotating promo banner on Home */
/* Home carousel. biz = which business it promotes (theme + icon); 'club' = Boche itself.
   go = route for live businesses; coming-soon businesses show a teaser. */
var BC_PROMO_CFG = { rotateMs: 5000 };
var BC_PROMOS = [
  { biz: 'club',   title: 'Win ₹1 lakh every day', art: 'draw', text: 'Every Tea order gets a scratch card for the daily 9 PM Lucky Draw.', cta: 'Lucky Draw', go: 'draw', icon: 'gift' },
  { biz: 'pub',    title: 'Pub Trail', art: 'pub', logo: 'img/shakesbierre.png',            text: 'Visit 3 Boche pubs this month and earn 1,500 bonus points.', cta: 'Explore pubs', go: 'biz/pub' },
  { biz: 'resort', title: 'Weekend at 1000 Acre', art: 'resort', text: 'Stay two nights and earn 1,000 bonus points.',                cta: 'View resort',  go: 'biz/resort' },
  { biz: 'club',   title: 'Bring a friend', art: 'friend',       text: 'Earn 500 points when a friend joins and makes a first visit.', cta: 'See offers',   go: 'offers' },
  { biz: 'tea',    title: 'Estate tea, home delivered', art: 'tea', text: 'Every pack comes with Lucky Draw numbers. Delivered anywhere in Kerala.', cta: 'Shop tea', go: 'tea' },
  { biz: 'gold',   title: 'Boche Gold', art: 'gold',           text: 'Jewellery purchases will earn points and lift your tier.',     cta: 'Coming soon' }
];

/* Boche Tea online shop. Prices in ₹ before GST; GST (taxRate on tea, logisticsTaxRate on logistics) is added only at checkout. Delivery only to Kerala pincodes.
   Logistics = each pack's own delivery charge × qty. */
var BC_TEA = {
  product: { name: 'Boche Estate Tea', tagline: 'Strong, malty CTC for a rich chai', desc: 'Strong, malty CTC from the Western Ghats. Brews a rich chai.' },
  /* Bigger packs cost less per kg (₹360 → ₹340 → ₹320).
     numbers = Lucky Draw numbers on the one scratch card each pack comes with
     logistics = delivery charge per pack, before GST */
  packs: [
    { id: 'p250', size: '250 g', grams: 250,  price: 90,  numbers: 1, logistics: 36 },
    { id: 'p500', size: '500 g', grams: 500,  price: 170, numbers: 3, logistics: 36 },
    { id: 'p1k',  size: '1 kg',  grams: 1000, price: 320, numbers: 8, logistics: 52 }
  ],
  maxQty: 10,
  taxRate: 5,            /* tea (HSN 0902) is 5% GST */
  logisticsTaxRate: 18,  /* delivery / logistics is 18% GST */
  eta: '3–5 days',
  pincodeApi: 'https://api.postalpincode.in/pincode/',
  /* Offline fallback: Kerala pincode prefix → district (used if the India Post lookup is unreachable) */
  districts: { '670': 'Kannur', '671': 'Kasaragod', '673': 'Kozhikode', '676': 'Malappuram', '678': 'Palakkad', '679': 'Palakkad',
    '680': 'Thrissur', '682': 'Ernakulam', '683': 'Ernakulam', '685': 'Idukki', '686': 'Kottayam', '688': 'Alappuzha',
    '689': 'Pathanamthitta', '690': 'Kollam', '691': 'Kollam', '692': 'Thiruvananthapuram', '693': 'Thiruvananthapuram', '694': 'Thiruvananthapuram', '695': 'Thiruvananthapuram' }
};

/* Daily Lucky Draw. Every paid Tea order gives one scratch card with a unique lucky number
   (format "XY 123456", unique per day). Entries submitted before drawHour go into that day's
   draw, later ones into the next day's. In production the server issues numbers and runs the draw. */
var BC_DRAW = {
  name: 'Lucky Draw',
  drawHour: 21,
  prizes: [
    { rank: '1st prize', amount: 100000, count: 1 },
    { rank: '2nd prize', amount: 50000,  count: 1 },
    { rank: '3rd prize', amount: 25000,  count: 1 },
    { rank: 'Lucky 7',   amount: 10000,  count: 7 }
  ],
  letters: 'ABCDEFGHJKLMNPRSTUVWXYZ',
  /* Prototype only: size of the simulated entry pool and names for simulated winners */
  demoPool: 3200,
  demoWins: 2,   /* prototype: the member's first 2 drawn days each give one of their numbers a Lucky 7 win */
  demoNames: ['Anu S.', 'Bijoy K.', 'Deepa R.', 'Faisal M.', 'Gopika N.', 'Hari P.', 'Jincy T.', 'Kiran V.', 'Lakshmi A.', 'Manu J.',
    'Nisha G.', 'Rahul C.', 'Reshma B.', 'Sajan P.', 'Shibu K.', 'Sneha M.', 'Thomas V.', 'Vineeth R.', 'Ashraf K.', 'Divya S.',
    'Jose A.', 'Nikhil T.', 'Priya L.', 'Sreejith N.', 'Tessa J.', 'Vishnu P.', 'Ann M.', 'Biju R.', 'Fathima S.', 'Arjun D.']
};

/* Customer support & grievances. Acknowledge within 48 hours and resolve within a month,
   in line with the Consumer Protection (E-Commerce) Rules, 2020. */
var BC_SUPPORT = {
  hours: 'Support is open 9 AM – 9 PM, every day',
  minChars: 20, maxChars: 1000,
  maxFiles: 3, maxMb: 5,
  ackHours: 48, resolveDays: 30
};

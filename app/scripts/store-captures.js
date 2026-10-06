// The stores' images (docs/store/captures): the browser tests' site driven as two phones, 440x956 at 3x (an
// instigateur composes an evening for tomorrow and keeps it, a passager joins it), then each screen captioned in the
// app's night, emerald and gold: the App Store's 6.9" size (1320x2868), Google Play's phone size (1080x1920), Play's
// icon and feature graphic, and an example of the evening's postcard as shared. The App Store's icon is the app's own
// (assets/images/logo-secretdate.png).
//
// Only the app's own pictures: the sites' photos, and the server's copies of them, are not ours to publish. With the
// local Supabase running (npm run db:start) and the site built (npm run build:e2e):
//   uv run python tests/e2e_server.py --port 8011     (from the repo's root)
//   node scripts/store-captures.js                     (from app/)
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require('@playwright/test');

const BASE = process.env.CAPTURES_URL ?? 'http://127.0.0.1:8011';
const OUT = path.resolve(__dirname, '../../docs/store/captures');
const RAW = fs.mkdtempSync(path.join(os.tmpdir(), 'secretdate-captures-'));
const FONTS = path.resolve(__dirname, '../node_modules/@expo-google-fonts');
const LOGO = path.resolve(__dirname, '../assets/images/logo-secretdate.png');

// Each image: its file, the screen behind it, its caption; Google Play takes eight (`play`).
const SHOTS = [
  ['01-accueil', 'accueil', 'Une soirée surprise à Paris', 'Composée pour vous deux, gardée secrète jusqu’au bout.'],
  ['02-envies', 'envies', 'Une humeur, deux envies', 'Et l’intrigue se trame en quelques secondes.'],
  ['03-intrigues', 'intrigues', 'Trois intrigues au choix', 'Changez une étape, gardez celle qui vous ressemble.'],
  ['04-feuille-de-route', 'feuille', 'Une feuille de route à la minute', 'Chaque étape, son heure et son trajet.'],
  ['05-passager', 'passager', 'Votre complice ne sait rien', 'Juste un jour, une heure… et des indices.'],
  ['06-indices', 'indices', 'Un indice chaque matin', 'La tenue, le budget, un mot mystère par étape.'],
  ['07-semaine', 'semaine', 'Une semaine en chapitres', 'Chaque notification fait monter le mystère.'],
  ['08-coulisses', 'coulisses', 'Vous tirez les ficelles', 'Les réservations, et ce que voit votre passager.'],
  ['09-carte-postale', 'carte', 'Une carte pour vos stories', 'Le nom de la soirée, ses mots mystères, rien de plus.'],
  ['10-carton', 'carton', 'Un carton à glisser sous l’oreiller', 'Un code à scanner, et le mystère commence.'],
];
const NOT_ON_PLAY = new Set(['02-envies', '08-coulisses']);

const PASSWORD = `captures-${Math.random().toString(36).slice(2)}`;
const email = (label) => `${label}-${Date.now()}@captures.test`;
const tomorrow = () => {
  const d = new Date(Date.now() + 86_400_000);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

async function phone(browser) {
  const context = await browser.newContext({
    viewport: { width: 440, height: 956 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true,
    locale: 'fr-FR', timezoneId: 'Europe/Paris', colorScheme: 'dark', baseURL: BASE,
  });
  await context.route('**/*', (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const ours = url.origin === new URL(BASE).origin && !url.pathname.startsWith('/images/');
    return request.resourceType() === 'image' && !ours ? route.abort() : route.continue();
  });
  return context;
}

async function account(page, label, button) {
  await page.getByText('Créer un compte', { exact: true }).click();
  await page.getByLabel('Email').fill(email(label));
  await page.getByLabel('Mot de passe').fill(PASSWORD);
  await page.getByText(button, { exact: true }).click();
}

const settle = (page, ms = 2500) => page.waitForTimeout(ms);
const shoot = (page, name) => page.screenshot({ path: path.join(RAW, `${name}.png`) });

async function screens(browser) {
  const page = await (await phone(browser)).newPage();
  await page.goto('/');
  await account(page, 'instigateur', 'Créer notre compte');
  await page.getByText('Lancer une nouvelle intrigue').click();
  await page.getByText('Rire aux éclats').waitFor();
  await settle(page);
  await shoot(page, 'envies');
  await page.getByText('Rire aux éclats').click();
  await page.getByText('Oui, on dîne').click();
  await page.locator('input[type=date]').fill(tomorrow());
  const composing = page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/soirees');
  await page.getByText('Tramer nos intrigues').click();
  const composed = await (await composing).json();
  await page.getByText('Trois intrigues se murmurent au salon').waitFor();
  await settle(page, 4000);
  await page.mouse.wheel(0, -5000);
  await settle(page);
  await shoot(page, 'intrigues');

  await page.getByText('Garder cette intrigue').first().click();
  await page.waitForURL(/\/revelation\?soiree=/);
  await settle(page, 4000);
  await shoot(page, 'feuille');
  const link = await page.getByText(/\/invitation\?code=[0-9a-f]{12}$/).textContent();
  await page.mouse.wheel(0, -5000);
  await page.getByText('Les Coulisses', { exact: true }).click();
  await settle(page);
  await shoot(page, 'coulisses');
  await page.getByTestId('semaine-passager').evaluate((el) => el.scrollIntoView({ block: 'start' }));
  await page.mouse.wheel(0, -50);
  await settle(page);
  await shoot(page, 'semaine');
  await page.getByText("Ou un carton d'invitation à imprimer…").click();
  await page.getByTestId('carton-invitation').evaluate((el) => el.scrollIntoView({ block: 'start' }));
  await page.mouse.wheel(0, -30);
  await settle(page);
  await shoot(page, 'carton');
  await page.getByTestId('carte-postale').evaluate((el) => el.scrollIntoView({ block: 'end' }));
  await page.mouse.wheel(0, 120);
  await settle(page);
  await shoot(page, 'carte');
  // The postcard itself, as it is shared: an example beside the stores' images.
  const downloading = page.waitForEvent('download');
  await page.getByText('Télécharger la carte').click();
  await (await downloading).saveAs(path.join(OUT, 'exemple-carte-postale.png'));

  const passager = await (await phone(browser)).newPage();
  await passager.goto(new URL(link).pathname + new URL(link).search);
  await account(passager, 'passager', 'Créer mon compte passager');
  await passager.getByText('Votre soirée secrète').waitFor();
  await settle(passager, 4000);
  await shoot(passager, 'passager');
  await passager.goto(`/revelation?soiree=${composed.name}`);
  await passager.getByText('Vos indices').waitFor();
  await settle(passager, 4000);
  await shoot(passager, 'indices');

  await page.goto('/');
  await settle(page, 4000);
  await shoot(page, 'accueil');
}

const font = (family, file) => `@font-face { font-family: '${family}'; src: url('${pathToFileURL(path.join(FONTS, file)).href}'); }`;
const sheet = (w, h, body, css = '') => `<!doctype html><html><head><meta charset="utf-8"><style>
${font('Cormorant', 'cormorant-garamond/500Medium_Italic/CormorantGaramond_500Medium_Italic.ttf')}
${font('CormorantUp', 'cormorant-garamond/600SemiBold/CormorantGaramond_600SemiBold.ttf')}
${font('Manrope', 'manrope/400Regular/Manrope_400Regular.ttf')}
html, body { margin: 0; width: ${w}px; height: ${h}px; overflow: hidden; }
body {
  background: radial-gradient(120% 60% at 50% 0%, #0E3324 0%, #071A12 45%, #040F0A 100%);
  color: #E9E5D8; font-family: Manrope; display: flex; flex-direction: column; align-items: center;
}
${css}
</style></head><body>${body}</body></html>`;

// A screen under its caption, on the App Store's layout scaled to the size.
function captioned(w, h, raw, title, sub) {
  const s = w / 1320;
  const width = h / w > 2 ? 1080 : 700;
  return sheet(w, h, `
    <div class="cap"><div class="title">${title}</div><div class="sub">${sub}</div></div>
    <div class="phone"><img src="${pathToFileURL(raw).href}"></div>`, `
    .cap { text-align: center; padding: ${Math.round(150 * s)}px ${Math.round(90 * s)}px 0; }
    .title { font-family: Cormorant; font-size: ${Math.round(104 * s)}px; line-height: 1.08; }
    .sub { margin-top: ${Math.round(26 * s)}px; font-size: ${Math.round(42 * s)}px; line-height: 1.35; color: #DBC18C; }
    .phone {
      margin-top: ${Math.round(70 * s)}px; width: ${width}px; border-radius: ${Math.round(72 * s)}px; overflow: hidden;
      border: ${Math.max(2, Math.round(4 * s))}px solid rgba(219, 193, 140, 0.38);
      box-shadow: 0 0 ${Math.round(120 * s)}px rgba(61, 183, 135, 0.28), 0 ${Math.round(40 * s)}px ${Math.round(90 * s)}px rgba(0, 0, 0, 0.6);
    }
    .phone img { display: block; width: 100%; }`);
}

const featureGraphic = () => sheet(1024, 500, `
  <div class="row"><img src="${pathToFileURL(LOGO).href}"><div><div class="name">Secret Date</div>
  <div class="tag">Des soirées surprises à deux, à Paris.<br>L’un compose, l’autre n’a que des indices.</div></div></div>`, `
  body { justify-content: center; }
  .row { display: flex; align-items: center; gap: 56px; height: 500px; padding: 0 70px; }
  .row img { width: 270px; height: 270px; border-radius: 48px; border: 3px solid rgba(219, 193, 140, 0.45); box-shadow: 0 0 80px rgba(61, 183, 135, 0.3); }
  .name { font-family: CormorantUp; font-size: 92px; color: #DBC18C; line-height: 1; }
  .tag { margin-top: 22px; font-size: 27px; line-height: 1.45; }`);

async function render(browser, html, w, h, file) {
  const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
  const tmp = path.join(RAW, '_sheet.html');
  fs.writeFileSync(tmp, html);
  await page.goto(pathToFileURL(tmp).href);
  await page.evaluate(() => document.fonts.ready);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const jpeg = file.endsWith('.jpg');
  await page.screenshot({ path: file, type: jpeg ? 'jpeg' : 'png', ...(jpeg ? { quality: 90 } : {}) });
  await page.close();
  console.log(path.relative(process.cwd(), file));
}

(async () => {
  const browser = await chromium.launch();
  try {
    await screens(browser);
    for (const [name, screen, title, sub] of SHOTS) {
      const raw = path.join(RAW, `${screen}.png`);
      await render(browser, captioned(1320, 2868, raw, title, sub), 1320, 2868, path.join(OUT, 'app-store', `${name}.jpg`));
      if (!NOT_ON_PLAY.has(name)) await render(browser, captioned(1080, 1920, raw, title, sub), 1080, 1920, path.join(OUT, 'google-play', `${name}.jpg`));
    }
    await render(browser, featureGraphic(), 1024, 500, path.join(OUT, 'google-play', 'feature-graphic-1024x500.png'));
    await render(browser, sheet(512, 512, `<img src="${pathToFileURL(LOGO).href}" width="512" height="512">`), 512, 512, path.join(OUT, 'google-play', 'icone-512.png'));
  } finally {
    await browser.close();
    fs.rmSync(RAW, { recursive: true, force: true });
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});

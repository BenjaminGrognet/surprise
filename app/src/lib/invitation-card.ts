// The printed invitation: a card the instigateur slips under a pillow or into a book. The evening's secret name, its
// day and hour, nothing else, and a QR code to the invitation link that opens the passager's clues. As a page to print
// (A6, landscape), and its QR code as SVG for the screen.
import QRCode from 'qrcode';

const QUIET = 4; // the blank margin a reader needs around the code, in modules

// The QR code of a link, as an SVG: one square per dark module, on white.
export function qrSvg(text: string, size = 200, ink = '#06281B') {
  const { modules } = QRCode.create(text, { errorCorrectionLevel: 'M' });
  const n = modules.size;
  let path = '';
  for (let y = 0; y < n; y++) {
    for (let x = 0; x < n; x++) if (modules.get(y, x)) path += `M${x + QUIET} ${y + QUIET}h1v1h-1z`;
  }
  const box = n + 2 * QUIET;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${box} ${box}" width="${size}" height="${size}" shape-rendering="crispEdges" role="img" aria-label="QR code de l'invitation"><rect width="${box}" height="${box}" fill="#ffffff"/><path d="${path}" fill="${ink}"/></svg>`;
}

const escape = (text: string) =>
  text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

// `brand`: the formula's name on the card, Secret Date unless a band's (Secret Squad).
export type Invitation = { secretTitle: string; when: string; link: string; brand?: string };

// The card as a page to print: ivory paper, gold rules, the name in italics, the code on the right. Its fonts come
// from Google Fonts; without them, a serif.
export function invitationHtml({ secretTitle, when, link, brand = 'Secret Date' }: Invitation) {
  return `<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>${escape(secretTitle)} · ${escape(brand)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,600;1,500&family=Manrope:wght@400;600&display=swap" rel="stylesheet">
<style>
  @page { size: A6 landscape; margin: 0; }
  * { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  html, body { margin: 0; background: #ffffff; }
  .card {
    width: 148mm; height: 105mm; padding: 9mm; background: #FBF8F0; color: #06281B;
    display: flex; gap: 7mm; align-items: center; position: relative; font-family: Manrope, Helvetica, sans-serif;
  }
  .card::before { content: ''; position: absolute; inset: 4mm; border: 0.4mm solid #B8975A; border-radius: 3mm; }
  .card::after { content: ''; position: absolute; inset: 5.2mm; border: 0.15mm solid #B8975A; border-radius: 2.4mm; }
  .text { flex: 1; display: flex; flex-direction: column; gap: 3.2mm; position: relative; z-index: 1; }
  .brand { font-family: 'Cormorant Garamond', Georgia, serif; font-weight: 600; letter-spacing: 0.35em; font-size: 9pt; color: #9A7B3F; }
  .kicker { font-size: 7.5pt; letter-spacing: 0.25em; text-transform: uppercase; color: #5E6E62; }
  h1 { margin: 0; font-family: 'Cormorant Garamond', Georgia, serif; font-style: italic; font-weight: 500; font-size: 23pt; line-height: 1.05; }
  .when { font-weight: 600; font-size: 10pt; color: #9A7B3F; }
  .hush { font-family: 'Cormorant Garamond', Georgia, serif; font-style: italic; font-size: 12pt; line-height: 1.25; }
  .code { width: 40mm; display: flex; flex-direction: column; align-items: center; gap: 2mm; position: relative; z-index: 1; }
  .code svg { width: 36mm; height: 36mm; }
  .scan { font-size: 7pt; text-align: center; line-height: 1.35; color: #5E6E62; }
  .link { font-size: 5.5pt; text-align: center; word-break: break-all; color: #5E6E62; }
</style></head>
<body><div class="card">
  <div class="text">
    <div class="brand">${escape(brand.toUpperCase())}</div>
    <div class="kicker">Vous êtes invité(e)</div>
    <h1>${escape(secretTitle)}</h1>
    <div class="when">${escape(when)}</div>
    <div class="hush">Gardez votre soirée.<br>Tout le reste est un secret.</div>
  </div>
  <div class="code">
    ${qrSvg(link)}
    <div class="scan">Scannez pour recevoir<br>vos indices</div>
    <div class="link">${escape(link)}</div>
  </div>
</div></body></html>`;
}

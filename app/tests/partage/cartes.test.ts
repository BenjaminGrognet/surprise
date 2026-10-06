// What leaves the app on paper or in a story: the evening's postcard (lib/postcard.ts), never more than the passager
// may know, and the printed invitation with its QR code (lib/invitation-card.ts).
import { describe, expect, test } from '@jest/globals';
import QRCode from 'qrcode';

import { stepWords } from '@/lib/clues';
import { formatTime } from '@/lib/dates';
import { invitationHtml, qrSvg } from '@/lib/invitation-card';
import { postcard, postcardFile } from '@/lib/postcard';

import { evening, local, SECRET } from '../notifications/fixtures';

const DAY = '2026-10-16';
const route = evening(DAY);
const words = stepWords(route, 'etapes');
const when = `Vendredi 16 octobre · ${formatTime(route.start)}`;

describe('the postcard', () => {
  test('before the evening: its name, day and hour, the words shown so far, the others veiled, no step', () => {
    const card = postcard(route, 'etapes', SECRET, local(DAY, 12, 0, -5));
    expect(card).toEqual({
      title: SECRET, when, words: [words[0].word, '?', '?'], steps: [],
      line: 'Une soirée secrète nous attend : le reste est un mystère.',
    });
    expect(postcard(route, 'etapes', SECRET, local(DAY, 16, 0, -1)).words).toEqual([words[0].word, words[1].word, words[2].word]);
  });

  test('the evening begun, still no step; over, every word and every step it went through', () => {
    expect(postcard(route, 'etapes', SECRET, local(DAY, 20)).steps).toEqual([]);
    expect(postcard(route, 'etapes', SECRET, local(DAY, 20)).line).toBe('Ce soir, une intrigue se joue pour nous deux.');
    const after = postcard(route, 'etapes', SECRET, local(DAY, 11, 0, 1));
    expect(after.words).toEqual(words.map((w) => w.word));
    expect(after.steps).toEqual(route.steps.map((s) => s.title));
    expect(after.line).toBe('Une soirée vécue à deux, en secret.');
  });

  test('its image is named after the secret name', () => {
    expect(postcardFile("Le Pacte de l'Île Saint-Louis")).toBe('secret-date-le-pacte-de-l-ile-saint-louis');
  });
});

describe('the printed invitation', () => {
  const link = 'https://secretdate.fr/invitation?code=0123456789ab';

  test('its QR code is the link: every dark module drawn, the three finders in their corners, a quiet margin', () => {
    const { modules } = QRCode.create(link, { errorCorrectionLevel: 'M' });
    const n = modules.size;
    const svg = qrSvg(link, 200);
    expect(svg).toContain(`viewBox="0 0 ${n + 8} ${n + 8}"`);
    expect(svg.match(/h1v1h-1z/g)).toHaveLength([...modules.data].filter(Boolean).length);
    for (const [x, y] of [[4, 4], [4 + n - 1, 4], [4, 4 + n - 1]]) expect(svg).toContain(`M${x} ${y}h1v1h-1z`);
    expect(svg).not.toMatch(/M[0-3] /);
  });

  test('the card: the secret name, day and hour, the code and the link, nothing else of the evening', () => {
    const html = invitationHtml({ secretTitle: SECRET, when, link });
    expect(html).toContain(`<h1>${SECRET}</h1>`);
    expect(html).toContain(when);
    expect(html).toContain(qrSvg(link));
    expect(html).toContain(`<div class="link">${link}</div>`);
    expect(html).toContain('@page { size: A6 landscape; margin: 0; }');
    for (const step of route.steps) expect(html).not.toContain(step.title);
  });

  test('a name with quotes or brackets stays text', () => {
    const html = invitationHtml({ secretTitle: 'Le "Pacte" <rouge> & or', when, link });
    expect(html).toContain('<h1>Le &quot;Pacte&quot; &lt;rouge&gt; &amp; or</h1>');
  });
});

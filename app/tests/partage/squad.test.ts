// A band's evening (Secret Squad) told in its own voice: its clues, mystery words, prices, notifications, widget,
// postcard and printed card say "la bande" where a couple's say "votre passager" — the same evening otherwise.
import { describe, expect, test } from '@jest/globals';

import { formatPrice, routePrice } from '@/lib/prices';
import type { SoireeRoute } from '@/lib/api';
import { cluesFor, stepWords } from '@/lib/clues';
import { complicity } from '@/lib/complicity';
import { invitationHtml } from '@/lib/invitation-card';
import { postcard } from '@/lib/postcard';
import { instigateurWeek, passagerWeek } from '@/lib/story';
import { widgetCard } from '@/lib/widget';
import type { EveningHistoryRow } from '@/lib/account';

import { evening, local, SECRET } from '../notifications/fixtures';

const DAY = '2026-10-16';
// The same Friday for six friends: every price counts the six of them.
const couple = evening(DAY);
const band: SoireeRoute = {
  ...couple, formule: 'squad', personnes: 6, price: 270,
  steps: couple.steps.map((s) => ({ ...s, price: s.price * 3 })),
};
const base = { route: band, mode: 'etapes' as const, secretTitle: SECRET, pageName: 'soiree-bande' };

describe('a band’s clues and words', () => {
  test('its budget is each one’s share, its words a band’s', () => {
    // 270 € for six: 45 € each, as a couple's 90 € is 45 € each.
    const budget = (route: SoireeRoute) => cluesFor(route).find((c) => c.kind === 'budget')!.text;
    expect(budget(band)).toBe(budget(couple));
    expect(budget({ ...band, price: 120 })).toBe('Une soirée douce pour le portefeuille de chacun.');
    const words = stepWords(band).map((w) => w.word);
    expect(['Festin', 'Tournée', 'Gourmandise', 'Tablée', 'Banquet']).toContain(words[0]);
    expect(['Fous rires', 'Délire', 'Bêtises']).toContain(words[1]);
    expect(['Fiesta', 'Dancefloor', 'Jusqu’au bout']).toContain(words[2]);
    expect(stepWords(couple).map((w) => w.word)).not.toContain('Fiesta');
  });

  test('its prices, each one’s share', () => {
    expect(routePrice(band)).toBe('45 €/pers.');
    expect(routePrice(couple)).toBe('90 €');
    expect(formatPrice(band.steps[0], band)).toBe('15 € par personne');
    expect(formatPrice(couple.steps[0], couple)).toBe('30 € à deux');
    expect(formatPrice(couple.steps[0])).toBe('30 € à deux');
  });

  test('two friends are a band, not a couple: each one’s share', () => {
    const friends: SoireeRoute = { ...couple, formule: 'squad', personnes: 2 };
    expect(routePrice(friends)).toBe('45 €/pers.');
    expect(formatPrice(friends.steps[0], friends)).toBe('15 € par personne');
  });
});

describe('a band’s phone', () => {
  test('the instigateur is told of the band, the band of its own book and its turn', () => {
    const alone = instigateurWeek({ ...base, booked: [], passager: false, squad: true });
    expect(alone.filter((b) => b.title.endsWith('Votre bande'))).toHaveLength(2);
    expect(alone.find((b) => b.title.endsWith('Votre bande'))!.body).toContain("Votre bande n'a pas encore son invitation");
    const joined = instigateurWeek({ ...base, booked: [], passager: true, squad: true });
    expect(joined.find((b) => b.id === 'ombre:0' || b.body.startsWith('Votre bande vient de recevoir'))!.body).toMatch(/^Votre bande vient de recevoir/);
    const week = passagerWeek(base);
    expect(week.find((b) => b.title.endsWith('Le Livre des Secrets'))!.body).toContain('Celles de la bande');
    expect(week.find((b) => b.title.endsWith('À votre tour'))!.body).toContain('prochaine virée de la bande');
  });

  test('the widget says Squad, and the band awaited', () => {
    const kept = { pageName: 'soiree-bande', route: band, mode: 'etapes' as const, secretTitle: SECRET, booked: ['test:comptoir', 'test:comedy'], squad: true };
    const before = local(DAY, 12, 0, -3);
    expect(widgetCard([{ ...kept, role: 'instigateur', passager: false }], before).line).toBe('Votre bande attend son invitation.');
    expect(widgetCard([{ ...kept, role: 'passager', passager: true }], before).kicker).toMatch(/^Squad · Invité · /);
  });
});

describe('what leaves the app', () => {
  test('the postcard is the band’s, the printed card Secret Squad’s', () => {
    expect(postcard(band, 'etapes', SECRET, local(DAY, 12, 0, -5)).line).toBe('Une virée secrète attend la bande : le reste est un mystère.');
    expect(postcard(band, 'etapes', SECRET, local(DAY, 11, 0, 1)).line).toBe('Une soirée vécue en bande, en secret.');
    const html = invitationHtml({ secretTitle: SECRET, when: 'Vendredi', link: 'https://example.com/invitation?code=x', brand: 'Secret Squad' });
    expect(html).toContain('SECRET SQUAD');
    expect(html).not.toContain('SECRET DATE');
  });

  test('a band’s evening is no step of the couple’s complicity', () => {
    const lived = (formule: 'duo' | 'squad') => ({ day: '2026-01-10', formule }) as EveningHistoryRow;
    expect(complicity([lived('duo'), lived('squad'), lived('squad')], '2026-10-06').lived).toBe(1);
  });
});

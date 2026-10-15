// Le duo and the day's question (supabase/migrations/…_duo_question_du_jour.sql): two accounts linked by an evening
// for two or by a code, one duo per account; each day's question sealed as the Livre is; the gauge fed by the base.
import { expect, test } from '@jest/globals';
import { chooseEvening, keptEvening } from '@/lib/account';
import { complicity, myComplicity } from '@/lib/complicity';
import { joinEvening } from '@/lib/couple';
import { answerToday, joinDuo, leaveDuo, myDuo, openDuo, pairedAnswers, partnerName, todaysQuestion } from '@/lib/duo';
import { sealPage } from '@/lib/souvenirs';
import { supabase } from '@/lib/supabase';

import { admin, as, keep, newAccount, pageName, PAST } from './helpers';

// Two accounts made, then paired by a code: the first opens its duo, the second enters its code.
async function pair(label: string) {
  const one = await newAccount(`${label}-un`);
  const code = await openDuo();
  const other = await newAccount(`${label}-deux`);
  await joinDuo(code);
  return { one, other, code };
}

test('a passager joining an evening for two pairs with its instigateur; a band never does', async () => {
  const lea = await newAccount('instigatrice');
  const row = await keep(PAST);
  expect(await myDuo()).toBeNull();
  const sam = await newAccount('passager');
  await joinEvening(row.invite_code);
  const duo = await myDuo();
  expect(duo).toMatchObject({ complete: true, partner: { user_id: lea.id, email: lea.email } });
  expect(partnerName(duo!.partner)).toMatch(/^Instigatrice$/);
  await as(lea);
  expect((await myDuo())?.partner?.user_id).toBe(sam.id);

  // A band's evening: its guests stay out of any duo.
  await newAccount('cerveau');
  const band = pageName();
  await chooseEvening({ pageName: band, title: 'Karaoké', secretTitle: 'La Virée', pitch: 'En bande.', vibes: ['rire'], day: PAST, formule: 'squad', personnes: 4 });
  const bandRow = await keptEvening(band);
  await newAccount('pote');
  await joinEvening(bandRow!.invite_code);
  expect(await myDuo()).toBeNull();
});

test('a duo by a code: two at most, one duo per account, its own code refused, the French reasons said', async () => {
  const { one, other, code } = await pair('code');
  expect(code).toMatch(/^[0-9a-f]{8}$/);
  expect((await myDuo())?.partner?.user_id).toBe(one.id);
  await as(one);
  expect(await openDuo()).toBe(code); // the same duo, its same code
  expect((await myDuo())?.partner?.user_id).toBe(other.id);

  await newAccount('troisieme');
  await expect(joinDuo(code)).rejects.toThrow('Ce duo est déjà complet.');
  await expect(joinDuo('pas-un-code')).rejects.toThrow('Code introuvable : demandez-le à nouveau à votre moitié.');
  const alone = await openDuo();
  await expect(joinDuo(alone)).rejects.toThrow("C'est votre propre code : envoyez-le à votre moitié.");

  // Already paired: the code of a duo waiting for its second is refused until this one is left.
  await newAccount('attend');
  const waiting = await openDuo();
  await as(one);
  await expect(joinDuo(waiting)).rejects.toThrow("Vous formez déjà un duo : quittez-le d'abord.");
  // Nobody writes a duo by hand.
  const forged = await supabase.from('duo_members').insert({ user_id: one.id, duo_id: (await myDuo())!.id });
  expect(forged.error).not.toBeNull();
});

test("the day's question: the same for both, each reads the other's answer once their own is sealed", async () => {
  const { one, other } = await pair('question');
  const today = await todaysQuestion();
  expect(today.question.texte.length).toBeGreaterThan(10);
  expect(today).toMatchObject({ mienne: null, sienne: null, sienne_donnee: false });
  await expect(answerToday('   ')).rejects.toThrow('Écrivez votre réponse avant de la sceller.');
  await answerToday('  Le café en terrasse ce matin.  ');
  await expect(answerToday('Encore')).rejects.toThrow('Votre réponse est déjà scellée.');
  expect(await todaysQuestion()).toMatchObject({ mienne: 'Le café en terrasse ce matin.', sienne: null, sienne_donnee: false });

  await as(one);
  const before = await todaysQuestion();
  expect(before.question.id).toBe(today.question.id);
  expect(before).toMatchObject({ mienne: null, sienne_donnee: true, sienne: null });
  // Not even straight from the table, before its own answer.
  const peek = await supabase.from('reponses_du_jour').select('texte').eq('author', other.id);
  expect(peek.data).toEqual([]);
  await answerToday('Ton rire au téléphone.');
  expect(await todaysQuestion()).toMatchObject({ mienne: 'Ton rire au téléphone.', sienne: 'Le café en terrasse ce matin.' });

  // Someone else's duo reads nothing of it.
  await newAccount('curieux');
  await expect(answerToday('Moi aussi')).rejects.toThrow("Formez d'abord votre duo : la question du jour se joue à deux.");
  expect((await supabase.from('reponses_du_jour').select('texte')).data).toEqual([]);
});

test('the days gone both answered are read again, the latest first; leaving the duo takes its answers away', async () => {
  const { one, other } = await pair('jours');
  const duo = (await myDuo())!;
  // Two days gone, written as they would have been: both answered the first, only one the second.
  const day = (back: number) => {
    const d = new Date();
    d.setDate(d.getDate() - back);
    return d.toISOString().slice(0, 10);
  };
  const rows = [
    { duo_id: duo.id, day: day(2), author: one.id, question_id: 1, texte: 'Le marché du dimanche.' },
    { duo_id: duo.id, day: day(2), author: other.id, question_id: 1, texte: 'Nos fous rires.' },
    { duo_id: duo.id, day: day(1), author: one.id, question_id: 2, texte: 'Seul de son côté.' },
  ];
  expect((await admin.from('reponses_du_jour').insert(rows)).error).toBeNull();
  const today = new Date().toISOString().slice(0, 10);
  const paired = await pairedAnswers(today);
  expect(paired).toEqual([{ day: day(2), question: expect.any(String), mienne: 'Nos fous rires.', sienne: 'Le marché du dimanche.' }]);
  expect((await myComplicity()).points).toBe(1);

  await leaveDuo();
  expect(await myDuo()).toBeNull();
  const left = await admin.from('reponses_du_jour').select('day').eq('duo_id', duo.id);
  expect(left.data).toEqual([]);
  await as(one);
  expect(await myDuo()).toBeNull();
});

test('the gauge: an evening for two lived and its Livre count, a band’s evening does not', async () => {
  await newAccount('jauge');
  expect(await myComplicity()).toMatchObject({ points: 0, name: 'Premiers regards', lived: 0 });
  const row = await keep(PAST);
  await sealPage(row.id, 'Inoubliable', null);
  const band = pageName();
  await chooseEvening({ pageName: band, title: 'Karaoké', secretTitle: 'La Virée', pitch: 'En bande.', vibes: ['rire'], day: PAST, formule: 'squad', personnes: 4 });
  const gauge = await myComplicity();
  expect(gauge).toMatchObject({ lived: 1, points: 13, name: 'Premiers regards', next: { name: 'Étincelles', left: 2 } });
  expect(gauge.next?.unlock).toMatch(/option secrète/);
});

test('the levels and what they unlock, from the points', () => {
  const at = (soirees: number, pages = 0, reponses = 0) =>
    complicity({ duo: true, complet: true, soirees, pages, reponses, quiz: 0, devinettes: 0, defis: 0 });
  expect(at(0)).toMatchObject({ points: 0, name: 'Premiers regards', unlocked: [] });
  expect(at(1, 2, 0)).toMatchObject({ points: 16, name: 'Étincelles', unlocked: ['option-secrete'] });
  expect(at(4)).toMatchObject({ points: 40, name: 'Étoiles filantes', unlocked: ['option-secrete', 'intrigue-speciale'] });
  expect(at(8)).toMatchObject({ name: 'Constellation', unlocked: ['option-secrete', 'intrigue-speciale', 'theme-minuit'] });
  expect(at(15)).toMatchObject({ name: 'Âmes complices', progress: 1, next: null });
  expect(at(2, 0, 5).progress).toBeCloseTo((25 - 15) / (40 - 15));
});

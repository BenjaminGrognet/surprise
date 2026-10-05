// The riddles shown to the partner who is being surprised, read off the chosen route with plain
// rules (no Claude call): what to wear, when to be ready, which bank of the Seine… Each one
// unlocks at its own time before the evening, so the mystery lifts step by step.
import type { SoireeRoute, SoireeStep } from '@/lib/api';
import { formatTime } from '@/lib/dates';

// What a clue tells, for the chapter it opens in the passager's week (lib/story.ts).
export type ClueKind = 'rendezvous' | 'ouverture' | 'budget' | 'tenue' | 'table' | 'duree' | 'bagage' | 'sens' | 'carte' | 'compte';
export type Clue = { text: string; at: number; kind: ClueKind }; // at: epoch ms when it shows (0: from the start)

// How the programme is lifted for the passager, chosen by the instigateur (soirees_choisies.reveal_mode).
export type RevealMode = 'etapes' | 'veille' | 'arrivee';
export const REVEAL_MODES: { key: RevealMode; label: string; hint: string }[] = [
  { key: 'etapes', label: 'Étape par étape', hint: 'Chaque étape, un quart d’heure avant son heure.' },
  { key: 'veille', label: 'La veille', hint: 'Tout le programme d’un coup, 24 h avant le début.' },
  { key: 'arrivee', label: 'Sur place', hint: 'Chaque étape à son heure, ou dès qu’il signale être arrivé.' },
];
export const revealMode = (value: string | null | undefined): RevealMode =>
  value === 'veille' || value === 'arrivee' ? value : 'etapes';

const HOUR = 3600_000;
const DAY = 24 * HOUR;
const LEFT_BANK = new Set([5, 6, 7, 13, 14, 15]);

// One line per vibe, in the order they're looked for: the rarer and more telling first.
const SENSES: [string, string][] = [
  ['frisson', 'Le cœur risque de battre un peu plus vite.'],
  ['coquin', 'Une note pimentée se cache dans le programme.'],
  ['insolite', "Un lieu que vous n'auriez jamais trouvé seuls."],
  ['musique', 'Vos oreilles sont invitées.'],
  ['rire', 'Préparez vos zygomatiques.'],
  ['creer', 'Vous repartirez avec quelque chose fait de vos mains.'],
  ['defi', 'Un défi vous attend : jouez collectif.'],
  ['emerveiller', 'Ouvrez grand les yeux, ça va briller.'],
  ['cultiver', 'Vous en ressortirez un peu plus savants.'],
  ['savourer', 'Vos papilles sont conviées.'],
  ['detente', 'Tout est prévu pour ralentir.'],
  ['flaner', 'Une partie du chemin se fait à pied.'],
];

function allSteps(route: SoireeRoute) {
  return [...route.steps, ...(route.night ? [route.night] : [])];
}

function has(steps: SoireeStep[], ...vibes: string[]) {
  return steps.some((s) => s.vibes.some((v) => vibes.includes(v)));
}

function outfit(route: SoireeRoute) {
  const steps = route.steps;
  const endHour = Number(formatTime(route.end).slice(0, 2)); // on Paris time, like the evening
  if (has(steps, 'bouger')) return 'Chaussures plates et tenue souple : vous allez bouger.';
  if (has(steps, 'creer')) return 'Une tenue qui ne craint ni la farine ni la peinture.';
  if (has(steps, 'fete') && endHour >= 1 && endHour < 6) return 'Des chaussures pour danser : la nuit sera longue.';
  if (has(steps, 'flaner')) return 'Une petite laine : une partie se joue dehors.';
  if (has(steps, 'romantique', 'emerveiller', 'savourer')) return "Portez une touche de doré : ce soir, on s'habille un peu.";
  return 'Venez comme vous êtes, avec un sourire en coin.';
}

function geography(route: SoireeRoute) {
  const steps = allSteps(route);
  if (steps.some((s) => s.arrondissement == null && s.town && s.town !== 'Paris')) return 'Ce soir, on passe le périphérique.';
  const banks = new Set(steps.filter((s) => s.arrondissement != null).map((s) => (LEFT_BANK.has(s.arrondissement!) ? 'gauche' : 'droite')));
  if (banks.size > 1) return 'Votre destination finale nécessite de traverser la Seine…';
  if (banks.size === 1) return `Tout se joue rive ${[...banks][0]}.`;
  return null;
}

// "Une soirée douce pour le portefeuille", from what the two of them will spend.
function budget(route: SoireeRoute) {
  if (route.price < 1) return "Rien à sortir du portefeuille : l'essentiel est offert.";
  if (route.price < 50) return 'Une soirée douce pour le portefeuille.';
  if (route.price < 120) return 'Un budget raisonnable, pour une soirée qui ne l’est pas.';
  return 'On sort le grand jeu : ce soir, on ne compte pas.';
}

function opening(route: SoireeRoute) {
  const first = route.steps[0];
  if (!first) return null;
  if (first.role === 'repas') return 'Tout commence autour d’une table.';
  if (first.role === 'verre') return 'Tout commence par un verre.';
  return 'Tout commence par une sortie.';
}

function duration(route: SoireeRoute) {
  const hours = Math.max(1, Math.round((Date.parse(route.end) - Date.parse(route.start)) / HOUR));
  return `Comptez environ ${hours} h de mystère.`;
}

// One clue a day from five days out (nine in the morning), then the tighter rhythm of the last day.
// A clue already past shows at once: an evening kept the day before has them all.
export function cluesFor(route: SoireeRoute, mode: RevealMode = 'etapes'): Clue[] {
  const start = Date.parse(route.start);
  const morning = (daysBefore: number) => Date.parse(`${route.day}T09:00`) - daysBefore * DAY;
  const clues: Clue[] = [
    { text: `Le rideau se lève à ${formatTime(route.start)}. Soyez prêts un peu avant.`, at: 0, kind: 'rendezvous' },
    { text: budget(route), at: morning(4), kind: 'budget' },
    { text: outfit(route), at: morning(3), kind: 'tenue' },
    {
      text: route.steps.some((s) => s.role === 'repas')
        ? 'Ne dînez pas avant : une table est prévue.'
        : 'Mangez un morceau avant de partir : pas de dîner au programme.',
      at: morning(2),
      kind: 'table',
    },
    { text: duration(route), at: morning(1), kind: 'duree' },
  ];
  const first = opening(route);
  if (first) clues.push({ text: first, at: morning(5), kind: 'ouverture' });
  if (route.night) clues.push({ text: 'Glissez une brosse à dents dans votre sac : vous ne dormirez pas chez vous.', at: morning(1), kind: 'bagage' });
  // One sense per step, the first that tells it, spread over the last days.
  const senses = new Set<string>();
  for (const step of route.steps) {
    const line = SENSES.find(([vibe, text]) => step.vibes.includes(vibe) && !senses.has(text));
    if (line) senses.add(line[1]);
  }
  [...senses].slice(0, 3).forEach((text, i) => clues.push({ text, at: [morning(2) + 6 * HOUR, start - 12 * HOUR, start - 4 * HOUR][i], kind: 'sens' }));
  const where = geography(route);
  if (where) clues.push({ text: where, at: start - 6 * HOUR, kind: 'carte' });
  const count = route.steps.length;
  clues.push({
    text: route.night
      ? `${count} étape${count > 1 ? 's' : ''}, puis une nuit ailleurs.`
      : `${count} étape${count > 1 ? 's' : ''} ; le mystère se referme vers ${formatTime(route.end)}.`,
    at: start - 2 * HOUR,
    kind: 'compte',
  });
  // "La veille": the programme itself shows the day before, so the clues stop there.
  const kept = mode === 'veille' ? clues.filter((c) => c.at <= start - DAY) : clues;
  return kept.sort((a, b) => a.at - b.at);
}

export const shownClues = (clues: Clue[], now: number) => clues.filter((c) => c.at <= now);
export const nextClue = (clues: Clue[], now: number) => clues.find((c) => c.at > now) ?? null;

// The hint of the day: the latest one unlocked, past the meeting time everyone already knows.
export function dayHint(route: SoireeRoute, now: number, mode: RevealMode = 'etapes') {
  const shown = shownClues(cluesFor(route, mode), now);
  return shown.length > 1 ? shown[shown.length - 1].text : outfit(route);
}

// The mystery word of a veiled step: a mood to look forward to, never what or where. The step's most telling vibe
// first (the rarer ones lead), else its role; a few words each, so two steps of one vibe don't share theirs.
const WORDS: [string, string[]][] = [
  ['frisson', ['Vertige', 'Frisson', 'Adrénaline']],
  ['coquin', ['Audace', 'Velours', 'Interdit']],
  ['insolite', ['Insolite', 'Énigme', 'Ailleurs']],
  ['musique', ['Mélodie', 'Vibrations', 'Résonance']],
  ['rire', ['Malice', 'Fantaisie', 'Éclats de rire']],
  ['creer', ['Savoir-faire', 'Inspiration', 'Façonner']],
  ['defi', ['Stratégie', 'Défi', 'Complicité']],
  ['emerveiller', ['Éblouissement', 'Lumières', 'Merveille']],
  ['cultiver', ['Curiosité', 'Mémoire', 'Érudition']],
  ['savourer', ['Gourmandise', 'Saveurs', 'Délice']],
  ['detente', ['Douceur', 'Lenteur', 'Apaisement']],
  ['flaner', ['Flânerie', 'Grand air', 'Dérive']],
  ['bouger', ['Élan', 'Mouvement', 'Énergie']],
  ['fete', ['Effervescence', 'Ivresse', 'Pétillant']],
  ['romantique', ['Tendresse', 'Intimité', 'Murmures']],
];
const ROLE_WORDS: Record<SoireeStep['role'], string[]> = {
  repas: ['Gourmandise', 'Saveurs', 'Tablée'],
  verre: ['Pétillant', 'Tchin', 'Ivresse'],
  sortie: ['Surprise', 'Mystère', 'Curiosité'],
  nuit: ['Rêverie', 'Clair de lune', 'Évasion'],
};

// The same step always draws the same word.
function seed(text: string) {
  let h = 0;
  for (const c of text) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return h;
}

function stepWord(step: SoireeStep, taken: Set<string>) {
  const pools = [...WORDS.filter(([vibe]) => step.vibes.includes(vibe)).map(([, words]) => words), ROLE_WORDS[step.role]];
  for (const pool of pools) {
    const start = seed(step.id) % pool.length;
    const word = [...pool.slice(start), ...pool.slice(0, start)].find((w) => !taken.has(w));
    if (word) return word;
  }
  return 'Mystère';
}

export type StepWord = { word: string; at: number }; // at: epoch ms when it shows (0: from the start)

// One mystery word per step, in the programme's order: the first from the start, the others one by one over the last
// days (three days before, the day before, the afternoon, the last hours), always an hour before their step lifts its veil.
export function stepWords(route: SoireeRoute, mode: RevealMode = 'etapes'): StepWord[] {
  const start = Date.parse(route.start);
  const morning = (daysBefore: number) => Date.parse(`${route.day}T09:00`) - daysBefore * DAY;
  const moments = [morning(3) + 6 * HOUR, morning(1) + 6 * HOUR, start - 5 * HOUR, start - 2 * HOUR];
  const taken = new Set<string>();
  return allSteps(route).map((step, i) => {
    const word = stepWord(step, taken);
    taken.add(word);
    const at = i === 0 ? 0 : Math.min(moments[Math.min(i - 1, moments.length - 1)], revealAt(route, step, mode) - HOUR);
    return { word, at };
  });
}

// When a step lifts its veil for the passager, by mode: a quarter of an hour before its hour (etapes), the day
// before the evening (veille), at its hour or as soon as they declare arriving (arrivee, `arrived` = step ids).
export function revealAt(route: SoireeRoute, step: SoireeStep, mode: RevealMode) {
  if (mode === 'veille') return Date.parse(route.start) - DAY;
  return Date.parse(step.start) - (mode === 'arrivee' ? 0 : HOUR / 4);
}

export function stepRevealed(route: SoireeRoute, step: SoireeStep, now: number, mode: RevealMode = 'etapes', arrived: string[] = []) {
  return revealAt(route, step, mode) <= now || (mode === 'arrivee' && arrived.includes(step.id));
}

// "dans 3 h", "dans 2 j", "dans 25 min".
export function inTime(at: number, now: number) {
  const minutes = Math.max(1, Math.ceil((at - now) / 60_000));
  if (minutes < 60) return `dans ${minutes} min`;
  const hours = Math.round(minutes / 60);
  return hours < 48 ? `dans ${hours} h` : `dans ${Math.round(hours / 24)} j`;
}

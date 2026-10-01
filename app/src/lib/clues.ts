// The riddles shown to the partner who is being surprised, read off the chosen route with plain
// rules (no Claude call): what to wear, when to be ready, which bank of the Seine… Each one
// unlocks at its own time before the evening, so the mystery lifts step by step.
import type { SoireeRoute, SoireeStep } from '@/lib/api';
import { formatTime } from '@/lib/dates';

export type Clue = { text: string; at: number }; // at: epoch ms when it shows (0: from the start)

const HOUR = 3600_000;
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

export function cluesFor(route: SoireeRoute): Clue[] {
  const start = Date.parse(route.start);
  const clues: Clue[] = [
    { text: `Le rideau se lève à ${formatTime(route.start)}. Soyez prêts un peu avant.`, at: 0 },
    { text: outfit(route), at: 0 },
    {
      text: route.steps.some((s) => s.role === 'repas')
        ? 'Ne dînez pas avant : une table est prévue.'
        : 'Mangez un morceau avant de partir : pas de dîner au programme.',
      at: 0,
    },
  ];
  if (route.night) clues.push({ text: 'Glissez une brosse à dents dans votre sac : vous ne dormirez pas chez vous.', at: start - 24 * HOUR });
  // One sense per step, the first that tells it, spread over the last day.
  const senses = new Set<string>();
  for (const step of route.steps) {
    const line = SENSES.find(([vibe, text]) => step.vibes.includes(vibe) && !senses.has(text));
    if (line) senses.add(line[1]);
  }
  [...senses].slice(0, 3).forEach((text, i) => clues.push({ text, at: start - [24, 12, 4][i] * HOUR }));
  const where = geography(route);
  if (where) clues.push({ text: where, at: start - 6 * HOUR });
  const count = route.steps.length;
  clues.push({
    text: route.night
      ? `${count} étape${count > 1 ? 's' : ''}, puis une nuit ailleurs.`
      : `${count} étape${count > 1 ? 's' : ''} ; le mystère se referme vers ${formatTime(route.end)}.`,
    at: start - 2 * HOUR,
  });
  return clues.sort((a, b) => a.at - b.at);
}

export const shownClues = (clues: Clue[], now: number) => clues.filter((c) => c.at <= now);
export const nextClue = (clues: Clue[], now: number) => clues.find((c) => c.at > now) ?? null;

// The hint of the day: the latest one unlocked, past the meeting time everyone already knows.
export function dayHint(route: SoireeRoute, now: number) {
  const shown = shownClues(cluesFor(route), now);
  return shown.length > 1 ? shown[shown.length - 1].text : outfit(route);
}

// A step stays veiled for the partner to surprise until a quarter of an hour before it starts.
export const stepRevealed = (step: SoireeStep, now: number) => Date.parse(step.start) - HOUR / 4 <= now;

// "dans 3 h", "dans 2 j", "dans 25 min".
export function inTime(at: number, now: number) {
  const minutes = Math.max(1, Math.ceil((at - now) / 60_000));
  if (minutes < 60) return `dans ${minutes} min`;
  const hours = Math.round(minutes / 60);
  return hours < 48 ? `dans ${hours} h` : `dans ${Math.round(hours / 24)} j`;
}

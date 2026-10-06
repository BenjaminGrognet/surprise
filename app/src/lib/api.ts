import { Platform } from 'react-native';

// The Python quiz/soiree server (src/surprise/quiz.py) — profile and evening composition,
// unrelated to Supabase (accounts, history), which the app talks to directly.
// The web build (npm run build:web) is served by that same server: same origin, from any host.
// ponytail: hosting the site apart from the API would mean building it with its URL instead.
export const API_URL =
  Platform.OS === 'web' && !__DEV__ ? '' : (process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8001');

// A failed call, with the server's reason when it gives one ({"error": …}).
export class ApiError extends Error {
  status: number;
  reason: string | null;
  constructor(path: string, status: number, reason: string | null) {
    super(`${path}: ${status}`);
    this.status = status;
    this.reason = reason;
  }
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });
  if (!r.ok) throw new ApiError(path, r.status, await r.json().then((body) => body?.error ?? null, () => null));
  return r.json();
}

// The server's refusal (409: no other activity for that step…) as a sentence for the page; null for any other failure.
export function refusal(error: unknown): string | null {
  if (!(error instanceof ApiError) || error.status !== 409 || !error.reason) return null;
  return `${error.reason[0].toUpperCase()}${error.reason.slice(1)}.`;
}

export type Persona = { name: string; text: string };
export type Profile = {
  names?: string;
  persona: Persona;
  vibes: string[];
  first_day?: string;
  budget: number;
  audace: number;
};
export type QuizOption = { value: unknown; label?: string; emoji?: string; desc?: string; icon?: string };
export type Question = {
  id: string;
  kind: 'single' | 'scale' | 'multi' | 'date' | 'text';
  question: string;
  hint?: string;
  options?: QuizOption[];
  min?: number;
  max?: number;
};
export type QuizData = { questions: Question[]; vibes: Record<string, string> };

export const getQuiz = () => api<QuizData>('/api/quiz');
// Stateless: the server only scores the answers, it doesn't keep them — the profile itself
// lives on this device (see lib/local-store.ts) and, for a signed-in couple, in Supabase.
export const saveProfile = (answers: Record<string, unknown>) =>
  api<{ profile: Profile }>('/api/profiles', { method: 'POST', body: JSON.stringify({ answers }) }).then((r) => r.profile);

export type ChipOption = { value: string; label: string; emoji?: string; icon?: string };
export type BudgetOption = { budget: number; label: string; desc?: string; emoji?: string; icon?: string };
// Secret Date, a couple's evening, or Secret Squad, a band of friends' (surprise.quiz SQUAD_…).
export type Formule = 'duo' | 'squad';
export type SoireeData = {
  formule?: Formule;
  envies: ChipOption[];
  moods?: string[]; // the mood cards, from the calmest to the wildest: wishes among `envies`
  occasions: ChipOption[];
  max: number;
  starts: ChipOption[];
  ends: ChipOption[];
  budgets: BudgetOption[]; // a band's: per person
  personnes?: { min: number; max: number; default: number }; // a band's size
  vibes?: Record<string, string>; // a band's words for the vibes
};
export type Night = {
  // A band's evening (Secret Squad), for `personnes`, its budget per person; a couple's otherwise.
  formule?: Formule;
  personnes?: number;
  envies: string[];
  diner: boolean | null;
  decoucher: boolean;
  occasion: string | null;
  start: string | null;
  end: string | null;
  budget: number | null;
  day: string;
  profile: Profile | null;
  // The evenings the couple chose (its history, by their pages): their activities are never proposed again.
  done?: string[];
  // Their votes on steps (lib/account.ts votesOf): the kinds of outing liked come first, those voted out never.
  votes?: Record<string, 1 | -1>;
};

export const getSoiree = (formule: Formule = 'duo') => api<SoireeData>(formule === 'squad' ? '/api/soiree?formule=squad' : '/api/soiree');

// One step of a composed route (surprise.parcours.step_json): all the raw data, no HTML —
// this screen decides how to lay it out.
export type SoireeStep = {
  start: string;
  end: string;
  travel_minutes: number;
  distance_km: number;
  title: string;
  venue: string;
  arrondissement: number | null;
  town: string | null;
  lat: number;
  lon: number;
  role: 'repas' | 'verre' | 'sortie' | 'nuit';
  kind: 'verifie' | 'seance' | 'gratuit' | 'sans_resa' | 'nuit';
  price: number;
  price_estimated: boolean;
  booking_url: string | null;
  booking_action: 'voir_lieu' | 'voir_fiche' | 'reserver';
  image_url: string | null;
  text: string | null;
  vibes: string[];
  keywords: string[];
  originality: number;
  basis: string;
  id: string; // source_id:external_id, the activity itself
  source_id: string;
  source_name: string;
  redo: string | null;
};
// Where a step is: its venue and its quarter (or town).
export function place(step: SoireeStep) {
  const where = step.arrondissement ? `Paris ${step.arrondissement}ᵉ` : step.town && step.town !== 'Paris' ? step.town : null;
  return [step.venue, where].filter(Boolean).join(' · ');
}

export type SoireeRoute = {
  index: number;
  title: string;
  secret_title: string; // its name once kept, shown to the passager too: a mood and a quarter, no venue
  // A band's evening (Secret Squad) and how many go out: its prices count them all, its clues and words are theirs.
  formule?: Formule;
  personnes?: number;
  pitch: string;
  day: string;
  start: string;
  end: string;
  price: number;
  price_estimated: boolean;
  steps: SoireeStep[];
  night: SoireeStep | null;
  redo: string;
};
export type ComposedSoiree = {
  name: string;
  naming: boolean; // Claude's titles are still coming: poll getSoireeState until it clears
  chosen: boolean; // the couple kept a route: it is the only one left, the page's name is enough to find it
  days: string[];
  start: string;
  end: string;
  budget: number;
  night_budget: number | null;
  vibes: string[];
  trame: string[];
  formule?: Formule;
  personnes?: number;
  routes: SoireeRoute[];
};

export const composeSoiree = (night: Night) => api<ComposedSoiree>('/api/soirees', { method: 'POST', body: JSON.stringify(night) });
export const getSoireeState = (name: string) => api<ComposedSoiree>(`/api/parcours/${encodeURIComponent(name)}`);
// A step's image the page could not show, even on a second try: the server checks it, and answers with another (the
// official site's) or null.
export const reportBrokenImage = (id: string, url: string) =>
  api<{ image_url: string | null }>('/api/images/broken', { method: 'POST', body: JSON.stringify({ id, url }) });
export const redoPart = (name: string, redo: string) =>
  api<ComposedSoiree>(`/api/parcours/${name}/${redo}`, { method: 'POST', body: '{}' });
// The route kept: the page keeps it alone from now on (the others go), as its route 0.
export const chooseRoute = (name: string, index: number) =>
  api<ComposedSoiree>(`/api/parcours/${name}/routes/${index}/choose`, { method: 'POST', body: '{}' });

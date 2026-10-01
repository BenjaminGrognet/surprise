import { Platform } from 'react-native';

// The Python quiz/soiree server (src/surprise/quiz.py) — profile and evening composition,
// unrelated to Supabase (accounts, history), which the app talks to directly.
// The web build (npm run build:web) is served by that same server: same origin, from any host.
// ponytail: hosting the site apart from the API would mean building it with its URL instead.
export const API_URL =
  Platform.OS === 'web' && !__DEV__ ? '' : (process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8001');

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
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

export type ChipOption = { value: string; label: string; emoji?: string };
export type BudgetOption = { budget: number; label: string; emoji?: string };
export type SoireeData = {
  envies: ChipOption[];
  occasions: ChipOption[];
  max: number;
  starts: ChipOption[];
  ends: ChipOption[];
  budgets: BudgetOption[];
};
export type Night = {
  envies: string[];
  diner: boolean | null;
  decoucher: boolean;
  occasion: string | null;
  start: string | null;
  end: string | null;
  budget: number | null;
  day: string;
  profile: Profile | null;
  // The evenings the couple chose (its history): their activities are never proposed again.
  done?: { page_name: string; route_index: number }[];
};

export const getSoiree = () => api<SoireeData>('/api/soiree');

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
export type SoireeRoute = {
  index: number;
  title: string;
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
  days: string[];
  start: string;
  end: string;
  budget: number;
  night_budget: number | null;
  vibes: string[];
  trame: string[];
  routes: SoireeRoute[];
};

export const composeSoiree = (night: Night) => api<ComposedSoiree>('/api/soirees', { method: 'POST', body: JSON.stringify(night) });
export const getSoireeState = (name: string) => api<ComposedSoiree>(`/api/parcours/${encodeURIComponent(name)}`);
export const redoPart = (name: string, redo: string) =>
  api<ComposedSoiree>(`/api/parcours/${name}/${redo}`, { method: 'POST', body: '{}' });

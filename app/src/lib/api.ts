// The Python quiz/soiree server (src/surprise/quiz.py) — profile and evening composition,
// unrelated to Supabase (accounts, history), which the app talks to directly.
export const API_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';

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
export type SavedProfile = { id: string; profile: Profile; answers: Record<string, unknown> };

export type QuizOption = { value: unknown; label?: string; emoji?: string };
export type Question = {
  id: string;
  kind: 'single' | 'scale' | 'multi' | 'date' | 'text';
  question: string;
  hint?: string;
  options?: QuizOption[];
  max?: number;
};
export type QuizData = { questions: Question[]; vibes: Record<string, string> };

export const getQuiz = () => api<QuizData>('/api/quiz');
export const getProfile = (id: string) => api<SavedProfile>(`/api/profiles/${encodeURIComponent(id)}`);
export const saveProfile = (answers: Record<string, unknown>) =>
  api<SavedProfile>('/api/profiles', { method: 'POST', body: JSON.stringify({ answers }) });

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
  profile: string | null;
};

export const getSoiree = () => api<SoireeData>('/api/soiree');
export const composeSoiree = (night: Night) =>
  api<{ url: string; count: number }>('/api/soirees', { method: 'POST', body: JSON.stringify(night) });

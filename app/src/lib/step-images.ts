// A step's photo and what stands in for it: the sites' images can be slow, refused or gone (see StepImage).
import { API_URL, type SoireeStep } from '@/lib/api';

// The server's own images (a kept evening's copies) are paths on it; the sites' are full addresses.
export const imageUri = (url: string) => (url.startsWith('/') ? API_URL + url : url);

// Before a photo that did not load is asked for again.
export const RETRY_MS = 2000;

// Stored with the app (assets/images/bannieres, sources in SOURCES.md): they always show.
const BANNERS = {
  complices: require('@/assets/images/bannieres/complices.jpg'),
  creatifs: require('@/assets/images/bannieres/creatifs.jpg'),
  curieux: require('@/assets/images/bannieres/curieux.jpg'),
  epicuriens: require('@/assets/images/bannieres/epicuriens.jpg'),
  explorateurs: require('@/assets/images/bannieres/explorateurs.jpg'),
  flaneurs: require('@/assets/images/bannieres/flaneurs.jpg'),
  noctambules: require('@/assets/images/bannieres/noctambules.jpg'),
  romantiques: require('@/assets/images/bannieres/romantiques.jpg'),
} as const;
export type Banner = keyof typeof BANNERS;

const BY_ROLE: Partial<Record<SoireeStep['role'], Banner>> = { repas: 'epicuriens', verre: 'noctambules', nuit: 'romantiques' };
const BY_VIBE: Record<string, Banner> = {
  rire: 'complices', defi: 'complices', bouger: 'complices',
  creer: 'creatifs',
  cultiver: 'curieux', emerveiller: 'curieux',
  savourer: 'epicuriens',
  flaner: 'flaneurs',
  fete: 'noctambules', musique: 'noctambules',
  insolite: 'explorateurs', frisson: 'explorateurs',
  romantique: 'romantiques', detente: 'romantiques', coquin: 'romantiques',
};

// The picture of the step's kind: a meal, a drink, a night, else the first mood of its activity.
export function bannerName(step: Pick<SoireeStep, 'role' | 'vibes'>): Banner {
  return BY_ROLE[step.role] ?? step.vibes.map((v) => BY_VIBE[v]).find(Boolean) ?? 'romantiques';
}

export const banner = (step: Pick<SoireeStep, 'role' | 'vibes'>): number => BANNERS[bannerName(step)];

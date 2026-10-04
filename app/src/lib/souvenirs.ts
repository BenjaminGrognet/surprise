// Le Livre des Secrets (supabase/migrations/…_souvenirs.sql): after a kept evening, each of the couple seals
// one page — a photo, a note. Sealed is final; the other's page reads only once one's own is sealed.
import type { EveningHistoryRow } from '@/lib/account';
import type { SoireeRoute } from '@/lib/api';
import { currentUser, supabase } from '@/lib/supabase';

export type Souvenir = { soiree_id: string; author: string; note: string; photo: string | null; sealed_at: string };

// A page with its photo's signed link, ready to show.
export type Page = Souvenir & { photoUrl: string | null; mine: boolean };

export type Book = { evening: EveningHistoryRow; pages: Page[] };

// The kept evening's book, found as the revelation finds it: by its page and route.
export async function book(pageName: string, routeIndex: number): Promise<Book | null> {
  const user = await currentUser();
  if (!user) return null;
  const { data, error } = await supabase
    .from('soirees_choisies').select('*, souvenirs(*)').eq('page_name', pageName).eq('route_index', routeIndex)
    .order('chosen_at', { ascending: false }).limit(1);
  if (error) throw new Error(error.message);
  if (!data?.length) return null;
  const { souvenirs, ...evening } = data[0] as Omit<EveningHistoryRow, 'souvenirs'> & { souvenirs: Souvenir[] };
  const urls = await photoUrls(souvenirs.map((s) => s.photo));
  const pages = souvenirs
    .map((s) => ({ ...s, photoUrl: s.photo ? urls[s.photo] ?? null : null, mine: s.author === user.id }))
    .sort((a, b) => Number(b.mine) - Number(a.mine));
  return { evening: evening as EveningHistoryRow, pages };
}

export async function photoUrls(paths: (string | null)[]): Promise<Record<string, string>> {
  const wanted = paths.filter((p): p is string => !!p);
  if (!wanted.length) return {};
  const { data, error } = await supabase.storage.from('souvenirs').createSignedUrls(wanted, 60 * 60);
  if (error) return {};
  return Object.fromEntries(data.flatMap((d) => (d.signedUrl && d.path ? [[d.path, d.signedUrl]] : [])));
}

export type Fragment = { uri: string; mimeType?: string | null };

// Seals the account's page: the photo first, under <soiree>/<author>/, then the note — the row is the seal.
export async function sealPage(soireeId: string, note: string, fragment: Fragment | null) {
  const user = await currentUser();
  if (!user) throw new Error('Connectez-vous pour sceller votre page.');
  let photo: string | null = null;
  if (fragment) {
    const type = fragment.mimeType || 'image/jpeg';
    const ext = type.split('/')[1]?.replace('jpeg', 'jpg') || 'jpg';
    photo = `${soireeId}/${user.id}/${Date.now()}.${ext}`;
    const bytes = await (await fetch(fragment.uri)).arrayBuffer();
    const { error } = await supabase.storage.from('souvenirs').upload(photo, bytes, { contentType: type });
    if (error) throw new Error(`La photo n'a pas pu être déposée : ${error.message}`);
  }
  const { error } = await supabase.from('souvenirs').insert({ soiree_id: soireeId, author: user.id, note: note.trim(), photo });
  if (error) throw new Error(error.code === '23505' ? 'Votre page est déjà scellée.' : error.message);
}

// The book opens once the evening has come: on its day, then forever after.
export const bookOpen = (row: { day: string | null }, today: string) => !!row.day && row.day <= today;

// On the day itself, the time to call for it: the evening's last step has begun (the night left aside).
export function curtainFalls(route: SoireeRoute, now: number) {
  const last = route.steps[route.steps.length - 1];
  return !!last && now >= Date.parse(last.start);
}

// The photo paths stored under <soiree>/…, or only under <soiree>/<author>/ when one is given.
async function photoPaths(soireeId: string, author?: string): Promise<string[]> {
  const bucket = supabase.storage.from('souvenirs');
  const folders = author ? [author] : ((await bucket.list(soireeId)).data ?? []).map((f) => f.name);
  const paths: string[] = [];
  for (const folder of folders) {
    const { data } = await bucket.list(`${soireeId}/${folder}`);
    paths.push(...(data ?? []).map((f) => `${soireeId}/${folder}/${f.name}`));
  }
  return paths;
}

// Removes the photos of these evenings (all of them, or only the account's own).
export async function removePhotos(soireeIds: string[], author?: string) {
  const paths = (await Promise.all(soireeIds.map((id) => photoPaths(id, author)))).flat();
  if (paths.length) await supabase.storage.from('souvenirs').remove(paths);
}

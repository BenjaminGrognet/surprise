// Le bilan du lendemain (docs/complicite.md, C16): on the Livre's page, once the evening is over, each one's favourite
// moment (public.bilans, read by the other once their own is given), and the steps to do again or to avoid — the
// couple's votes (public.gouts), which the next evenings follow.
import { currentUser, saveTaste } from '@/lib/account';
import type { SoireeStep } from '@/lib/api';
import { supabase } from '@/lib/supabase';

export type Bilan = { author: string; prefere: string; prefere_titre: string; mine: boolean };

export async function reviews(soireeId: string): Promise<Bilan[]> {
  const user = await currentUser();
  const { data, error } = await supabase.from('bilans').select('author, prefere, prefere_titre').eq('soiree_id', soireeId);
  if (error) throw new Error(error.message);
  return (data as Omit<Bilan, 'mine'>[]).map((b) => ({ ...b, mine: b.author === user?.id })).sort((a, b) => Number(b.mine) - Number(a.mine));
}

// The review given: the favourite step, and a vote for each step to do again (+1) or to avoid (-1).
export async function giveReview(soireeId: string, favourite: Pick<SoireeStep, 'id' | 'title'>, again: Pick<SoireeStep, 'id' | 'title'>[], avoid: Pick<SoireeStep, 'id' | 'title'>[]) {
  const { error } = await supabase.from('bilans').insert({ soiree_id: soireeId, prefere: favourite.id, prefere_titre: favourite.title });
  if (error) throw new Error(error.code === '23505' ? 'Votre bilan est déjà donné.' : error.message);
  await Promise.all([...again.map((s) => saveTaste(s, 1)), ...avoid.map((s) => saveTaste(s, -1))]);
}

import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { PrimaryButton } from '@/components/buttons';
import { ThemedText } from '@/components/themed-text';
import { Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { getSoireeState, type SoireeStep } from '@/lib/api';
import { giveReview, reviews, type Bilan } from '@/lib/bilan';

// « Le bilan du lendemain » (docs/complicite.md, C16), under the Livre once the evening is over: the favourite moment,
// the steps to do again, those to avoid — three questions; then each one's favourite, the other's once one's own is
// given. Its votes guide the next evenings (public.gouts).
export function Review({ soireeId, pageName, squad }: { soireeId: string; pageName: string; squad: boolean }) {
  const theme = useTheme();
  const [steps, setSteps] = useState<SoireeStep[]>([]);
  const [given, setGiven] = useState<Bilan[] | null>(null);
  const [favourite, setFavourite] = useState<string | null>(null);
  const [again, setAgain] = useState<string[]>([]);
  const [avoid, setAvoid] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    getSoireeState(pageName).then((state) => setSteps(state.routes[0]?.steps ?? []), () => {});
    reviews(soireeId).then(setGiven, () => setGiven([]));
  }, [pageName, soireeId]);

  if (!steps.length || given === null) return null;
  const mine = given.find((b) => b.mine);
  const toggle = (list: string[], id: string) => (list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);

  async function send() {
    const step = steps.find((s) => s.id === favourite);
    if (!step) return;
    setBusy(true);
    setError('');
    try {
      await giveReview(soireeId, step, steps.filter((s) => again.includes(s.id)), steps.filter((s) => avoid.includes(s.id)));
      setGiven(await reviews(soireeId));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <View testID="bilan" style={[styles.card, { backgroundColor: theme.velvet, borderColor: theme.accentSoft }]}>
      <ThemedText type="eyebrow">Le bilan du lendemain</ThemedText>
      {mine ? (
        <>
          {given.map((b) => (
            <ThemedText key={b.author} style={{ color: theme.cream }}>
              {b.mine ? `Votre moment préféré : ${b.prefere_titre}` : `${squad ? 'Un moment préféré de la bande' : 'Celui de votre complice'} : ${b.prefere_titre}`}
            </ThemedText>
          ))}
          {given.length < 2 && !squad ? (
            <ThemedText type="small" themeColor="textSecondary">Le moment préféré de votre complice apparaîtra ici dès qu’il sera donné.</ThemedText>
          ) : null}
        </>
      ) : (
        <>
          <Question label="Votre moment préféré" steps={steps} chosen={favourite ? [favourite] : []} onPick={(id) => setFavourite(id)} />
          <Question label="À refaire" steps={steps} chosen={again} onPick={(id) => {
            setAgain((a) => toggle(a, id));
            setAvoid((a) => a.filter((x) => x !== id));
          }} />
          <Question label="À éviter la prochaine fois" steps={steps} chosen={avoid} onPick={(id) => {
            setAvoid((a) => toggle(a, id));
            setAgain((a) => a.filter((x) => x !== id));
          }} />
          <PrimaryButton wide disabled={!favourite} busy={busy} onPress={send}>Donner mon bilan</PrimaryButton>
          <ThemedText type="small" themeColor="textSecondary">Vos réponses guident les prochaines soirées.</ThemedText>
        </>
      )}
      {error ? <ThemedText type="small" themeColor="danger">{error}</ThemedText> : null}
    </View>
  );
}

function Question({ label, steps, chosen, onPick }: { label: string; steps: SoireeStep[]; chosen: string[]; onPick: (id: string) => void }) {
  const theme = useTheme();
  return (
    <View style={styles.question} accessibilityLabel={label}>
      <ThemedText type="smallBold">{label}</ThemedText>
      <View style={styles.choices}>
        {steps.map((s) => {
          const on = chosen.includes(s.id);
          return (
            <Pressable key={s.id} onPress={() => onPick(s.id)} accessibilityRole="checkbox" accessibilityState={{ checked: on }}
              style={[styles.choice, { borderColor: on ? theme.accent : theme.accentHair, backgroundColor: on ? theme.backgroundSelected : 'transparent' }]}>
              <ThemedText type="small" style={{ color: on ? theme.accentInk : theme.cream }}>{s.title}</ThemedText>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { gap: Spacing.three, padding: Spacing.three + 2, borderRadius: Radius.tile, borderWidth: 1 },
  question: { gap: Spacing.two },
  choices: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.two },
  choice: { borderWidth: 1, borderRadius: Radius.pill, paddingHorizontal: Spacing.three, paddingVertical: Spacing.two },
});

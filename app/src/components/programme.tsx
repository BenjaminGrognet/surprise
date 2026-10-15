import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { PrimaryButton, TextButton, TextLink } from '@/components/buttons';
import { ThemedText } from '@/components/themed-text';
import { Fonts, Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { programmeDone, startProgramme, type Programme } from '@/lib/duo';

// « 4 semaines pour se retrouver » (docs/complicite.md, C11): before it begins, what it is and a way to begin; then the
// week the duo is in — its evening (the form set on its wishes), its question, its défi ticked by each — and the weeks
// gone or ahead as dots; once over, a way to begin again.
export function ProgrammeCard({ programme, partner, onChange }: { programme: Programme; partner: string; onChange: () => void }) {
  const theme = useTheme();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError('');
    try {
      await action();
      onChange();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }
  const week = programme.semaines.find((w) => w.semaine === programme.semaine) ?? null;
  return (
    <View testID="programme" style={[styles.card, { backgroundColor: theme.velvet, borderColor: theme.accentSoft }]}>
      <View style={styles.head}>
        <ThemedText type="eyebrow">4 semaines pour se retrouver</ThemedText>
        {week ? <ThemedText type="small" themeColor="textSecondary">{`Semaine ${week.semaine} sur 4`}</ThemedText> : null}
      </View>
      {programme.semaine === 0 ? (
        <>
          <ThemedText style={{ color: theme.creamSoft }}>
            Un mois pour sortir de la routine : chaque semaine une soirée, une question à vous poser et un défi, de plus en plus audacieux.
          </ThemedText>
          <PrimaryButton wide busy={busy} onPress={() => run(startProgramme)}>Commencer le programme</PrimaryButton>
        </>
      ) : week ? (
        <>
          <ThemedText style={[styles.title, { color: theme.cream }]}>{week.titre}</ThemedText>
          <ThemedText style={{ color: theme.creamSoft }}>{week.texte}</ThemedText>
          <TextLink href={{ pathname: '/soiree', params: { formule: 'duo', envies: week.envies.join(',') } }}>Composer la soirée de la semaine →</TextLink>
          <View style={styles.part}>
            <ThemedText type="eyebrow" style={styles.label}>La question à vous poser</ThemedText>
            <ThemedText type="clue" style={{ color: theme.cream }}>{week.question}</ThemedText>
          </View>
          <View style={styles.part}>
            <ThemedText type="eyebrow" style={styles.label}>Le défi</ThemedText>
            <ThemedText style={{ color: theme.cream }}>{week.defi}</ThemedText>
            <ThemedText type="small" themeColor="textSecondary">
              {week.fait_par_moi && week.fait_par_l_autre
                ? 'Relevé à deux.'
                : week.fait_par_moi ? `Fait de votre côté : à ${partner} maintenant.` : week.fait_par_l_autre ? `${partner} l’a relevé. À vous !` : 'Chacun le coche une fois fait.'}
            </ThemedText>
            {week.fait_par_moi ? null : <PrimaryButton wide busy={busy} onPress={() => run(() => programmeDone(week.semaine))}>Défi relevé</PrimaryButton>}
          </View>
        </>
      ) : (
        <>
          <ThemedText style={{ color: theme.creamSoft }}>Programme terminé : quatre semaines, quatre soirées. Bravo à vous deux.</ThemedText>
          <TextButton busy={busy} onPress={() => run(startProgramme)}>Recommencer le programme</TextButton>
        </>
      )}
      {programme.semaine > 0 ? (
        <View style={styles.dots} accessibilityLabel={`Semaine ${Math.min(programme.semaine, 4)} sur 4`}>
          {programme.semaines.map((w) => (
            <View key={w.semaine} style={[styles.dot, {
              backgroundColor: w.fait_par_moi && w.fait_par_l_autre ? theme.gold : w.ouverte ? theme.accent : 'transparent',
              borderColor: w.ouverte ? theme.accent : theme.line,
            }]} />
          ))}
        </View>
      ) : null}
      {error ? <ThemedText type="small" themeColor="danger">{error}</ThemedText> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { gap: Spacing.three, padding: Spacing.three + 2, borderRadius: Radius.tile, borderWidth: 1 },
  head: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', gap: Spacing.two },
  title: { fontFamily: Fonts.headingItalic, fontSize: 24, lineHeight: 30 },
  part: { gap: Spacing.one },
  label: { fontSize: 10, letterSpacing: 2.5 },
  dots: { flexDirection: 'row', gap: Spacing.two, justifyContent: 'center' },
  dot: { width: 10, height: 10, borderRadius: 5, borderWidth: 1 },
});

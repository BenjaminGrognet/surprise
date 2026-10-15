import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { PrimaryButton, TextButton } from '@/components/buttons';
import { DayField } from '@/components/day-field';
import { ThemedText } from '@/components/themed-text';
import { Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { refusal, shiftSoiree, type ComposedSoiree } from '@/lib/api';
import { longDay } from '@/lib/dates';

// The evenings composed but not kept yet — ready from an email (a date that counts), or from the form — moved to
// another day: the same evening, each step kept at its hour where it can be that day, the others drawn again.
// `told`: what the last move changed, kept by the screen (the page's new name remounts it).
export function ShiftDay({
  day, name, told, onShifted,
}: { day: string; name: string; told: string; onShifted: (moved: ComposedSoiree, told: string) => void }) {
  const theme = useTheme();
  const [open, setOpen] = useState(false);
  const [chosen, setChosen] = useState(day);
  const [busy, setBusy] = useState(false);
  const [said, setSaid] = useState('');

  async function shift() {
    setBusy(true);
    setSaid('');
    try {
      const moved = await shiftSoiree(name, chosen);
      onShifted(moved, moved.changed
        ? `Décalée au ${longDay(chosen)} : ${moved.changed} étape${moved.changed > 1 ? 's' : ''} remplacée${moved.changed > 1 ? 's' : ''}, ${moved.changed > 1 ? 'elles n’étaient' : 'elle n’était'} pas possible${moved.changed > 1 ? 's' : ''} ce jour-là.`
        : `Décalée au ${longDay(chosen)} : la même soirée, étape pour étape.`);
      setOpen(false);
    } catch (error) {
      setSaid(refusal(error) ?? 'La soirée n’a pas pu être décalée : réessayez dans un instant.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <View testID="decaler" style={[styles.box, { borderColor: theme.line, backgroundColor: theme.backgroundElement }]}>
      <View style={styles.row}>
        <ThemedText type="small" themeColor="textSecondary" style={styles.grow}>{`Prévue le ${longDay(day)}`}</ThemedText>
        <TextButton onPress={() => setOpen(!open)}>{open ? 'Annuler' : 'Décaler la date'}</TextButton>
      </View>
      {open ? (
        <>
          <DayField label="Le nouveau jour" value={chosen} onChange={setChosen} />
          <PrimaryButton wide busy={busy} disabled={!chosen || chosen === day} onPress={shift}>
            {busy ? 'On déplace votre soirée…' : 'Décaler la soirée'}
          </PrimaryButton>
          <ThemedText type="small" themeColor="textSecondary">
            On garde la même soirée ; une étape impossible ce jour-là est remplacée par une autre du même genre.
          </ThemedText>
        </>
      ) : null}
      {told && !said ? <ThemedText type="small" themeColor="accentInk">{told}</ThemedText> : null}
      {said ? <ThemedText type="small" themeColor="danger">{said}</ThemedText> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  box: { gap: Spacing.two, padding: Spacing.three, borderRadius: Radius.tile, borderWidth: 1 },
  row: { flexDirection: 'row', alignItems: 'center', gap: Spacing.two },
  grow: { flex: 1 },
});

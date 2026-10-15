import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { PrimaryButton, TextButton } from '@/components/buttons';
import { TextField } from '@/components/text-field';
import { ThemedText } from '@/components/themed-text';
import { Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import type { Duo } from '@/lib/duo';
import { addKeyDate, dayOfYear, parseDayMonth, removeKeyDate, type Genre, type KeyDate } from '@/lib/occasions';

const GENRES: { value: Genre; label: string }[] = [
  { value: 'rencontre', label: 'Notre rencontre' },
  { value: 'anniversaire', label: 'Un anniversaire' },
  { value: 'autre', label: 'Autre' },
];

// « Les dates qui comptent » (docs/complicite.md, B7): noted by either of the duo; three weeks before each — and before
// Saint-Valentin —, three intrigues composed for that day arrive by email and on the home. A birthday reminds only the
// other one.
export function KeyDates({ duo, dates, me, partner, onChange }: {
  duo: Duo; dates: KeyDate[]; me: string; partner: string; onChange: () => void;
}) {
  const theme = useTheme();
  const [adding, setAdding] = useState(false);
  const [label, setLabel] = useState('');
  const [genre, setGenre] = useState<Genre>('rencontre');
  const [when, setWhen] = useState('');
  const [whose, setWhose] = useState<'moi' | 'autre'>('autre');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function add() {
    const day = parseDayMonth(when);
    setError('');
    if (!day) return setError('Indiquez le jour et le mois, par exemple 14/02.');
    setBusy(true);
    try {
      const pour = genre === 'anniversaire' ? (whose === 'moi' ? me : duo.partner?.user_id ?? null) : null;
      await addKeyDate(duo.id, { label: label || GENRES.find((g) => g.value === genre)!.label, genre, ...day, pour });
      setAdding(false);
      setLabel('');
      setWhen('');
      onChange();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <View testID="dates-qui-comptent" style={[styles.card, { backgroundColor: theme.backgroundElement, borderColor: theme.line }]}>
      <ThemedText type="eyebrow">Les dates qui comptent</ThemedText>
      <ThemedText type="small" style={{ color: theme.creamSoft }}>
        Trois semaines avant chacune, et avant la Saint-Valentin, trois intrigues composées pour ce jour-là vous attendent.
      </ThemedText>
      {dates.map((d) => (
        <View key={d.id} style={styles.row}>
          <View style={styles.grow}>
            <ThemedText type="smallBold">{d.label}</ThemedText>
            <ThemedText type="small" themeColor="textSecondary">
              {dayOfYear(d)}{d.pour ? (d.pour === me ? ' · votre anniversaire' : ` · l’anniversaire de ${partner}`) : ''}
            </ThemedText>
          </View>
          <TextButton onPress={() => removeKeyDate(d.id).then(onChange, () => {})}>Retirer</TextButton>
        </View>
      ))}
      {adding ? (
        <View style={styles.form}>
          <View style={styles.chips}>
            {GENRES.map((g) => <Chip key={g.value} label={g.label} on={genre === g.value} onPress={() => setGenre(g.value)} />)}
          </View>
          {genre === 'anniversaire' ? (
            <View style={styles.chips}>
              <Chip label="Le mien" on={whose === 'moi'} onPress={() => setWhose('moi')} />
              <Chip label={`Celui de ${partner}`} on={whose === 'autre'} onPress={() => setWhose('autre')} />
            </View>
          ) : null}
          <TextField value={label} onChangeText={setLabel} maxLength={80} accessibilityLabel="Le nom de la date"
            placeholder="Son nom (facultatif)" placeholderTextColor={theme.creamFaint} style={[styles.field, { color: theme.cream, backgroundColor: theme.background }]} />
          <TextField value={when} onChangeText={setWhen} maxLength={5} accessibilityLabel="Le jour et le mois"
            placeholder="Jour et mois : 14/02" placeholderTextColor={theme.creamFaint} style={[styles.field, { color: theme.cream, backgroundColor: theme.background }]} />
          <PrimaryButton wide busy={busy} disabled={!when.trim()} onPress={add}>Noter cette date</PrimaryButton>
          <TextButton onPress={() => setAdding(false)}>Annuler</TextButton>
        </View>
      ) : (
        <TextButton onPress={() => setAdding(true)}>+ Ajouter une date</TextButton>
      )}
      {error ? <ThemedText type="small" themeColor="danger">{error}</ThemedText> : null}
    </View>
  );
}

function Chip({ label, on, onPress }: { label: string; on: boolean; onPress: () => void }) {
  const theme = useTheme();
  return (
    <Pressable onPress={onPress} accessibilityRole="radio" accessibilityState={{ checked: on }}
      style={[styles.chip, { borderColor: on ? theme.accent : theme.accentHair, backgroundColor: on ? theme.backgroundSelected : 'transparent' }]}>
      <ThemedText type="small" style={{ color: on ? theme.accentInk : theme.cream }}>{label}</ThemedText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: { gap: Spacing.three, padding: Spacing.three + 2, borderRadius: Radius.tile, borderWidth: 1 },
  row: { flexDirection: 'row', alignItems: 'center', gap: Spacing.two },
  grow: { flex: 1, gap: 2 },
  form: { gap: Spacing.two },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.two },
  chip: { borderWidth: 1, borderRadius: Radius.pill, paddingHorizontal: Spacing.three, paddingVertical: Spacing.two },
  field: { padding: Spacing.three, borderRadius: Radius.field, fontSize: 16 },
});

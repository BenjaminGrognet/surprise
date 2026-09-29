import { Platform, StyleSheet, TextInput, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { isoDay } from '@/lib/dates';
import { useTheme } from '@/hooks/use-theme';

// Mirrors dayField() in src/surprise/client.js. On web, a real <input type="date"> (native
// platform feature, same UX as the original site); native gets a plain ISO text field —
// ponytail: no native date picker yet, swap in @react-native-community/datetimepicker if wanted.
export function DayField({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const theme = useTheme();
  return (
    <View style={styles.field}>
      <ThemedText type="smallBold">Le jour</ThemedText>
      {Platform.OS === 'web' ? (
        <input
          type="date"
          value={value}
          min={isoDay(new Date())}
          onChange={(e: { target: { value: string } }) => onChange(e.target.value)}
          style={{ font: 'inherit', padding: 14, borderRadius: 14, border: 'none', background: theme.backgroundElement, color: theme.text, width: '100%' }}
        />
      ) : (
        <TextInput
          value={value}
          onChangeText={onChange}
          placeholder="AAAA-MM-JJ"
          style={[styles.input, { backgroundColor: theme.backgroundElement, color: theme.text }]}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  field: { gap: Spacing.one },
  input: { fontSize: 16, padding: 14, borderRadius: 14 },
});

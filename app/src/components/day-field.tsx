import { Platform, StyleSheet, TextInput, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Fonts, Spacing } from '@/constants/theme';
import { isoDay } from '@/lib/dates';
import { useTheme } from '@/hooks/use-theme';

// On web, a real <input type="date"> (native platform feature); native gets a plain ISO text field —
// ponytail: no native date picker yet, swap in @react-native-community/datetimepicker if wanted.
export function DayField({ value, onChange, label = 'Le jour' }: { value: string; onChange: (value: string) => void; label?: string }) {
  const theme = useTheme();
  return (
    <View style={styles.field}>
      <ThemedText type="smallBold">{label}</ThemedText>
      {Platform.OS === 'web' ? (
        <input
          type="date"
          value={value}
          min={isoDay(new Date())}
          onChange={(e: { target: { value: string } }) => onChange(e.target.value)}
          style={{
            fontFamily: Fonts.sans, fontSize: 16, padding: 14, borderRadius: 14, border: `1px solid ${theme.line}`,
            background: theme.backgroundElement, color: theme.text, width: '100%', boxSizing: 'border-box', colorScheme: 'dark',
          }}
        />
      ) : (
        <TextInput
          value={value}
          onChangeText={onChange}
          placeholder="AAAA-MM-JJ"
          placeholderTextColor={theme.textSecondary}
          style={[styles.input, { backgroundColor: theme.backgroundElement, color: theme.text, borderColor: theme.line }]}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  field: { gap: Spacing.two },
  input: { fontFamily: Fonts.sans, fontSize: 16, padding: 14, borderRadius: 14, borderWidth: 1 },
});

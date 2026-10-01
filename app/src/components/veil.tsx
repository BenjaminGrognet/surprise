import { StyleSheet, View } from 'react-native';

import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

// The blurred lines that stand for hidden text: nothing of it is sent to the screen.
export function Veil({ widths }: { widths: `${number}%`[] }) {
  const theme = useTheme();
  return (
    <View style={styles.veil}>
      {widths.map((w, i) => (
        <View key={i} style={[styles.line, { width: w, backgroundColor: theme.backgroundSelected }]} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  veil: { gap: Spacing.two, paddingVertical: Spacing.one },
  line: { height: 10, borderRadius: 5 },
});

import { useEffect, useState } from 'react';
import { Animated, Easing, Modal, Platform, StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

// A gold arc turning on a faint ring: "wait a moment", next to a link that was just pressed.
export function Spinner({ size = 14 }: { size?: number }) {
  const theme = useTheme();
  const [turn] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const loop = Animated.loop(Animated.timing(turn, { toValue: 1, duration: 900, easing: Easing.linear, useNativeDriver: Platform.OS !== 'web' }));
    loop.start();
    return () => loop.stop();
  }, [turn]);
  const rotate = turn.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] });
  return (
    <Animated.View
      accessibilityLabel="Chargement"
      style={{
        width: size, height: size, borderRadius: size / 2, borderWidth: Math.max(2, size / 7),
        borderColor: theme.accentFaint, borderTopColor: theme.accent, transform: [{ rotate }],
      }}
    />
  );
}

// A step or route being redrawn: its card dims while the new one is sought.
export const busyStyle = (busy: boolean) => (busy ? { opacity: 0.45 } : null);

// The long wait of a composition: the screen dims, a card turns and tells, one line after the other, what is happening.
export function Waiting({ title, lines }: { title: string; lines: string[] }) {
  const theme = useTheme();
  const [i, setI] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setI((n) => (n + 1) % lines.length), 3200);
    return () => clearInterval(timer);
  }, [lines.length]);
  return (
    <Modal transparent animationType="fade" visible statusBarTranslucent>
      <View style={styles.backdrop}>
        <View style={[styles.card, { backgroundColor: theme.backgroundElement, borderColor: theme.accentSoft }]}>
          <Spinner size={34} />
          <ThemedText type="subtitle" style={styles.center}>{title}</ThemedText>
          <ThemedText type="clue" themeColor="textSecondary" style={styles.center}>{lines[i]}</ThemedText>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: Spacing.four, backgroundColor: 'rgba(5, 15, 14, 0.78)' },
  card: { width: '100%', maxWidth: 360, alignItems: 'center', gap: Spacing.three, padding: Spacing.five, borderRadius: 24, borderWidth: 1 },
  center: { textAlign: 'center' },
});

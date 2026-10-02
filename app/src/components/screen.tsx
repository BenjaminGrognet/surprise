import type { ReactNode } from 'react';
import { ScrollView, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { TAB_BAR_SPACE, useTabBar } from '@/components/tab-bar';
import { ThemedView } from '@/components/themed-view';
import { MaxContentWidth, Spacing } from '@/constants/theme';

// A screen's frame: the night background, one centred column that scrolls, no bar above — each page opens on its own
// card (PageCard) —, and room at the foot for the floating tab bar.
export function Screen({ children, gap = Spacing.three }: { children: ReactNode; gap?: number }) {
  const tabBar = useTabBar();
  return (
    <ThemedView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <SafeAreaView style={[styles.column, { gap }, tabBar && { paddingBottom: TAB_BAR_SPACE }]}>{children}</SafeAreaView>
      </ScrollView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  scroll: { flexGrow: 1, alignItems: 'center' },
  column: { width: '100%', maxWidth: MaxContentWidth, paddingHorizontal: Spacing.four, paddingTop: Spacing.four, paddingBottom: Spacing.three },
});

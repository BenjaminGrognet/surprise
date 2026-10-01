import type { ReactNode } from 'react';
import { ScrollView, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { BrandHeader } from '@/components/brand-header';
import { ThemedView } from '@/components/themed-view';
import { MaxContentWidth, Spacing } from '@/constants/theme';

// A screen's frame: the night background, one centred column that scrolls, the SecretDate header on top.
export function Screen({ children, gap = Spacing.three }: { children: ReactNode; gap?: number }) {
  return (
    <ThemedView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <SafeAreaView style={[styles.column, { gap }]}>
          <BrandHeader />
          {children}
        </SafeAreaView>
      </ScrollView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  scroll: { flexGrow: 1, alignItems: 'center' },
  column: { width: '100%', maxWidth: MaxContentWidth, paddingHorizontal: Spacing.four, paddingTop: Spacing.two, paddingBottom: Spacing.six },
});

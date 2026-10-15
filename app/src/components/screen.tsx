import { type ReactNode, useRef } from 'react';
import { type NativeScrollEvent, type NativeSyntheticEvent, ScrollView, StyleSheet, type View } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';

import { TAB_BAR_SPACE, useTabBar } from '@/components/tab-bar';
import { ThemedView } from '@/components/themed-view';
import { MaxContentWidth, Spacing } from '@/constants/theme';

// A screen's frame: the night background, one centred column that scrolls, no bar above — each page opens on its own
// card (PageCard) —, and room at the foot for the floating tab bar. `scroller`: to bring a part of it into view
// (useBringIntoView).
export function Screen({ children, gap = Spacing.three, scroller }: { children: ReactNode; gap?: number; scroller?: Scroller }) {
  const tabBar = useTabBar();
  return (
    <ThemedView style={styles.container}>
      <ScrollView ref={scroller?.scrollRef} onScroll={scroller?.onScroll} scrollEventThrottle={64} contentContainerStyle={styles.scroll}>
        <SafeAreaView style={[styles.column, { gap }, tabBar && { paddingBottom: TAB_BAR_SPACE }]}>{children}</SafeAreaView>
      </ScrollView>
    </ThemedView>
  );
}

type Scroller = ReturnType<typeof useBringIntoView>;

// Brings a part of a Screen into view, its top just under the window's (and the phone's notch). Measured when asked,
// not when laid out: a part above it may have grown or gone since (the web only says when a view's size changes).
export function useBringIntoView() {
  const scrollRef = useRef<ScrollView>(null);
  const offset = useRef(0);
  const insets = useSafeAreaInsets();
  const onScroll = (event: NativeSyntheticEvent<NativeScrollEvent>) => {
    offset.current = event.nativeEvent.contentOffset.y;
  };
  const bring = (part: View | null) =>
    part?.measureInWindow((_x, y) => {
      scrollRef.current?.scrollTo({ y: Math.max(0, offset.current + y - insets.top - Spacing.three), animated: true });
    });
  return { scrollRef, onScroll, bring };
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  scroll: { flexGrow: 1, alignItems: 'center' },
  column: { width: '100%', maxWidth: MaxContentWidth, paddingHorizontal: Spacing.four, paddingTop: Spacing.four, paddingBottom: Spacing.three },
});

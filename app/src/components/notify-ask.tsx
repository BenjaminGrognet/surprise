import { useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { GhostButton } from '@/components/buttons';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { askNotify, notifyState, type NotifyState } from '@/lib/notifications';

// The phone's notifications asked for where they make sense, once: the passager's week on their evening, the
// instigateur's reminders on theirs. Nothing once answered, nor on the web.
export function NotifyAsk({ text }: { text: string }) {
  const [state, setState] = useState<NotifyState>('unsupported');
  useEffect(() => {
    notifyState().then(setState).catch(() => {});
  }, []);
  if (state !== 'ask') return null;
  return (
    <View style={styles.block}>
      <ThemedText type="small" themeColor="textSecondary">{text}</ThemedText>
      <GhostButton onPress={() => askNotify().then(setState)}>Activer les notifications</GhostButton>
    </View>
  );
}

const styles = StyleSheet.create({
  block: { gap: Spacing.three },
});

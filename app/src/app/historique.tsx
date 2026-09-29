import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { Linking, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { PrimaryLink, TextLink } from '@/components/buttons';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { MaxContentWidth, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { currentUser, eveningsHistory, type EveningHistoryRow } from '@/lib/account';
import { API_URL } from '@/lib/api';
import { supabaseConfigured } from '@/lib/supabase';

const frDay = (iso: string) => new Date(`${iso}T12:00`).toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });

type State = 'loading' | 'anonymous' | 'empty' | 'error' | EveningHistoryRow[];

export default function HistoriqueScreen() {
  const [state, setState] = useState<State>(supabaseConfigured ? 'loading' : 'error');

  useEffect(() => {
    if (!supabaseConfigured) return;
    (async () => {
      const user = await currentUser();
      if (!user) return setState('anonymous');
      try {
        const rows = await eveningsHistory();
        setState(rows.length ? rows : 'empty');
      } catch {
        setState('error');
      }
    })();
  }, []);

  return (
    <Screen>
      <ThemedText type="title">Mon historique</ThemedText>
      {state === 'loading' && <ThemedText themeColor="textSecondary">On retrouve vos soirées…</ThemedText>}
      {state === 'error' && !supabaseConfigured && (
        <ThemedView type="backgroundElement" style={styles.notice}>
          <ThemedText themeColor="textSecondary">Les comptes ne sont pas encore configurés sur ce serveur.</ThemedText>
        </ThemedView>
      )}
      {state === 'error' && supabaseConfigured && <ThemedText style={styles.error}>L&apos;historique n&apos;a pas pu être chargé.</ThemedText>}
      {state === 'anonymous' && (
        <ThemedView type="backgroundElement" style={styles.notice}>
          <ThemedText themeColor="textSecondary">Connectez-vous pour retrouver les soirées que vous avez choisies. </ThemedText>
          <TextLink href="/compte">Se connecter →</TextLink>
        </ThemedView>
      )}
      {state === 'empty' && (
        <>
          <ThemedText themeColor="textSecondary">
            Vous n&apos;avez pas encore choisi de soirée : quand vous composez une soirée, gardez celle que vous avez vraiment faite.
          </ThemedText>
          <PrimaryLink href="/soiree">Composer une soirée</PrimaryLink>
        </>
      )}
      {Array.isArray(state) && (
        <>
          <ThemedText themeColor="textSecondary">
            {state.length} soirée{state.length > 1 ? 's' : ''} vécue{state.length > 1 ? 's' : ''}.
          </ThemedText>
          <View style={styles.list}>
            {state.map((row, i) => (
              <HistoryCard key={i} row={row} />
            ))}
          </View>
        </>
      )}
    </Screen>
  );
}

function HistoryCard({ row }: { row: EveningHistoryRow }) {
  const theme = useTheme();
  return (
    <Pressable
      onPress={() => Linking.openURL(`${API_URL}/parcours/${row.page_name}.html#parcours-${row.route_index + 1}`)}
      style={[styles.card, { backgroundColor: theme.backgroundElement }]}>
      <ThemedText type="small" themeColor="textSecondary">{row.day ? frDay(row.day) : 'Date libre'}</ThemedText>
      <ThemedText type="subtitle" style={styles.cardTitle}>{row.title}</ThemedText>
      <ThemedText themeColor="textSecondary">{row.pitch}</ThemedText>
      <View style={styles.tags}>
        {(row.vibes ?? []).map((v) => (
          <ThemedText key={v} type="small" style={[styles.tag, { backgroundColor: theme.backgroundSelected }]}>{v}</ThemedText>
        ))}
      </View>
    </Pressable>
  );
}

function Screen({ children }: { children: ReactNode }) {
  return (
    <ThemedView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <SafeAreaView style={styles.safeArea}>{children}</SafeAreaView>
      </ScrollView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  scroll: { flexGrow: 1, alignItems: 'center' },
  safeArea: { width: '100%', maxWidth: MaxContentWidth, paddingHorizontal: Spacing.four, paddingVertical: Spacing.three, gap: Spacing.three },
  notice: { padding: Spacing.three, borderRadius: 14 },
  error: { color: '#ff5c72' },
  list: { gap: Spacing.two + 2 },
  card: { padding: Spacing.three + 2, borderRadius: 20, gap: 4 },
  cardTitle: { fontSize: 19 },
  tags: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 4 },
  tag: { borderRadius: 999, paddingVertical: 4, paddingHorizontal: 12, overflow: 'hidden' },
});

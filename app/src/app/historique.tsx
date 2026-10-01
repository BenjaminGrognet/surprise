import { useEffect, useState } from 'react';
import { router } from 'expo-router';
import { Pressable, StyleSheet, View } from 'react-native';

import { PrimaryLink, TextLink } from '@/components/buttons';
import { Screen } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useCouple } from '@/hooks/use-couple';
import { useTheme } from '@/hooks/use-theme';
import { currentUser, eveningsHistory, type EveningHistoryRow } from '@/lib/account';
import { isoDay } from '@/lib/dates';
import { supabaseConfigured } from '@/lib/supabase';

const frDay = (iso: string) => new Date(`${iso}T12:00`).toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });

type State = 'loading' | 'anonymous' | 'empty' | 'error' | EveningHistoryRow[];

export default function HistoriqueScreen() {
  const theme = useTheme();
  const { role } = useCouple();
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

  const notice = [styles.notice, { backgroundColor: theme.backgroundElement, borderColor: theme.line }];
  return (
    <Screen>
      <ThemedText type="eyebrow">Le carnet</ThemedText>
      <ThemedText type="title">Nos intrigues</ThemedText>
      {state === 'loading' && <ThemedText themeColor="textSecondary">On retrouve vos soirées…</ThemedText>}
      {state === 'error' && !supabaseConfigured && (
        <View style={notice}>
          <ThemedText themeColor="textSecondary">Les comptes ne sont pas encore configurés sur ce serveur.</ThemedText>
        </View>
      )}
      {state === 'error' && supabaseConfigured && <ThemedText themeColor="danger">L&apos;historique n&apos;a pas pu être chargé.</ThemedText>}
      {state === 'anonymous' && (
        <View style={notice}>
          <ThemedText themeColor="textSecondary">Connectez-vous pour retrouver les intrigues que vous avez gardées. </ThemedText>
          <TextLink href="/compte">Se connecter →</TextLink>
        </View>
      )}
      {state === 'empty' && (
        <>
          <ThemedText themeColor="textSecondary">
            {role === 'passager'
              ? "Pas encore d'intrigue : votre instigateur trame la première."
              : "Pas encore d'intrigue gardée : lancez-en une, et gardez la soirée que vous allez vraiment vivre."}
          </ThemedText>
          {role === 'instigateur' ? <PrimaryLink href="/soiree">Lancer une intrigue</PrimaryLink> : null}
        </>
      )}
      {Array.isArray(state) && (
        <>
          <ThemedText themeColor="textSecondary">
            {state.length} intrigue{state.length > 1 ? 's' : ''} gardée{state.length > 1 ? 's' : ''}.
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

// The instigateur reopens a past evening's routes, one still to come on its roadmap; the passager opens the
// revelation, whose steps lift as their hour comes.
function HistoryCard({ row }: { row: EveningHistoryRow }) {
  const theme = useTheme();
  const { role } = useCouple();
  const ahead = !!row.day && row.day >= isoDay(new Date());
  const sealed = ahead && role === 'passager';
  const params = { soiree: row.page_name, route: String(row.route_index) };
  return (
    <Pressable
      onPress={() => router.push({ pathname: ahead || role === 'passager' ? '/revelation' : '/soiree', params })}
      style={[styles.card, { backgroundColor: theme.backgroundElement, borderColor: ahead ? theme.accentSoft : theme.line }]}>
      <ThemedText type="eyebrow" themeColor={ahead ? 'accentInk' : 'textSecondary'}>
        {ahead ? 'À venir · ' : ''}{row.day ? frDay(row.day) : 'Date libre'}
      </ThemedText>
      {/* To the passager, an evening to come keeps its secret here too: its title would give it away. */}
      <ThemedText type="subtitle">{sealed ? 'Une intrigue scellée' : row.title}</ThemedText>
      {sealed ? null : <ThemedText themeColor="textSecondary">{row.pitch}</ThemedText>}
      <View style={styles.tags}>
        {(sealed ? [] : row.vibes ?? []).map((v) => (
          <ThemedText key={v} type="small" themeColor="accentInk" style={[styles.tag, { borderColor: theme.accentSoft }]}>{v}</ThemedText>
        ))}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  notice: { padding: Spacing.three, borderRadius: 16, borderWidth: 1 },
  list: { gap: Spacing.three },
  card: { padding: Spacing.four, borderRadius: 22, borderWidth: 1, gap: Spacing.two },
  tags: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 4 },
  tag: { borderRadius: 999, borderWidth: 1, paddingVertical: 4, paddingHorizontal: 12, overflow: 'hidden' },
});

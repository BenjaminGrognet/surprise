import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { PrimaryLink, TextButton, TextLink } from '@/components/buttons';
import { Countdown, IntrigueCard } from '@/components/intrigue-card';
import { Screen } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useNow } from '@/hooks/use-now';
import { useTheme } from '@/hooks/use-theme';
import { eveningsHistory, upcomingEvening, type EveningHistoryRow } from '@/lib/account';
import { getSoireeState, type Profile, type SoireeRoute } from '@/lib/api';
import { dayHint } from '@/lib/clues';
import { complicity, type Complicity } from '@/lib/complicity';
import { isoDay } from '@/lib/dates';
import { forgetProfile, rememberedProfile } from '@/lib/local-store';
import { supabaseConfigured } from '@/lib/supabase';

// "Le Tableau des Complots": no catalogue, one sealed card — the next mystery evening and its
// countdown —, one button to plot a new one, and the couple's complicity gauge.
export default function AccueilScreen() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [upcoming, setUpcoming] = useState<{ row: EveningHistoryRow; route: SoireeRoute | null } | null>(null);
  const [gauge, setGauge] = useState<Complicity | null>(null);

  useEffect(() => {
    (async () => {
      const remembered = await rememberedProfile();
      setProfile(remembered?.profile ?? null);
      if (supabaseConfigured) {
        const today = isoDay(new Date());
        const [row, history] = await Promise.all([
          upcomingEvening(today).catch(() => null),
          eveningsHistory().catch(() => []),
        ]);
        setGauge(complicity(history, today));
        if (row) {
          const state = await getSoireeState(row.page_name).catch(() => null);
          setUpcoming({ row, route: state?.routes.find((r) => r.index === row.route_index) ?? null });
        }
      }
      setLoaded(true);
    })();
  }, []);

  return (
    <Screen gap={Spacing.four}>
      {loaded ? (upcoming ? <NextIntrigue {...upcoming} /> : <NoIntrigue />) : <IntrigueCard><View style={styles.placeholder} /></IntrigueCard>}

      <View style={styles.actions}>
        <PrimaryLink wide href="/soiree">Lancer une nouvelle intrigue</PrimaryLink>
        {loaded && !profile ? <TextLink href="/profil">D&apos;abord, faire notre profil (2 minutes) →</TextLink> : null}
      </View>

      {gauge ? <Gauge gauge={gauge} /> : null}

      <View style={styles.links}>
        {profile ? <TextLink href="/profil">{`Notre profil · ${profile.persona.name}`}</TextLink> : null}
        <TextLink href="/historique">Nos intrigues passées</TextLink>
        {profile ? <TextButton onPress={() => forgetProfile().then(() => setProfile(null))}>Oublier ce profil</TextButton> : null}
      </View>
    </Screen>
  );
}

function NextIntrigue({ row, route }: { row: EveningHistoryRow; route: SoireeRoute | null }) {
  const now = useNow();
  const start = route ? Date.parse(route.start) : null;
  const under = start != null && route && now >= start && now < Date.parse(route.end);
  const open = () => router.push({ pathname: '/revelation', params: { soiree: row.page_name, route: String(row.route_index) } });
  return (
    <IntrigueCard onPress={open}>
      <ThemedText type="eyebrow" style={styles.center}>{under ? "L'intrigue a commencé" : 'Votre prochaine intrigue'}</ThemedText>
      <ThemedText type="title" style={styles.center}>L&apos;Inattendu vous attend…</ThemedText>
      {start != null && !under ? <Countdown to={start} now={now} /> : null}
      {route ? (
        <ThemedText type="clue" themeColor="textSecondary" style={styles.center}>
          <ThemedText type="clue" themeColor="accentInk">✦ Indice du jour : </ThemedText>
          {dayHint(route, now)}
        </ThemedText>
      ) : null}
      <ThemedText type="small" themeColor="textSecondary" style={styles.center}>Touchez la carte pour la révélation</ThemedText>
    </IntrigueCard>
  );
}

function NoIntrigue() {
  return (
    <IntrigueCard>
      <ThemedText type="eyebrow" style={styles.center}>Aucune intrigue en cours</ThemedText>
      <ThemedText type="title" style={styles.center}>Le prochain secret reste à écrire…</ThemedText>
      <ThemedText themeColor="textSecondary" style={styles.center}>
        Dites-nous votre humeur : on trame trois soirées dans Paris, vous en gardez une, et l&apos;un de vous deux garde le secret
        jusqu&apos;au jour J.
      </ThemedText>
    </IntrigueCard>
  );
}

function Gauge({ gauge }: { gauge: Complicity }) {
  const theme = useTheme();
  return (
    <View style={styles.gauge}>
      <ThemedText type="small" themeColor="textSecondary" style={styles.center}>
        Niveau de complicité : <ThemedText type="smallBold" themeColor="accentInk">{gauge.name}</ThemedText>
      </ThemedText>
      <View style={[styles.track, { backgroundColor: theme.line }]}>
        <View style={[styles.fill, { width: `${Math.max(gauge.progress, 0.03) * 100}%`, backgroundColor: theme.accent }]} />
      </View>
      <ThemedText type="small" themeColor="textSecondary" style={[styles.center, styles.caption]}>
        {gauge.lived} soirée{gauge.lived > 1 ? 's' : ''} vécue{gauge.lived > 1 ? 's' : ''} à deux
        {gauge.next ? ` · encore ${gauge.next.left} pour « ${gauge.next.name} »` : ''}
      </ThemedText>
    </View>
  );
}

const styles = StyleSheet.create({
  center: { textAlign: 'center' },
  placeholder: { height: 280 },
  actions: { gap: Spacing.two, alignItems: 'center' },
  gauge: { gap: Spacing.two },
  track: { height: 3, borderRadius: 2, overflow: 'hidden' },
  fill: { height: '100%', borderRadius: 2 },
  caption: { fontSize: 12 },
  links: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', columnGap: Spacing.four },
});

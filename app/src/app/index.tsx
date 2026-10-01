import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { PrimaryLink, TextButton, TextLink } from '@/components/buttons';
import { Countdown, IntrigueCard } from '@/components/intrigue-card';
import { Screen } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useCouple } from '@/hooks/use-couple';
import { useNow } from '@/hooks/use-now';
import { useTheme } from '@/hooks/use-theme';
import { accountProfile, eveningsHistory, upcomingEvening, type EveningHistoryRow } from '@/lib/account';
import { getSoireeState, type Profile, type SoireeRoute } from '@/lib/api';
import { dayHint } from '@/lib/clues';
import { complicity, type Complicity } from '@/lib/complicity';
import { isoDay } from '@/lib/dates';
import { forgetProfile, rememberedProfile } from '@/lib/local-store';
import { curtainFalls } from '@/lib/souvenirs';
import { supabaseConfigured } from '@/lib/supabase';

// "Le Tableau des Complots": no catalogue, one sealed card — the next mystery evening and its
// countdown —, one button to plot a new one, and the couple's complicity gauge. The passager gets the
// card and the gauge only: the instigateur makes the profile and orders the evenings.
export default function AccueilScreen() {
  const { role } = useCouple();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [upcoming, setUpcoming] = useState<{ row: EveningHistoryRow; route: SoireeRoute | null } | null>(null);
  const [gauge, setGauge] = useState<Complicity | null>(null);
  const [toSeal, setToSeal] = useState<EveningHistoryRow | null>(null);

  useEffect(() => {
    (async () => {
      const remembered = await rememberedProfile();
      let known = remembered?.profile ?? null;
      if (!known && supabaseConfigured) {
        known = (await accountProfile().catch(() => null))?.profile ?? null;
      }
      setProfile(known);
      if (supabaseConfigured) {
        const today = isoDay(new Date());
        const [row, history] = await Promise.all([
          upcomingEvening(today).catch(() => null),
          eveningsHistory().catch(() => []),
        ]);
        setGauge(complicity(history, today));
        // An evening of the past week whose book the account hasn't sealed yet.
        const weekAgo = new Date();
        weekAgo.setDate(weekAgo.getDate() - 7);
        setToSeal(history.find((r) => !!r.day && r.day < today && r.day >= isoDay(weekAgo) && !r.souvenirs?.length) ?? null);
        if (row) {
          const state = await getSoireeState(row.page_name).catch(() => null);
          setUpcoming({ row, route: state?.routes.find((r) => r.index === row.route_index) ?? null });
        }
      }
      setLoaded(true);
    })();
  }, []);

  const profileLink = profile
    ? `Notre profil : ${profile.persona.name} · le refaire →`
    : "D'abord, faire notre profil (2 minutes) →";
  return (
    <Screen gap={Spacing.three}>
      {toSeal ? <BookCall row={toSeal} /> : null}
      {loaded ? (
        upcoming ? <NextIntrigue {...upcoming} /> : role === 'passager' ? <AwaitingIntrigue /> : <NoIntrigue />
      ) : (
        <IntrigueCard><View style={styles.placeholder} /></IntrigueCard>
      )}

      {role === 'instigateur' ? (
        <View style={styles.actions}>
          <PrimaryLink wide href="/soiree">Lancer une nouvelle intrigue</PrimaryLink>
          {loaded ? <TextLink href="/profil">{profileLink}</TextLink> : null}
          {upcoming && !upcoming.row.passager ? (
            <TextLink href={{ pathname: '/revelation', params: { soiree: upcoming.row.page_name, route: String(upcoming.row.route_index) } }}>
              Inviter votre passager à cette soirée →
            </TextLink>
          ) : null}
        </View>
      ) : null}

      {gauge ? <Gauge gauge={gauge} /> : null}

      <View style={styles.links}>
        <TextLink href="/historique">Mes soirées</TextLink>
        {role === 'instigateur' && profile ? (
          <TextButton onPress={() => forgetProfile().then(() => setProfile(null))}>Oublier ce profil</TextButton>
        ) : null}
      </View>
    </Screen>
  );
}

function NextIntrigue({ row, route }: { row: EveningHistoryRow; route: SoireeRoute | null }) {
  const now = useNow();
  // Its last step begun, the evening calls for its book.
  if (route && curtainFalls(route, now) && !row.souvenirs?.length) return <BookCall row={row} />;
  const start = route ? Date.parse(route.start) : null;
  const under = start != null && route && now >= start && now < Date.parse(route.end);
  const open = () => router.push({ pathname: '/revelation', params: { soiree: row.page_name, route: String(row.route_index) } });
  return (
    <IntrigueCard onPress={open}>
      <ThemedText type="eyebrow" style={styles.center}>{under ? "L'intrigue a commencé" : 'Votre prochaine intrigue'}</ThemedText>
      <ThemedText type="title" style={styles.center}>{row.secret_title ?? route?.secret_title ?? 'L’Inattendu vous attend…'}</ThemedText>
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

// Le Livre des Secrets, at the end of the evening or the days after: a photo, a note, sealed.
function BookCall({ row }: { row: EveningHistoryRow }) {
  const open = () => router.push({ pathname: '/livre', params: { soiree: row.page_name, route: String(row.route_index) } });
  return (
    <IntrigueCard onPress={open}>
      <ThemedText type="eyebrow" style={styles.center}>L&apos;intrigue s&apos;achève</ThemedText>
      <ThemedText type="title" style={styles.center}>Le Livre des Secrets</ThemedText>
      <ThemedText themeColor="textSecondary" style={styles.center}>
        Le rideau tombe sur « {row.secret_title ?? row.title} ». Déposez une photo et un mot avant qu&apos;ils ne s&apos;évaporent.
      </ThemedText>
      <ThemedText type="small" themeColor="accentInk" style={styles.center}>Ouvrir le grimoire →</ThemedText>
    </IntrigueCard>
  );
}

function NoIntrigue() {
  return (
    <IntrigueCard>
      <ThemedText type="eyebrow" style={styles.center}>Aucune intrigue en cours</ThemedText>
      <ThemedText type="title" style={styles.center}>Le prochain secret reste à écrire…</ThemedText>
      <ThemedText themeColor="textSecondary" style={styles.center}>
        Dites-nous votre humeur : on trame trois soirées dans Paris, vous en gardez une, et vous seul en gardez le secret ; votre
        passager ne reçoit que des indices jusqu&apos;au jour J.
      </ThemedText>
    </IntrigueCard>
  );
}

// The passager, before any evening is kept: nothing to see yet, and that's the point.
function AwaitingIntrigue() {
  return (
    <IntrigueCard>
      <ThemedText type="eyebrow" style={styles.center}>Passager</ThemedText>
      <ThemedText type="title" style={styles.center}>Quelque chose se trame…</ThemedText>
      <ThemedText themeColor="textSecondary" style={styles.center}>
        Dès que votre instigateur aura scellé une soirée, son compte à rebours et ses indices apparaîtront ici.
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
  placeholder: { height: 180 },
  actions: { gap: Spacing.one, alignItems: 'center' },
  gauge: { gap: Spacing.one },
  track: { height: 3, borderRadius: 2, overflow: 'hidden' },
  fill: { height: '100%', borderRadius: 2 },
  caption: { fontSize: 12 },
  links: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', columnGap: Spacing.four },
});

import { useEffect, useState } from 'react';
import { Image, ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { AccountNav } from '@/components/account-nav';
import { PrimaryLink, TextButton, TextLink } from '@/components/buttons';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { MaxContentWidth, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { API_URL, getSoireeState, type Profile, type SoireeRoute } from '@/lib/api';
import { upcomingEvening, type EveningHistoryRow } from '@/lib/account';
import { formatTime, isoDay, longDay } from '@/lib/dates';
import { forgetProfile, rememberedProfile } from '@/lib/local-store';
import { supabaseConfigured } from '@/lib/supabase';

const BANNER = 'https://images.unsplash.com/photo-1504730513966-dfcd6e53fdc8?auto=format&fit=crop&w=1600&q=60';

const STEPS = [
  { emoji: '💬', title: 'Votre profil, une fois', text: "Quelques questions sur vous deux : ce qui vous plaît, ce que vous ne voulez jamais, votre budget." },
  { emoji: '✨', title: 'Une envie par soirée', text: 'Ambiance, date, heure, budget : configurez votre soirée idéale en quelques clics.' },
  { emoji: '🌙', title: 'Trois parcours au choix', text: "Horaires, trajets, prix et liens de réservation ; une étape ne vous plaît pas, on la retire au sort. Et si vous découchez, la nuit est prévue." },
];

export default function AccueilScreen() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [upcoming, setUpcoming] = useState<EveningHistoryRow | null>(null);

  useEffect(() => {
    (async () => {
      const remembered = await rememberedProfile();
      setProfile(remembered?.profile ?? null);
      setLoaded(true);
      if (supabaseConfigured) setUpcoming(await upcomingEvening(isoDay(new Date())).catch(() => null));
    })();
  }, []);

  return (
    <ThemedView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <SafeAreaView style={styles.safeArea}>
          <AccountNav />
          <View style={styles.badge}>
            <ThemedText type="smallBold" style={styles.badgeText}>Soirée à deux</ThemedText>
          </View>
          {/* The upcoming evening's photos stand for the banner; the pitch is for couples new here. */}
          {upcoming ? <Upcoming row={upcoming} /> : <Image source={{ uri: BANNER }} style={styles.banner} />}
          {loaded && !profile && (
            <>
              <ThemedText type="title">Des soirées uniques à deux dans Paris.</ThemedText>
              <ThemedText themeColor="textSecondary" style={styles.lead}>
                Dites-nous qui vous êtes, puis ce qui vous fait envie ce soir-là : on compose trois soirées complètes.
              </ThemedText>
            </>
          )}

          {loaded && <Start profile={profile} onForget={() => forgetProfile().then(() => setProfile(null))} />}

          {!profile && (
            <>
              <View style={styles.progressTrack}>
                <View style={styles.progressBar} />
              </View>
              <ThemedText type="small" themeColor="textSecondary">3 étapes, à votre rythme</ThemedText>

              <ThemedView style={styles.steps}>
                {STEPS.map((s) => (
                  <ThemedView key={s.title} style={styles.step} type="backgroundElement">
                    <ThemedText style={styles.stepEmoji}>{s.emoji}</ThemedText>
                    <ThemedView style={styles.stepBody} type="backgroundElement">
                      <ThemedText type="smallBold">{s.title}</ThemedText>
                      <ThemedText type="small" themeColor="textSecondary">{s.text}</ThemedText>
                    </ThemedView>
                  </ThemedView>
                ))}
              </ThemedView>
            </>
          )}
        </SafeAreaView>
      </ScrollView>
    </ThemedView>
  );
}

// The evening the couple chose, until its day is over: its steps' photos, when and what.
function Upcoming({ row }: { row: EveningHistoryRow }) {
  const theme = useTheme();
  const [route, setRoute] = useState<SoireeRoute | null>(null);
  useEffect(() => {
    getSoireeState(row.page_name)
      .then((s) => setRoute(s.routes.find((r) => r.index === row.route_index) ?? null))
      .catch(() => null);
  }, [row.page_name, row.route_index]);
  const photos = (route?.steps ?? []).map((s) => s.image_url).filter((u): u is string => !!u).slice(0, 3);
  return (
    <View style={[styles.upcoming, { borderColor: theme.accent }]}>
      {photos.length ? (
        <View style={styles.photos}>
          {photos.map((u) => (
            <Image key={u} source={{ uri: u.startsWith('/') ? API_URL + u : u }} style={styles.photo} />
          ))}
        </View>
      ) : null}
      <View style={styles.upcomingBody}>
        <ThemedText type="smallBold" style={{ color: theme.accentInk }}>
          ✨ Notre soirée à venir · {row.day ? longDay(row.day) : ''}{route ? ` · ${formatTime(route.start)} → ${formatTime(route.end)}` : ''}
        </ThemedText>
        <ThemedText type="subtitle">{row.title}</ThemedText>
        {route ? (
          <ThemedText type="small" themeColor="textSecondary" numberOfLines={3}>
            {[...route.steps, ...(route.night ? [route.night] : [])].map((s) => `${formatTime(s.start)} ${s.title}`).join(' · ')}
          </ThemedText>
        ) : null}
        <PrimaryLink href={{ pathname: '/soiree', params: { soiree: row.page_name, route: String(row.route_index) } }}>
          Voir notre soirée
        </PrimaryLink>
      </View>
    </View>
  );
}

function Start({ profile: p, onForget }: { profile: Profile | null; onForget: () => void }) {
  if (!p) {
    return (
      <ThemedView style={styles.actions}>
        <PrimaryLink href="/profil">Faire notre profil</PrimaryLink>
        <TextLink href="/soiree">Une soirée tout de suite, sans profil →</TextLink>
      </ThemedView>
    );
  }
  return (
    <ThemedView style={styles.persona} type="backgroundElement">
      <ThemedText type="small" themeColor="textSecondary">
        {p.names ? `${p.names} · ` : ''}<ThemedText type="smallBold">{p.persona.name}</ThemedText>
      </ThemedText>
      <PrimaryLink href="/soiree">Préparer une soirée</PrimaryLink>
      <View style={styles.links}>
        <TextLink href="/profil">Notre profil</TextLink>
        <TextLink href={{ pathname: '/profil', params: { new: '1' } }}>Refaire le quiz</TextLink>
        <TextButton onPress={onForget}>Oublier ce profil</TextButton>
      </View>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  scroll: { flexGrow: 1, alignItems: 'center' },
  safeArea: { width: '100%', maxWidth: MaxContentWidth, paddingHorizontal: Spacing.four, gap: Spacing.three, paddingBottom: Spacing.six },
  badge: { alignSelf: 'flex-start', paddingVertical: 6, paddingHorizontal: 14, borderRadius: 999, backgroundColor: '#caa15a' },
  badgeText: { color: '#ffffff', letterSpacing: 0.5 },
  banner: { width: '100%', height: 200, borderRadius: Spacing.three },
  lead: { fontSize: 17, lineHeight: 24 },
  actions: { gap: Spacing.two, alignItems: 'flex-start' },
  upcoming: {
    backgroundColor: '#ffffff', borderWidth: 1.5, borderRadius: Spacing.three, overflow: 'hidden',
    shadowColor: '#caa15a', shadowOffset: { width: 0, height: 8 }, shadowOpacity: 0.25, shadowRadius: 18, elevation: 6,
  },
  photos: { flexDirection: 'row', gap: 2, height: 150 },
  photo: { flex: 1, height: '100%' },
  upcomingBody: { gap: Spacing.two, padding: Spacing.three },
  links: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.three },
  persona: { gap: Spacing.two, padding: Spacing.three, borderRadius: Spacing.three },
  progressTrack: { height: 6, borderRadius: 999, backgroundColor: '#efe0cf', overflow: 'hidden' },
  progressBar: { height: '100%', width: '33%', borderRadius: 999, backgroundColor: '#caa15a' },
  steps: { gap: Spacing.two, marginTop: Spacing.three },
  step: { flexDirection: 'row', gap: Spacing.two, padding: Spacing.three, borderRadius: Spacing.three },
  stepEmoji: { fontSize: 24 },
  stepBody: { flex: 1, gap: 2 },
});

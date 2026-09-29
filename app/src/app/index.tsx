import { useEffect, useState } from 'react';
import { Image, ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { AccountNav } from '@/components/account-nav';
import { PrimaryLink, TextLink } from '@/components/buttons';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Fonts, MaxContentWidth, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { getProfile, type SavedProfile } from '@/lib/api';
import { rememberedProfile } from '@/lib/local-store';

const BANNER = 'https://images.unsplash.com/photo-1499856871958-5b9627545d1a?auto=format&fit=crop&w=1600&q=60';

const STEPS = [
  { emoji: '💬', title: 'Votre profil, une fois', text: "Quelques questions sur vous deux : ce qui vous plaît, ce que vous ne voulez jamais, votre budget." },
  { emoji: '✨', title: 'Une envie par soirée', text: "Faire la fête, se poser, pimenter, une occasion à fêter : jusqu'à trois envies, un jour, si vous dînez, l'heure et le budget de cette soirée-là." },
  { emoji: '🌙', title: 'Trois parcours au choix', text: "Horaires, trajets, prix et liens de réservation ; une étape ne vous plaît pas, on la retire au sort. Et si vous découchez, la nuit est prévue." },
];

export default function AccueilScreen() {
  const theme = useTheme();
  const [profile, setProfile] = useState<SavedProfile | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    (async () => {
      const id = await rememberedProfile();
      if (id) {
        try {
          setProfile(await getProfile(id));
        } catch {
          // No saved profile reachable — fall back to the first-visit flow below.
        }
      }
      setLoaded(true);
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
          <Image source={{ uri: BANNER }} style={styles.banner} />
          <ThemedText style={[styles.brand, { color: theme.accentInk }]}>Surprise</ThemedText>
          <ThemedText type="title">Des soirées uniques à deux dans Paris.</ThemedText>
          <ThemedText themeColor="textSecondary" style={styles.lead}>
            Dites-nous qui vous êtes, puis ce qui vous fait envie ce soir-là : on compose trois soirées complètes.
          </ThemedText>

          {loaded && <Start profile={profile} />}

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
        </SafeAreaView>
      </ScrollView>
    </ThemedView>
  );
}

function Start({ profile }: { profile: SavedProfile | null }) {
  if (!profile) {
    return (
      <ThemedView style={styles.actions}>
        <PrimaryLink href="/profil">Faire notre profil</PrimaryLink>
        <TextLink href="/soiree">Une soirée tout de suite, sans profil →</TextLink>
      </ThemedView>
    );
  }
  const p = profile.profile;
  return (
    <ThemedView style={styles.persona} type="backgroundElement">
      <ThemedText type="small" themeColor="textSecondary">
        {p.names ? `Content de vous revoir, ${p.names}` : 'Content de vous revoir'}
      </ThemedText>
      <ThemedText type="subtitle">{p.persona.name}</ThemedText>
      <ThemedText>{p.persona.text}</ThemedText>
      <ThemedView style={styles.actions} type="backgroundElement">
        <PrimaryLink href={{ pathname: '/soiree', params: { p: profile.id } }}>Préparer une soirée</PrimaryLink>
        <TextLink href={{ pathname: '/profil', params: { p: profile.id } }}>Revoir notre profil</TextLink>
        <TextLink href="/profil">Refaire le quiz</TextLink>
      </ThemedView>
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
  brand: { fontFamily: Fonts.headingBold, fontSize: 18, marginTop: Spacing.three },
  lead: { fontSize: 17, lineHeight: 24 },
  actions: { gap: Spacing.two, alignItems: 'flex-start' },
  persona: { gap: Spacing.two, padding: Spacing.three, borderRadius: Spacing.three },
  progressTrack: { height: 6, borderRadius: 999, backgroundColor: '#efe0cf', overflow: 'hidden' },
  progressBar: { height: '100%', width: '33%', borderRadius: 999, backgroundColor: '#caa15a' },
  steps: { gap: Spacing.two, marginTop: Spacing.three },
  step: { flexDirection: 'row', gap: Spacing.two, padding: Spacing.three, borderRadius: Spacing.three },
  stepEmoji: { fontSize: 24 },
  stepBody: { flex: 1, gap: 2 },
});

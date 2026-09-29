import { useLocalSearchParams } from 'expo-router';
import { type ReactNode, useEffect, useState } from 'react';
import { Linking, ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { AccountNav } from '@/components/account-nav';
import { PrimaryButton, TextLink } from '@/components/buttons';
import { DayField } from '@/components/day-field';
import { OptionButton, OptionRow } from '@/components/option-button';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { MaxContentWidth, Spacing } from '@/constants/theme';
import { API_URL, getProfile, getSoiree, composeSoiree, type Night, type SavedProfile, type SoireeData } from '@/lib/api';
import { isoDay, longDay, nextFriday } from '@/lib/dates';

const MEALS = [
  { value: true, label: 'Oui, on dîne pendant la soirée', emoji: '🍽️' },
  { value: false, label: "Non, on aura déjà mangé", emoji: '✅' },
];
const NIGHTS = [
  { value: false, label: 'On rentre chez nous', emoji: '🏠' },
  { value: true, label: 'On découche : une nuit dans un hôtel ou une love room', emoji: '🛏️' },
];

export default function SoireeScreen() {
  const { p } = useLocalSearchParams<{ p?: string }>();
  const [data, setData] = useState<SoireeData | null>(null);
  const [profile, setProfile] = useState<SavedProfile | null>(null);
  const [night, setNight] = useState<Night>({
    envies: [], diner: null, decoucher: false, occasion: null, start: null, end: null, budget: null, day: nextFriday(), profile: null,
  });
  const [status, setStatus] = useState<'idle' | 'composing' | 'error'>('idle');

  useEffect(() => {
    (async () => {
      const soiree = await getSoiree();
      setData(soiree);
      if (p) {
        const found = await getProfile(p).catch(() => null);
        if (found) {
          setProfile(found);
          setNight((n) => ({
            ...n,
            profile: found.id,
            day: found.profile.first_day && found.profile.first_day >= isoDay(new Date()) ? found.profile.first_day : n.day,
          }));
        }
      }
    })();
  }, [p]);

  if (!data) {
    return (
      <Screen>
        <ThemedText themeColor="textSecondary">Chargement…</ThemedText>
      </Screen>
    );
  }

  async function compose() {
    setStatus('composing');
    try {
      const { url } = await composeSoiree(night);
      await Linking.openURL(`${API_URL}${url}`);
      setStatus('idle');
    } catch {
      setStatus('error');
    }
  }

  function toggleEnvie(value: string) {
    setNight((n) => ({
      ...n,
      envies: n.envies.includes(value) ? n.envies.filter((v) => v !== value) : n.envies.length < data!.max ? [...n.envies, value] : n.envies,
    }));
  }
  const toggleOccasion = (value: string) => setNight((n) => ({ ...n, occasion: n.occasion === value ? null : value }));
  const toggleStart = (value: string) => setNight((n) => ({ ...n, start: n.start === value ? null : value }));
  const toggleEnd = (value: string) => setNight((n) => ({ ...n, end: n.end === value ? null : value }));

  const p2 = profile?.profile;
  const ready = night.envies.length > 0 && night.diner !== null && !!night.day;

  return (
    <Screen>
      <AccountNav />
      {p2 ? (
        <ThemedView type="backgroundElement" style={styles.profileLine}>
          <ThemedText type="small" themeColor="textSecondary">
            {p2.names || p2.persona.name}
            {p2.names ? ` · ${p2.persona.name}` : ''} — vos « jamais », votre budget et vos goûts s&apos;appliquent.{' '}
          </ThemedText>
          <TextLink href={{ pathname: '/profil', params: { p: profile!.id } }}>Voir le profil</TextLink>
        </ThemedView>
      ) : (
        <ThemedView type="backgroundElement" style={styles.profileLine}>
          <ThemedText type="small" themeColor="textSecondary">Sans profil, on compose avec des réglages par défaut. </ThemedText>
          <TextLink href="/profil">Faire le quiz</TextLink>
        </ThemedView>
      )}

      <ThemedText type="title">Ce soir, envie de quoi ?</ThemedText>
      <ThemedText themeColor="textSecondary">Jusqu&apos;à {data.max} envies, on les mêle dans la soirée.</ThemedText>
      <ThemedText type="small" themeColor="textSecondary">{night.envies.length} sur {data.max}</ThemedText>
      <OptionRow>
        {data.envies.map((o) => (
          <OptionButton key={o.value} label={o.label} emoji={o.emoji} selected={night.envies.includes(o.value)}
            disabled={!night.envies.includes(o.value) && night.envies.length >= data.max}
            onPress={() => toggleEnvie(o.value)} />
        ))}
      </OptionRow>

      <ThemedText type="subtitle" style={styles.sub}>Et pour manger ?</ThemedText>
      <OptionRow>
        {MEALS.map((o) => (
          <OptionButton key={String(o.value)} label={o.label} emoji={o.emoji} selected={night.diner === o.value}
            onPress={() => setNight((n) => ({ ...n, diner: o.value }))} />
        ))}
      </OptionRow>

      <ThemedText type="subtitle" style={styles.sub}>Et après ?</ThemedText>
      <OptionRow>
        {NIGHTS.map((o) => (
          <OptionButton key={String(o.value)} label={o.label} emoji={o.emoji} selected={night.decoucher === o.value}
            onPress={() => setNight((n) => ({ ...n, decoucher: o.value }))} />
        ))}
      </OptionRow>

      <ThemedText type="subtitle" style={styles.sub}>Et pour commencer ?</ThemedText>
      <ThemedText type="small" themeColor="textSecondary">Sans choix : l&apos;heure habituelle, ou plus tôt si une envie le demande.</ThemedText>
      <OptionRow>
        {data.starts.map((o) => (
          <OptionButton key={o.value} label={o.label} emoji={o.emoji} pill selected={night.start === o.value} onPress={() => toggleStart(o.value)} />
        ))}
      </OptionRow>

      <ThemedText type="subtitle" style={styles.sub}>Et pour finir ?</ThemedText>
      <ThemedText type="small" themeColor="textSecondary">Sans choix : ce que vos envies demandent, ou minuit et demi.</ThemedText>
      <OptionRow>
        {data.ends.map((o) => (
          <OptionButton key={o.value} label={o.label} emoji={o.emoji} pill selected={night.end === o.value} onPress={() => toggleEnd(o.value)} />
        ))}
      </OptionRow>

      <ThemedText type="subtitle" style={styles.sub}>Et le budget, pour cette soirée ?</ThemedText>
      <ThemedText type="small" themeColor="textSecondary">{p2 ? 'Sans choix : le budget habituel de votre profil.' : 'Sans choix : 120 €.'}</ThemedText>
      <OptionRow>
        {data.budgets.map((o) => (
          <OptionButton key={o.budget} label={o.label} emoji={o.emoji} pill selected={night.budget === o.budget}
            onPress={() => setNight((n) => ({ ...n, budget: n.budget === o.budget ? null : o.budget }))} />
        ))}
      </OptionRow>

      <ThemedText type="subtitle" style={styles.sub}>Une occasion ?</ThemedText>
      <OptionRow>
        {data.occasions.map((o) => (
          <OptionButton key={o.value} label={o.label} emoji={o.emoji} pill selected={night.occasion === o.value} onPress={() => toggleOccasion(o.value)} />
        ))}
      </OptionRow>

      <DayField value={night.day} onChange={(day) => setNight((n) => ({ ...n, day }))} />

      {status === 'error' && <ThemedText style={styles.error}>La composition a échoué. Réessayez dans un instant.</ThemedText>}
      <View style={styles.nav}>
        <View />
        <PrimaryButton disabled={!ready || status === 'composing'} onPress={compose}>
          {status === 'composing' ? `On compose votre soirée du ${longDay(night.day)}…` : 'Composer notre soirée'}
        </PrimaryButton>
      </View>
    </Screen>
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
  safeArea: { width: '100%', maxWidth: MaxContentWidth, paddingHorizontal: Spacing.four, paddingVertical: Spacing.three, gap: Spacing.two },
  profileLine: { padding: Spacing.two + 2, borderRadius: 14, marginBottom: Spacing.two },
  sub: { marginTop: Spacing.three },
  nav: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: Spacing.three, marginBottom: Spacing.four },
  error: { color: '#ff5c72' },
});

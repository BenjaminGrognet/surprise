import { type ReactNode, useEffect, useState } from 'react';
import { Image, ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { AccountNav } from '@/components/account-nav';
import { PrimaryButton, TextButton, TextLink } from '@/components/buttons';
import { DayField } from '@/components/day-field';
import { OptionButton, OptionRow } from '@/components/option-button';
import { RouteResult } from '@/components/route-result';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { MaxContentWidth, Spacing } from '@/constants/theme';
import { chooseEvening, currentUser } from '@/lib/account';
import {
  composeSoiree, getQuiz, getSoiree, getSoireeState, redoPart,
  type ComposedSoiree, type Night, type Profile, type SoireeData,
} from '@/lib/api';
import { isoDay, longDay, nextFriday } from '@/lib/dates';
import { rememberedProfile } from '@/lib/local-store';

const BANNER = 'https://images.unsplash.com/photo-1671691302268-e316f81c7b3e?auto=format&fit=crop&w=1600&q=60';

const MEALS = [
  { value: true, label: 'Oui, on dîne pendant la soirée', emoji: '🍽️' },
  { value: false, label: "Non, on aura déjà mangé", emoji: '✅' },
];
const NIGHTS = [
  { value: false, label: 'On rentre chez nous', emoji: '🏠' },
  { value: true, label: 'On découche : une nuit dans un hôtel ou une love room', emoji: '🛏️' },
];
// While Claude's titles are still coming, poll for up to a minute, every couple of seconds.
const NAMING_TIMEOUT_MS = 60000;
const NAMING_POLL_MS = 2000;

export default function SoireeScreen() {
  const [data, setData] = useState<SoireeData | null>(null);
  const [vibes, setVibes] = useState<Record<string, string>>({});
  const [profile, setProfile] = useState<Profile | null>(null);
  const [night, setNight] = useState<Night>({
    envies: [], diner: null, decoucher: false, occasion: null, start: null, end: null, budget: null, day: nextFriday(), profile: null,
  });
  const [status, setStatus] = useState<'idle' | 'composing' | 'error'>('idle');
  const [composed, setComposed] = useState<ComposedSoiree | null>(null);
  const [busyRedo, setBusyRedo] = useState<string | null>(null);
  const [chosen, setChosen] = useState<Set<number>>(new Set());
  // 'signin': not signed in, needs a link to /compte. A string: a plain error message.
  const [notice, setNotice] = useState<'signin' | string | null>(null);

  useEffect(() => {
    (async () => {
      const [soiree, quiz] = await Promise.all([getSoiree(), getQuiz()]);
      setData(soiree);
      setVibes(quiz.vibes);
      const remembered = await rememberedProfile();
      if (remembered) {
        setProfile(remembered.profile);
        setNight((n) => ({
          ...n,
          profile: remembered.profile,
          day: remembered.profile.first_day && remembered.profile.first_day >= isoDay(new Date()) ? remembered.profile.first_day : n.day,
        }));
      }
    })();
  }, []);

  // Claude's titles arrive a few seconds after the composition: poll until they do.
  useEffect(() => {
    if (!composed?.naming) return;
    const since = Date.now();
    let cancelled = false;
    const poll = async () => {
      const fresh = await getSoireeState(composed.name).catch(() => null);
      if (cancelled) return;
      if (fresh && !fresh.naming) return setComposed(fresh);
      if (Date.now() - since < NAMING_TIMEOUT_MS) setTimeout(poll, NAMING_POLL_MS);
    };
    const timer = setTimeout(poll, NAMING_POLL_MS);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [composed?.naming, composed?.name]);

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
      setComposed(await composeSoiree(night));
      setChosen(new Set());
      setStatus('idle');
    } catch {
      setStatus('error');
    }
  }

  async function redo(redoPath: string) {
    if (!composed) return;
    setBusyRedo(redoPath);
    setNotice(null);
    try {
      setComposed(await redoPart(composed.name, redoPath));
    } catch {
      setNotice('Pas de nouvelle proposition : réessayez dans un instant.');
    } finally {
      setBusyRedo(null);
    }
  }

  async function choose(route: ComposedSoiree['routes'][number]) {
    if (!composed) return;
    setNotice(null);
    if (!(await currentUser())) {
      setNotice('signin');
      return;
    }
    try {
      await chooseEvening({
        pageName: composed.name, routeIndex: route.index, title: route.title, pitch: route.pitch,
        vibes: composed.vibes.map((v) => vibes[v] || v), day: route.day,
      });
      setChosen((prev) => new Set(prev).add(route.index));
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Impossible de la garder.');
    }
  }

  if (composed) {
    return (
      <Screen>
        <AccountNav />
        <TextButton onPress={() => setComposed(null)}>← Recomposer la soirée</TextButton>
        <ThemedText type="title" style={styles.sub}>
          {composed.routes.length > 0 ? `${composed.routes.length} soirées pour vous deux` : 'Aucun parcours ce soir-là'}
        </ThemedText>
        {composed.routes.length === 0 ? (
          <ThemedText themeColor="textSecondary">Élargissez les horaires, le budget ou les envies, et recomposez.</ThemedText>
        ) : null}
        {notice === 'signin' ? (
          <ThemedView type="backgroundElement" style={styles.profileLine}>
            <ThemedText type="small" themeColor="textSecondary">Connectez-vous pour garder cette soirée dans votre historique. </ThemedText>
            <TextLink href="/compte">Aller à mon compte</TextLink>
          </ThemedView>
        ) : notice ? (
          <ThemedText style={styles.error}>{notice}</ThemedText>
        ) : null}
        {composed.routes.map((route) => (
          <RouteResult
            key={route.index}
            route={route}
            vibes={vibes}
            chosen={chosen.has(route.index)}
            busyRedo={busyRedo}
            onRedo={redo}
            onChoose={() => choose(route)}
          />
        ))}
      </Screen>
    );
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

  const p2 = profile;
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
          <TextLink href="/profil">Voir le profil</TextLink>
        </ThemedView>
      ) : (
        <ThemedView type="backgroundElement" style={styles.profileLine}>
          <ThemedText type="small" themeColor="textSecondary">Sans profil, on compose avec des réglages par défaut. </ThemedText>
          <TextLink href="/profil">Faire le quiz</TextLink>
        </ThemedView>
      )}

      <Image source={{ uri: BANNER }} style={styles.banner} />
      <View style={styles.badge}>
        <ThemedText type="smallBold" style={styles.badgeText}>Soirée à deux</ThemedText>
      </View>
      <ThemedText type="title">Ce soir, envie de quoi ?</ThemedText>
      <ThemedText themeColor="textSecondary">Jusqu&apos;à {data.max} envies, on les mêle dans la soirée.</ThemedText>

      <View style={styles.progressRow}>
        <ThemedText type="smallBold" style={styles.progressLabel}>{night.envies.length} sur {data.max} choisies</ThemedText>
        <View style={styles.progressTrack}>
          <View style={[styles.progressBar, { width: `${(night.envies.length / data.max) * 100}%` }]} />
        </View>
      </View>
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
  badge: { alignSelf: 'flex-start', paddingVertical: 6, paddingHorizontal: 14, borderRadius: 999, backgroundColor: '#caa15a' },
  badgeText: { color: '#ffffff', letterSpacing: 0.5 },
  banner: { width: '100%', height: 160, borderRadius: Spacing.three },
  progressRow: { gap: Spacing.one },
  progressLabel: { color: '#a67c1e' },
  progressTrack: { height: 6, borderRadius: 999, backgroundColor: '#efe0cf', overflow: 'hidden' },
  progressBar: { height: '100%', borderRadius: 999, backgroundColor: '#caa15a' },
  sub: { marginTop: Spacing.three },
  nav: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: Spacing.three, marginBottom: Spacing.four },
  error: { color: '#ff5c72' },
});

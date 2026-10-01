import { type ReactNode, useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';

import { PrimaryButton, PrimaryLink, TextButton, TextLink } from '@/components/buttons';
import { DayField } from '@/components/day-field';
import { MoodSlider } from '@/components/mood-slider';
import { CheckLine, OptionButton, OptionRow } from '@/components/option-button';
import { RouteResult } from '@/components/route-result';
import { Screen } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { chooseEvening, currentUser, eveningsHistory } from '@/lib/account';
import {
  composeSoiree, getQuiz, getSoiree, getSoireeState, redoPart,
  type ComposedSoiree, type Night, type Profile, type SoireeData,
} from '@/lib/api';
import { isoDay, longDay, nextFriday } from '@/lib/dates';
import { rememberedProfile } from '@/lib/local-store';

// The mood slider's stops, from "Tamisé & Intime" to "Aventureux & Insolite": each one is one of
// the server's wishes (surprise.quiz.ENVIES). The other wishes are the "secret options".
const MOODS = ['cocooning', 'romantique', 'nous', 'curieux', 'surprise'];
const MIDDLE_MOOD = 2;

const MEALS = [
  { value: true, label: 'Oui, on dîne', emoji: '🍽️' },
  { value: false, label: 'Non, déjà mangé', emoji: '✓' },
];
const NIGHTS = [
  { value: false, label: 'On rentre', emoji: '🏠' },
  { value: true, label: 'On découche', emoji: '🗝️' },
];
// While Claude's titles are still coming, poll for up to a minute, every couple of seconds.
const NAMING_TIMEOUT_MS = 60000;
const NAMING_POLL_MS = 2000;

export default function SoireeScreen() {
  // ?soiree=<name>: the evening composed before, so a reload or a shared link shows it again;
  // &route=<index>: the route the couple chose, then the only one shown.
  const { soiree: saved, route: picked } = useLocalSearchParams<{ soiree?: string; route?: string }>();
  const [data, setData] = useState<SoireeData | null>(null);
  const [vibes, setVibes] = useState<Record<string, string>>({});
  const [profile, setProfile] = useState<Profile | null>(null);
  const [mood, setMood] = useState(MIDDLE_MOOD);
  const [secrets, setSecrets] = useState<string[]>([]);
  const [night, setNight] = useState<Night>({
    envies: [], diner: null, decoucher: false, occasion: null, start: null, end: null, budget: null, day: nextFriday(), profile: null,
  });
  const [status, setStatus] = useState<'idle' | 'composing' | 'error'>('idle');
  const [composed, setComposed] = useState<ComposedSoiree | null>(null);
  const [busyRedo, setBusyRedo] = useState<string | null>(null);
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

  useEffect(() => {
    if (saved) getSoireeState(saved).then(setComposed).catch(() => null);
  }, [saved]);

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

  const moods = MOODS.map((value) => data.envies.find((e) => e.value === value)).filter((e): e is NonNullable<typeof e> => !!e);
  const others = data.envies.filter((e) => !MOODS.includes(e.value));
  const moodValue = moods[Math.min(mood, moods.length - 1)]?.value;
  const envies = [...(moodValue ? [moodValue] : []), ...secrets].slice(0, data.max);

  async function compose() {
    setStatus('composing');
    try {
      const history = (await currentUser()) ? await eveningsHistory().catch(() => []) : [];
      const fresh = await composeSoiree({ ...night, envies, done: history.map((h) => ({ page_name: h.page_name, route_index: h.route_index })) });
      setComposed(fresh);
      router.setParams({ soiree: fresh.name, route: undefined });
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
      setNotice(redoPath.endsWith('/remove') ? 'Étape non retirée : réessayez dans un instant.' : 'Pas de nouvelle proposition : réessayez dans un instant.');
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
      // Kept: on to the day itself, where each partner picks a side — organiser or surprised.
      router.replace({ pathname: '/revelation', params: { soiree: composed.name, route: String(route.index) } });
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Impossible de la garder.');
    }
  }

  if (composed) {
    const shown = picked === undefined ? composed.routes : composed.routes.filter((r) => String(r.index) === picked);
    const chosen = picked !== undefined && shown.length > 0;
    return (
      <Screen>
        <TextButton onPress={() => (chosen ? router.back() : setComposed(null))}>{chosen ? '← Retour' : '← Changer nos envies'}</TextButton>
        <ThemedText type="eyebrow">
          {chosen ? longDay(shown[0].day) : composed.routes.length > 0 ? `${composed.routes.length} intrigues possibles` : 'Aucune intrigue ce soir-là'}
        </ThemedText>
        <ThemedText type="title">
          {chosen ? 'Votre feuille de route' : composed.routes.length > 0 ? 'Gardez celle qui vous trouble' : 'Le hasard a fait chou blanc'}
        </ThemedText>
        {composed.routes.length === 0 ? (
          <ThemedText themeColor="textSecondary">Élargissez les horaires, le budget ou les envies, et relancez l&apos;intrigue.</ThemedText>
        ) : !chosen ? (
          <ThemedText themeColor="textSecondary">
            Une étape ne vous plaît pas ? Changez-la ou retirez-la. Une fois gardée, votre passager n&apos;en verra que les indices.
          </ThemedText>
        ) : (
          <PrimaryLink href={{ pathname: '/revelation', params: { soiree: composed.name, route: picked } }}>Ouvrir la révélation</PrimaryLink>
        )}
        {notice === 'signin' ? (
          <View style={styles.notice}>
            <ThemedText type="small" themeColor="textSecondary">Connectez-vous pour garder cette intrigue. </ThemedText>
            <TextLink href="/compte">Aller à mon compte</TextLink>
          </View>
        ) : notice ? (
          <ThemedText themeColor="danger">{notice}</ThemedText>
        ) : null}
        {shown.map((route) => (
          <RouteResult
            key={route.index}
            route={route}
            chosen={picked === String(route.index)}
            busyRedo={busyRedo}
            onRedo={redo}
            onChoose={() => choose(route)}
          />
        ))}
      </Screen>
    );
  }

  const toggleSecret = (value: string) =>
    setSecrets((s) => (s.includes(value) ? s.filter((v) => v !== value) : s.length < data.max - 1 ? [...s, value] : s));
  const toggleOccasion = (value: string) => setNight((n) => ({ ...n, occasion: n.occasion === value ? null : value }));
  const toggleStart = (value: string) => setNight((n) => ({ ...n, start: n.start === value ? null : value }));
  const toggleEnd = (value: string) => setNight((n) => ({ ...n, end: n.end === value ? null : value }));
  const ready = envies.length > 0 && night.diner !== null && !!night.day;

  return (
    <Screen gap={Spacing.four}>
      <View style={styles.intro}>
        <ThemedText type="eyebrow">Le filtre de vos envies</ThemedText>
        <ThemedText type="title">Quelle intrigue vous tente ?</ThemedText>
        <ThemedText type="small" themeColor="textSecondary">
          {profile
            ? `${profile.names ? `${profile.names} · ` : ''}${profile.persona.name} : vos « jamais », votre budget et vos goûts s'appliquent.`
            : 'Sans profil, on trame avec des réglages par défaut.'}
        </ThemedText>
        <TextLink href="/profil">{profile ? 'Voir le profil →' : 'Faire le quiz →'}</TextLink>
      </View>

      <Section title="L'humeur du soir">
        <MoodSlider
          stops={moods.map((m) => ({ label: m.label, emoji: m.emoji }))}
          value={Math.min(mood, moods.length - 1)}
          onChange={setMood}
          left="Tamisé & Intime"
          right="Aventureux & Insolite"
        />
      </Section>

      <Section title="Les options secrètes" hint={`Jusqu'à ${data.max - 1}, glissées dans le programme.`}>
        <View>
          {others.map((o) => (
            <CheckLine key={o.value} label={o.label} emoji={o.emoji} checked={secrets.includes(o.value)}
              disabled={!secrets.includes(o.value) && secrets.length >= data.max - 1}
              onPress={() => toggleSecret(o.value)} />
          ))}
        </View>
      </Section>

      <Section title="Le dîner fait-il partie du complot ?">
        <OptionRow>
          {MEALS.map((o) => (
            <OptionButton key={String(o.value)} label={o.label} emoji={o.emoji} pill selected={night.diner === o.value}
              onPress={() => setNight((n) => ({ ...n, diner: o.value }))} />
          ))}
        </OptionRow>
      </Section>

      <Section title="Et quand la nuit tombe ?" hint="Découcher : une nuit à l'hôtel ou dans une love room.">
        <OptionRow>
          {NIGHTS.map((o) => (
            <OptionButton key={String(o.value)} label={o.label} emoji={o.emoji} pill selected={night.decoucher === o.value}
              onPress={() => setNight((n) => ({ ...n, decoucher: o.value }))} />
          ))}
        </OptionRow>
      </Section>

      <Section title="L'heure du rendez-vous" hint="Sans choix : l'heure habituelle, ou plus tôt si une envie le demande.">
        <OptionRow>
          {data.starts.map((o) => (
            <OptionButton key={o.value} label={o.label} emoji={o.emoji} pill selected={night.start === o.value} onPress={() => toggleStart(o.value)} />
          ))}
        </OptionRow>
      </Section>

      <Section title="Le rideau tombe…" hint="Sans choix : ce que vos envies demandent, ou minuit et demi.">
        <OptionRow>
          {data.ends.map((o) => (
            <OptionButton key={o.value} label={o.label} emoji={o.emoji} pill selected={night.end === o.value} onPress={() => toggleEnd(o.value)} />
          ))}
        </OptionRow>
      </Section>

      <Section title="Le budget du soir" hint={profile ? 'Sans choix : le budget habituel de votre profil.' : 'Sans choix : 120 €.'}>
        <OptionRow>
          {data.budgets.map((o) => (
            <OptionButton key={o.budget} label={o.label} emoji={o.emoji} pill selected={night.budget === o.budget}
              onPress={() => setNight((n) => ({ ...n, budget: n.budget === o.budget ? null : o.budget }))} />
          ))}
        </OptionRow>
      </Section>

      <Section title="Une occasion à célébrer ?">
        <OptionRow>
          {data.occasions.map((o) => (
            <OptionButton key={o.value} label={o.label} emoji={o.emoji} pill selected={night.occasion === o.value} onPress={() => toggleOccasion(o.value)} />
          ))}
        </OptionRow>
      </Section>

      <DayField label="Le jour J" value={night.day} onChange={(day) => setNight((n) => ({ ...n, day }))} />

      {status === 'error' && <ThemedText themeColor="danger">L&apos;intrigue n&apos;a pas pu être tramée. Réessayez dans un instant.</ThemedText>}
      <PrimaryButton wide disabled={!ready || status === 'composing'} onPress={compose}>
        {status === 'composing' ? `On trame votre soirée du ${longDay(night.day)}…` : night.diner === null ? 'Dîner ou pas ? Dites-le-nous' : 'Tramer nos intrigues'}
      </PrimaryButton>
    </Screen>
  );
}

function Section({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  const theme = useTheme();
  return (
    <View style={[styles.section, { borderColor: theme.line, backgroundColor: theme.backgroundElement }]}>
      <View style={styles.sectionHead}>
        <ThemedText type="subtitle">{title}</ThemedText>
        {hint ? <ThemedText type="small" themeColor="textSecondary">{hint}</ThemedText> : null}
      </View>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  intro: { gap: Spacing.two },
  section: { gap: Spacing.three, padding: Spacing.four, borderRadius: 22, borderWidth: 1 },
  sectionHead: { gap: Spacing.one },
  notice: { padding: Spacing.three, borderRadius: 14 },
});

import { type ReactNode, useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';

import { PrimaryButton, PrimaryLink, TextButton, TextLink } from '@/components/buttons';
import { DayField } from '@/components/day-field';
import { PageCard } from '@/components/intrigue-card';
import { OptionCard, OptionGrid } from '@/components/option-card';
import { RouteResult } from '@/components/route-result';
import { Screen } from '@/components/screen';
import { Waiting } from '@/components/spinner';
import { ThemedText } from '@/components/themed-text';
import { Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { chooseEvening, currentUser, eveningsHistory, keptEvening } from '@/lib/account';
import {
  chooseRoute, composeSoiree, getQuiz, getSoiree, getSoireeState, redoPart,
  type ComposedSoiree, type Night, type Profile, type SoireeData,
} from '@/lib/api';
import { isoDay, longDay, nextFriday, shortDay } from '@/lib/dates';
import { rememberedProfile } from '@/lib/local-store';

// The mood cards, from "Tamisé & Intime" to "Aventureux & Insolite": each one is one of
// the server's wishes (surprise.quiz.ENVIES). The other wishes are the "secret options".
const MOODS = ['cocooning', 'romantique', 'nous', 'curieux', 'surprise'];
const MIDDLE_MOOD = 2;

const MEALS = [
  { value: true, label: 'Oui, on dîne', icon: 'couvert' },
  { value: false, label: 'Non, déjà mangé', icon: 'coche' },
];
const NIGHTS = [
  { value: false, label: 'On rentre', icon: 'maison' },
  { value: true, label: 'On découche', icon: 'cle' },
];
// While Claude's titles are still coming, poll for up to a minute, every couple of seconds.
const NAMING_TIMEOUT_MS = 60000;
const NAMING_POLL_MS = 2000;

export default function SoireeScreen() {
  // ?soiree=<name>: the evening composed before, so a reload or a shared link shows it again; once a route
  // is kept, the page has that route alone.
  const { soiree: saved } = useLocalSearchParams<{ soiree?: string }>();
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

  // A page whose route was kept: is it in the couple's history yet (else "Garder" again saves it there)?
  const [keptPage, setKeptPage] = useState<string | null>(null);
  useEffect(() => {
    if (composed?.chosen) keptEvening(composed.name).then((e) => setKeptPage(e?.page_name ?? null)).catch(() => {});
  }, [composed?.chosen, composed?.name]);
  const inHistory = !!composed && keptPage === composed.name;

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
      const fresh = await composeSoiree({ ...night, envies, done: history.map((h) => h.page_name) });
      setComposed(fresh);
      router.setParams({ soiree: fresh.name });
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
    // The page keeps this route alone (the others go), then the couple's history keeps the page. Kept again
    // (the history failed the first time), the page has that route as its route 0 and nothing changes.
    const kept = await chooseRoute(composed.name, route.index).catch(() => null);
    if (!kept) {
      setNotice("Cette intrigue n'a pas pu être gardée : réessayez dans un instant.");
      return;
    }
    setComposed(kept);
    try {
      await chooseEvening({
        pageName: composed.name, title: route.title, secretTitle: route.secret_title, pitch: route.pitch,
        vibes: composed.vibes.map((v) => vibes[v] || v), day: route.day,
      });
      // Kept: on to the day itself, where each partner picks a side — organiser or surprised.
      router.replace({ pathname: '/revelation', params: { soiree: composed.name } });
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Impossible de la garder.');
    }
  }

  if (composed) {
    const shown = composed.routes;
    const chosen = composed.chosen && shown.length > 0;
    return (
      <Screen>
        <PageCard
          badge={chosen ? shortDay(shown[0].day) : `${composed.routes.length} intrigue${composed.routes.length > 1 ? 's' : ''}`}
          title={chosen ? 'Votre feuille de route' : composed.routes.length > 0 ? 'Trois intrigues se murmurent au salon' : 'Le hasard a fait chou blanc'}
          text={composed.routes.length === 0
            ? "Élargissez les horaires, le budget ou les envies, et relancez l'intrigue."
            : chosen ? undefined : "Une étape ne vous plaît pas ? Changez-la ou retirez-la. Une fois gardée, votre passager n'en verra que les indices."}>
          {chosen && inHistory ? (
            <PrimaryLink href={{ pathname: '/revelation', params: { soiree: composed.name } }}>Ouvrir la révélation</PrimaryLink>
          ) : null}
          <TextButton onPress={() => (chosen ? router.back() : setComposed(null))}>{chosen ? '← Retour' : '← Changer nos envies'}</TextButton>
        </PageCard>
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
            chosen={chosen && inHistory}
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
    <Screen gap={Spacing.two}>
      <PageCard
        badge={profile ? 'Votre profil' : 'Sans profil'}
        title="Quelle intrigue vous tente ?"
        text={profile
          ? `${profile.names ? `${profile.names}, vos` : 'Vos'} « jamais », votre budget et vos goûts s'appliquent.`
          : 'On trame avec des réglages par défaut.'}>
        <TextLink href="/profil">{profile ? 'Voir le profil →' : 'Faire le quiz →'}</TextLink>
      </PageCard>

      <Section title="L'humeur du soir">
        <OptionGrid>
          {moods.map((m, i) => (
            <OptionCard key={m.value} label={m.label} icon={m.icon} emoji={m.emoji} selected={Math.min(mood, moods.length - 1) === i}
              onPress={() => setMood(i)} />
          ))}
        </OptionGrid>
      </Section>

      <Section title="Les options secrètes" hint={`Jusqu'à ${data.max - 1}, glissées dans le programme.`}>
        <OptionGrid>
          {others.map((o) => (
            <OptionCard key={o.value} label={o.label} icon={o.icon} emoji={o.emoji} selected={secrets.includes(o.value)}
              disabled={!secrets.includes(o.value) && secrets.length >= data.max - 1}
              onPress={() => toggleSecret(o.value)} />
          ))}
        </OptionGrid>
      </Section>

      <Section title="Le dîner fait-il partie du complot ?">
        <OptionGrid>
          {MEALS.map((o) => (
            <OptionCard key={String(o.value)} label={o.label} icon={o.icon} selected={night.diner === o.value}
              onPress={() => setNight((n) => ({ ...n, diner: o.value }))} />
          ))}
        </OptionGrid>
      </Section>

      <Section title="Et quand la nuit tombe ?" hint="Découcher : une nuit à l'hôtel ou dans une love room.">
        <OptionGrid>
          {NIGHTS.map((o) => (
            <OptionCard key={String(o.value)} label={o.label} icon={o.icon} selected={night.decoucher === o.value}
              onPress={() => setNight((n) => ({ ...n, decoucher: o.value }))} />
          ))}
        </OptionGrid>
      </Section>

      <Section title="L'heure du rendez-vous" hint="Sans choix : l'heure habituelle, ou plus tôt si une envie le demande.">
        <OptionGrid>
          {data.starts.map((o) => (
            <OptionCard key={o.value} label={o.label} icon={o.icon} emoji={o.emoji} selected={night.start === o.value} onPress={() => toggleStart(o.value)} />
          ))}
        </OptionGrid>
      </Section>

      <Section title="Le rideau tombe…" hint="Sans choix : ce que vos envies demandent, ou minuit et demi.">
        <OptionGrid>
          {data.ends.map((o) => (
            <OptionCard key={o.value} label={o.label} icon={o.icon} emoji={o.emoji} selected={night.end === o.value} onPress={() => toggleEnd(o.value)} />
          ))}
        </OptionGrid>
      </Section>

      <Section title="Le budget du soir" hint={profile ? 'Sans choix : le budget habituel de votre profil.' : 'Sans choix : 120 €.'}>
        <OptionGrid>
          {data.budgets.map((o) => (
            <OptionCard key={o.budget} label={o.label} desc={o.desc} icon={o.icon} emoji={o.emoji} selected={night.budget === o.budget}
              onPress={() => setNight((n) => ({ ...n, budget: n.budget === o.budget ? null : o.budget }))} />
          ))}
        </OptionGrid>
      </Section>

      <Section title="Une occasion à célébrer ?">
        <OptionGrid>
          {data.occasions.map((o) => (
            <OptionCard key={o.value} label={o.label} icon={o.icon} emoji={o.emoji} selected={night.occasion === o.value} onPress={() => toggleOccasion(o.value)} />
          ))}
        </OptionGrid>
      </Section>

      <DayField label="Le jour J" value={night.day} onChange={(day) => setNight((n) => ({ ...n, day }))} />

      {status === 'composing' ? <Waiting title="La nuit ourdit ses secrets…" lines={COMPOSING_LINES} /> : null}
      {status === 'error' && <ThemedText themeColor="danger">L&apos;intrigue n&apos;a pas pu être tramée. Réessayez dans un instant.</ThemedText>}
      <PrimaryButton wide disabled={!ready || status === 'composing'} onPress={compose}>
        {status === 'composing' ? `Le ${longDay(night.day)} se trame en secret…` : night.diner === null ? 'Dîner ou pas ? Dites-le-nous' : 'Tramer nos intrigues'}
      </PrimaryButton>
    </Screen>
  );
}

function Section({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  const theme = useTheme();
  return (
    <View style={[styles.section, { borderColor: theme.line, backgroundColor: theme.backgroundElement }]}>
      <View style={styles.sectionHead}>
        <ThemedText type="smallBold">{title}</ThemedText>
        {hint ? <ThemedText type="small" themeColor="textSecondary">{hint}</ThemedText> : null}
      </View>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  section: { gap: Spacing.two, padding: Spacing.three, borderRadius: Radius.tile, borderWidth: 1 },
  sectionHead: { gap: 2 },
  notice: { padding: Spacing.three, borderRadius: 14 },
});

const COMPOSING_LINES = [
  'Les portes de la ville s’entrouvrent pour vous…',
  'Quelques adresses chuchotent encore à cette heure…',
  'Un détour secret se dessine entre deux ruelles…',
  'Les rendez-vous se scellent à la cire, un à un…',
  'La nuit garde le meilleur pour la fin.',
];

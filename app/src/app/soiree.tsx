import { type ReactNode, useEffect, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';

import { PrimaryButton, PrimaryLink, TextButton, TextLink } from '@/components/buttons';
import { DayField } from '@/components/day-field';
import { CardEmblem, IntrigueCard, PageCard } from '@/components/intrigue-card';
import { OptionCard, OptionGrid } from '@/components/option-card';
import { RouteResult } from '@/components/route-result';
import { Screen } from '@/components/screen';
import { Waiting } from '@/components/spinner';
import { ThemedText } from '@/components/themed-text';
import { Brands, Fonts, Radius, Spacing } from '@/constants/theme';
import { useCouple } from '@/hooks/use-couple';
import { useTastes } from '@/hooks/use-tastes';
import { PaletteProvider, useTheme } from '@/hooks/use-theme';
import { chooseEvening, currentUser, eveningsHistory, keptEvening, myTastes, votesOf } from '@/lib/account';
import {
  chooseRoute, composeSoiree, getQuiz, getSoiree, getSoireeState, redoPart, refusal,
  type ComposedSoiree, type Formule, type Night, type Profile, type SoireeData,
} from '@/lib/api';
import { isoDay, longDay, nextFriday, shortDay } from '@/lib/dates';
import { rememberedProfile } from '@/lib/local-store';

// The mood cards, from "Tamisé & Intime" to "Aventureux & Insolite": each one is one of
// the server's wishes (surprise.quiz.ENVIES, its MOODS; a band's, SQUAD_MOODS), the middle one chosen until the couple
// picks; several of them if they like. The other wishes are the "secret options": data.max wishes in all.
const MOODS = ['cocooning', 'romantique', 'nous', 'curieux', 'surprise'];
const MIDDLE_MOOD = 2;
// A band's evening (Secret Squad): how many they are, the instigateur counted (surprise.quiz.SQUAD_PERSONNES); from
// two, an evening with a friend being no date.
const PERSONNES = { min: 2, max: 10, default: 6 };
// From this many, fewer places book a table or a session for all of them online.
const BIG_BAND = 8;

const MEALS = [
  { value: true, label: 'Oui, on dîne', icon: 'couvert' },
  { value: false, label: 'Non, déjà mangé', icon: 'assiette_barree' },
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
  // is kept, the page has that route alone. ?formule=: the formula chosen first, Secret Date (duo) or Secret Squad.
  const { soiree: saved, formule: asked } = useLocalSearchParams<{ soiree?: string; formule?: string }>();
  // A passager composing in turn: the page speaks of the roles reversed.
  const turn = useCouple().role === 'passager';
  const [formule, setFormule] = useState<Formule | null>(asked === 'squad' || asked === 'duo' ? asked : null);
  const [personnes, setPersonnes] = useState(PERSONNES.default);
  const [data, setData] = useState<SoireeData | null>(null);
  const [vibes, setVibes] = useState<Record<string, string>>({});
  const [profile, setProfile] = useState<Profile | null>(null);
  const [picked, setPicked] = useState<string[] | null>(null); // the moods chosen, null: the middle one
  const [secrets, setSecrets] = useState<string[]>([]);
  // What the band never wants (Secret Squad): asked with the order, a band having no profile.
  const [eviter, setEviter] = useState<string[]>([]);
  const [night, setNight] = useState<Night>({
    envies: [], diner: null, decoucher: false, occasion: null, start: null, end: null, budget: null, day: nextFriday(), profile: null,
  });
  const [status, setStatus] = useState<'idle' | 'composing' | 'error'>('idle');
  const [composed, setComposed] = useState<ComposedSoiree | null>(null);
  const [busyRedo, setBusyRedo] = useState<string | null>(null);
  // 'signin': not signed in, needs a link to /compte. A string: a plain error message.
  const [notice, setNotice] = useState<'signin' | string | null>(null);
  const tastes = useTastes();

  useEffect(() => {
    if (!formule) return;
    (async () => {
      const [soiree, quiz] = await Promise.all([getSoiree(formule), getQuiz()]);
      setData(soiree);
      // A band says its vibes its own way.
      setVibes({ ...quiz.vibes, ...soiree.vibes });
      // A couple's profile; a band's evening comes from its order alone.
      const remembered = formule === 'duo' ? await rememberedProfile() : null;
      if (remembered) {
        setProfile(remembered.profile);
        setNight((n) => ({
          ...n,
          profile: remembered.profile,
          day: remembered.profile.first_day && remembered.profile.first_day >= isoDay(new Date()) ? remembered.profile.first_day : n.day,
        }));
      }
    })();
  }, [formule]);

  // Another formula, other wishes: those chosen for the other one go.
  function pickFormule(chosen: Formule) {
    if (chosen !== formule) {
      setData(null);
      setSecrets([]);
      setEviter([]);
      setPicked(null);
      setNight((n) => ({ ...n, occasion: null, budget: null, decoucher: false }));
    }
    setFormule(chosen);
    router.setParams({ formule: chosen });
  }

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

  if (!composed && !formule) return <FormulePicker turn={turn} onPick={pickFormule} />;
  const squad = (composed?.formule ?? formule) === 'squad';
  if (!composed && !data) {
    return (
      <PaletteProvider name={squad ? 'squad' : 'date'}>
        <Screen>
          <ThemedText themeColor="textSecondary">Chargement…</ThemedText>
        </Screen>
      </PaletteProvider>
    );
  }

  if (composed) return <PaletteProvider name={squad ? 'squad' : 'date'}>{result(composed)}</PaletteProvider>;
  if (!data) return null;
  const moodKeys = data.moods ?? MOODS;
  const moods = moodKeys.map((value) => data.envies.find((e) => e.value === value)).filter((e): e is NonNullable<typeof e> => !!e);
  const others = data.envies.filter((e) => !moodKeys.includes(e.value));
  const middle = moods[Math.min(MIDDLE_MOOD, moods.length - 1)]?.value;
  const chosenMoods = picked ?? (middle ? [middle] : []);
  const room = data.max - chosenMoods.length; // the secret options left
  const envies = [...chosenMoods, ...secrets].slice(0, data.max);

  async function compose() {
    setStatus('composing');
    try {
      const signedIn = !!(await currentUser());
      // A band's evening: neither the couple's profile nor its votes, only the evenings done (never the same activity twice).
      const [history, votes] = signedIn
        ? await Promise.all([eveningsHistory().catch(() => []), squad ? [] : myTastes().catch(() => [])])
        : [[], []];
      const band = squad ? { formule: 'squad' as const, personnes, profile: null, decoucher: false, eviter } : { formule: 'duo' as const };
      const fresh = await composeSoiree({ ...night, ...band, envies, done: history.map((h) => h.page_name), votes: votesOf(votes) });
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
    } catch (error) {
      setNotice(refusal(error) ?? (redoPath.endsWith('/remove') ? 'Étape non retirée : réessayez dans un instant.' : 'Pas de nouvelle proposition : réessayez dans un instant.'));
    } finally {
      setBusyRedo(null);
    }
  }

  // Back to the wishes, of the formula composed.
  function back(composed: ComposedSoiree) {
    pickFormule(composed.formule ?? 'duo');
    setComposed(null);
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
        formule: composed.formule, personnes: composed.personnes,
      });
      // Kept: on to the day itself, where each partner picks a side — organiser or surprised.
      router.replace({ pathname: '/revelation', params: { soiree: composed.name } });
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Impossible de la garder.');
    }
  }

  // The evening composed: its three routes to change, take out, vote on and keep; once kept, the route alone.
  function result(composed: ComposedSoiree) {
    const shown = composed.routes;
    const chosen = composed.chosen && shown.length > 0;
    const band = composed.formule === 'squad';
    const surprised = turn ? "c'est votre instigateur qui n'en verra que les indices" : band ? "la bande n'en verra que les indices" : "votre passager n'en verra que les indices";
    return (
      <Screen>
        <PageCard
          badge={chosen ? shortDay(shown[0].day) : `${composed.routes.length} intrigue${composed.routes.length > 1 ? 's' : ''}`}
          title={chosen ? 'Votre feuille de route' : composed.routes.length > 0 ? (band ? 'Trois virées pour la bande' : 'Trois intrigues se murmurent au salon') : 'Le hasard a fait chou blanc'}
          text={composed.routes.length === 0
            ? "Élargissez les horaires, le budget ou les envies, et relancez l'intrigue."
            : chosen
              ? undefined
              : band
                ? `Une étape ne vous plaît pas ? Changez-la ou retirez-la. Une fois gardée, ${surprised}.`
                : `Une étape ne vous plaît pas ? Changez-la ou retirez-la, et d'un pouce dites-nous si son genre vous plaît : les prochaines soirées en tiendront compte. Une fois gardée, ${surprised}.`}>
          {chosen && inHistory ? (
            <PrimaryLink href={{ pathname: '/revelation', params: { soiree: composed.name } }}>Ouvrir la révélation</PrimaryLink>
          ) : null}
          <TextButton onPress={() => (chosen ? router.back() : back(composed))}>{chosen ? '← Retour' : '← Changer nos envies'}</TextButton>
        </PageCard>
        {notice === 'signin' ? (
          <View style={styles.notice}>
            <ThemedText type="small" themeColor="textSecondary">Connectez-vous pour garder cette intrigue. </ThemedText>
            <TextLink href="/compte">Aller à mon compte</TextLink>
          </View>
        ) : notice ? (
          <ThemedText themeColor="danger">{notice}</ThemedText>
        ) : null}
        {tastes.error ? <ThemedText themeColor="danger">{tastes.error}</ThemedText> : null}
        {shown.map((route) => (
          <RouteResult
            key={route.index}
            route={route}
            chosen={chosen && inHistory}
            busyRedo={busyRedo}
            onRedo={redo}
            onChoose={() => choose(route)}
            votes={tastes.votes}
            onVote={band ? undefined : tastes.vote}
          />
        ))}
      </Screen>
    );
  }

  const toggleMood = (value: string) =>
    setPicked(chosenMoods.includes(value) ? chosenMoods.filter((v) => v !== value) : [...chosenMoods, value]);
  const toggleSecret = (value: string) =>
    setSecrets((s) => (s.includes(value) ? s.filter((v) => v !== value) : s.length < room ? [...s, value] : s));
  const toggleEviter = (value: string) => setEviter((e) => (e.includes(value) ? e.filter((v) => v !== value) : [...e, value]));
  const toggleOccasion = (value: string) => setNight((n) => ({ ...n, occasion: n.occasion === value ? null : value }));
  const toggleStart = (value: string) => setNight((n) => ({ ...n, start: n.start === value ? null : value }));
  const toggleEnd = (value: string) => setNight((n) => ({ ...n, end: n.end === value ? null : value }));
  const ready = envies.length > 0 && night.diner !== null && !!night.day;
  const profileLine = profile
    ? `${profile.names ? `${profile.names}, vos` : 'Vos'} « jamais », votre budget et vos goûts s'appliquent.`
    : 'On trame avec des réglages par défaut.';

  const range = data.personnes ?? PERSONNES;
  return (
    <PaletteProvider name={squad ? 'squad' : 'date'}>
      <Screen gap={Spacing.two}>
        {squad ? (
          <PageCard
            badge="Squad"
            title="Quelle virée pour la bande ?"
            text="Une soirée secrète entre potes : un EVJF, un anniversaire, des retrouvailles ou juste l'envie. Tout se décide ici, pour la bande ; les invités ne verront que les indices.">
            <TextButton onPress={() => pickFormule('duo')}>← Plutôt une soirée à deux</TextButton>
          </PageCard>
        ) : (
          <PageCard
            badge={turn ? 'À votre tour' : profile ? 'Votre profil' : 'Sans profil'}
            title={turn ? 'À votre tour de surprendre' : 'Quelle intrigue vous tente ?'}
            text={turn
              ? `Vous avez suivi les indices, à vous de les semer : concoctez une soirée dont votre complice ne saura presque rien. ${profileLine}`
              : profileLine}>
            <TextLink href="/profil">{profile ? 'Voir le profil →' : 'Faire le quiz →'}</TextLink>
            <TextButton onPress={() => pickFormule('squad')}>Plutôt une soirée entre potes →</TextButton>
          </PageCard>
        )}

        {squad ? (
          <Section
            title="Combien serez-vous ?"
            hint={`Vous compris, de ${range.min} à ${range.max}.${personnes >= BIG_BAND ? ' À partir de 8, moins de lieux se réservent en ligne pour tout le monde.' : ''}`}>
            <Stepper value={personnes} min={range.min} max={range.max} onChange={setPersonnes} />
          </Section>
        ) : null}

        <Section title="L'humeur du soir" hint={`Une ou plusieurs : ${data.max} envies en tout avec les options secrètes.`}>
          <OptionGrid>
            {moods.map((m) => (
              <OptionCard key={m.value} label={m.label} icon={m.icon} emoji={m.emoji} selected={chosenMoods.includes(m.value)}
                disabled={!chosenMoods.includes(m.value) && chosenMoods.length + secrets.length >= data.max}
                onPress={() => toggleMood(m.value)} />
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

        <Section
          title="Les options secrètes"
          hint={room > 0 ? `Jusqu'à ${room}, glissées dans le programme.` : `Vos humeurs prennent les ${data.max} envies : retirez-en une pour en glisser.`}>
          <OptionGrid>
            {others.map((o) => (
              <OptionCard key={o.value} label={o.label} icon={o.icon} emoji={o.emoji} selected={secrets.includes(o.value)}
                tint={squad ? 'secret' : undefined}
                disabled={!secrets.includes(o.value) && secrets.length >= room}
                onPress={() => toggleSecret(o.value)} />
            ))}
          </OptionGrid>
        </Section>

        {/* A band goes home: no hotel nor love room for it. */}
        {squad ? null : (
          <Section title="Et quand la nuit tombe ?" hint="Découcher : une nuit à l'hôtel ou dans une love room.">
            <OptionGrid>
              {NIGHTS.map((o) => (
                <OptionCard key={String(o.value)} label={o.label} icon={o.icon} selected={night.decoucher === o.value}
                  onPress={() => setNight((n) => ({ ...n, decoucher: o.value }))} />
              ))}
            </OptionGrid>
          </Section>
        )}

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

        <Section
          title={squad ? 'Le budget par personne' : 'Le budget du soir'}
          hint={squad ? 'Sans choix : 60 € chacun.' : profile ? 'Sans choix : le budget habituel de votre profil.' : 'Sans choix : 120 €.'}>
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

        {squad && data.eviter ? (
          <Section title="Ce que la bande ne veut pas" hint="Aucune étape ne le proposera. Autant de réponses que vous voulez.">
            <OptionGrid>
              {data.eviter.map((o) => (
                <OptionCard key={o.value} label={o.label} desc={o.desc} icon={o.icon} emoji={o.emoji} selected={eviter.includes(o.value)}
                  onPress={() => toggleEviter(o.value)} />
              ))}
            </OptionGrid>
          </Section>
        ) : null}

        <DayField label="Le jour J" value={night.day} onChange={(day) => setNight((n) => ({ ...n, day }))} />

        {status === 'composing' ? <Waiting title="La nuit ourdit ses secrets…" lines={COMPOSING_LINES} /> : null}
        {status === 'error' && <ThemedText themeColor="danger">L&apos;intrigue n&apos;a pas pu être tramée. Réessayez dans un instant.</ThemedText>}
        <PrimaryButton wide disabled={!ready || status === 'composing'} onPress={compose}>
          {status === 'composing'
            ? `Le ${longDay(night.day)} se trame en secret…`
            : night.diner === null ? 'Dîner ou pas ? Dites-le-nous' : squad ? `Tramer la virée à ${personnes}` : 'Tramer nos intrigues'}
        </PrimaryButton>
      </Screen>
    </PaletteProvider>
  );
}

// The first choice: Secret Date, for two, or Secret Squad, for a band of friends — each in its own look.
function FormulePicker({ turn, onPick }: { turn: boolean; onPick: (formule: Formule) => void }) {
  return (
    <Screen gap={Spacing.three}>
      <PageCard
        badge={turn ? 'À votre tour' : 'Nouvelle intrigue'}
        title="Quelle soirée tramer ?"
        text="À deux, ou toute la bande : la même mécanique, des indices jusqu'au jour J, et une soirée à part." />
      <FormuleCard
        name="date"
        title="Une soirée à deux"
        text="Pour votre moitié : un tête-à-tête secret, du premier verre à la dernière étape."
        onPress={() => onPick('duo')} />
      <FormuleCard
        name="squad"
        title="Une soirée entre potes"
        text="EVJF, EVG, anniversaire ou juste l'envie : une virée secrète de 2 à 10, des activités pour toute la bande."
        onPress={() => onPick('squad')} />
    </Screen>
  );
}

function FormuleCard({ name, title, text, onPress }: { name: 'date' | 'squad'; title: string; text: string; onPress: () => void }) {
  return (
    <PaletteProvider name={name}>
      <FormuleCardBody title={title} text={text} brand={Brands[name]} onPress={onPress} />
    </PaletteProvider>
  );
}

function FormuleCardBody({ title, text, brand, onPress }: { title: string; text: string; brand: string; onPress: () => void }) {
  const theme = useTheme();
  return (
    <IntrigueCard onPress={onPress} align="start" label={`${brand} : ${title}`}>
      <View style={styles.formuleHead}>
        <CardEmblem />
        <ThemedText style={[styles.formuleBrand, { color: theme.gold }]}>{brand}</ThemedText>
      </View>
      <ThemedText style={styles.formuleTitle}>{title}</ThemedText>
      <ThemedText style={{ color: theme.creamSoft }}>{text}</ThemedText>
      <ThemedText type="smallBold" themeColor="accentInk">Choisir →</ThemedText>
    </IntrigueCard>
  );
}

// How many: a minus, the figure, a plus.
function Stepper({ value, min, max, onChange }: { value: number; min: number; max: number; onChange: (value: number) => void }) {
  const theme = useTheme();
  const step = (by: number) => onChange(Math.min(max, Math.max(min, value + by)));
  const button = (by: number, label: string, disabled: boolean) => (
    <Pressable
      onPress={() => step(by)}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={by > 0 ? 'Une personne de plus' : 'Une personne de moins'}
      style={[styles.stepButton, { borderColor: theme.accentFaint, backgroundColor: theme.velvet }, disabled && styles.stepDisabled]}>
      <ThemedText style={[styles.stepSign, { color: theme.accent }]}>{label}</ThemedText>
    </Pressable>
  );
  return (
    <View style={styles.stepper}>
      {button(-1, '−', value <= min)}
      <View style={styles.stepValue} accessibilityLabel={`${value} personnes`}>
        <ThemedText style={[styles.stepFigure, { color: theme.gold }]}>{value}</ThemedText>
        <ThemedText type="small" themeColor="textSecondary">personnes</ThemedText>
      </View>
      {button(1, '+', value >= max)}
    </View>
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
  formuleHead: { flexDirection: 'row', alignItems: 'center', gap: Spacing.two },
  formuleBrand: { fontFamily: Fonts.headingBold, fontSize: 20, lineHeight: 24, letterSpacing: 0.4 },
  formuleTitle: { fontFamily: Fonts.headingItalic, fontSize: 30, lineHeight: 35, marginTop: Spacing.two },
  stepper: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: Spacing.four, paddingVertical: Spacing.one },
  stepButton: { width: 44, height: 44, borderRadius: 22, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  stepDisabled: { opacity: 0.35 },
  stepSign: { fontSize: 24, lineHeight: 28 },
  stepValue: { alignItems: 'center', minWidth: 80 },
  stepFigure: { fontFamily: Fonts.sansThin, fontSize: 40, lineHeight: 46 },
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

import * as Linking from 'expo-linking';
import { type Href, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { Platform, Pressable, Share, StyleSheet, View } from 'react-native';

import { PrimaryButton, TextButton, TextLink } from '@/components/buttons';
import { Gauge } from '@/components/gauge';
import { KeyDates } from '@/components/key-dates';
import { ProgrammeCard } from '@/components/programme';
import { PageCard } from '@/components/intrigue-card';
import { Screen } from '@/components/screen';
import { TextField } from '@/components/text-field';
import { ThemedText } from '@/components/themed-text';
import { Veil } from '@/components/veil';
import { Fonts, Radius, Spacing } from '@/constants/theme';
import { useLook, useTheme } from '@/hooks/use-theme';
import { EARNED, LEVELS, myComplicity, type Complicity } from '@/lib/complicity';
import { isoDay, longDay } from '@/lib/dates';
import {
  answerQuiz, answerToday, badgesFor, defiDone, joinDuo, leaveDuo, weeksQuiz, myDuo, openDuo, pairedAnswers, partnerName,
  myProgramme, todaysQuestion, verdict, weeksDefi, type Duo, type Programme, type Jour, type Paired, type Quiz, type QuizQuestion, type Semaine,
} from '@/lib/duo';
import { keyDates, type KeyDate } from '@/lib/occasions';
import { useCouple } from '@/hooks/use-couple';

type State = { duo: Duo | null; gauge: Complicity | null; jour: Jour | null; paired: Paired[]; quiz: Quiz | null; semaine: Semaine | null; dates: KeyDate[]; programme: Programme | null };

// The paliers of the day's questions, from the lightest: a duo climbs them answer after answer.
const PALIERS = { 1: 'Pour rire', 2: 'Se raconter', 3: 'Nous deux', 4: 'À cœur ouvert' } as const;


// « Mon couple » (docs/complicite.md): the complicity gauge and how it climbs, the day's question — each reads the
// other's answer once their own is sealed —, the days both answered, and the duo itself: formed by an evening for two
// or by a code sent to the other (a link `/couple?duo=<code>` fills it in), left from the foot of the page.
export default function CoupleScreen() {
  const { duo: given } = useLocalSearchParams<{ duo?: string }>();
  const [state, setState] = useState<State | 'loading' | 'error'>('loading');
  const { userId } = useCouple();

  const load = useCallback(
    () => Promise.all([myDuo(), myComplicity().catch(() => null)])
      .then(async ([duo, gauge]) => {
        const [jour, paired, quiz, semaine, dates, programme] = duo?.complete
          ? await Promise.all([todaysQuestion(), pairedAnswers(isoDay(new Date())), weeksQuiz(), weeksDefi(), keyDates(), myProgramme()])
          : [null, [], null, null, [], null];
        return { duo, gauge, jour, paired, quiz, semaine, dates, programme };
      })
      .then(setState, () => setState('error')),
    [],
  );
  useEffect(() => {
    load();
  }, [load]);

  if (state === 'loading' || state === 'error') {
    return (
      <Screen>
        <PageCard back title="Mon couple" text={state === 'error' ? "La page n'a pas pu être ouverte. Réessayez dans un instant." : undefined} />
        {state === 'loading' ? <ThemedText themeColor="textSecondary">On rassemble vos secrets…</ThemedText> : null}
      </Screen>
    );
  }
  const { duo, gauge, jour, paired, quiz, semaine, dates, programme } = state;
  const partner = partnerName(duo?.partner ?? null);
  return (
    <Screen gap={Spacing.four}>
      <PageCard
        back
        badge={duo?.complete ? 'Duo' : undefined}
        title="Mon couple"
        text={duo?.complete
          ? `Vous et ${partner}. Chaque soirée, chaque page du Livre, chaque question partagée fait grandir votre complicité.`
          : 'Ici, vous jouez à deux : une question chaque jour, des défis, des quiz. Formez d’abord votre duo.'}
      />
      {gauge ? (
        <View style={styles.block}>
          <Gauge gauge={gauge} />
          <Earned />
          <Unlocks gauge={gauge} />
        </View>
      ) : null}
      {duo?.complete && jour ? <TodaysQuestion jour={jour} partner={partner} onAnswered={load} /> : null}
      {duo?.complete && semaine ? <WeeksDefi semaine={semaine} partner={partner} onDone={load} /> : null}
      {duo?.complete && quiz ? <MonthsQuiz quiz={quiz} partner={partner} onAnswered={load} /> : null}
      {duo?.complete && programme ? <ProgrammeCard programme={programme} partner={partner} onChange={load} /> : null}
      {duo?.complete && userId ? <KeyDates duo={duo} dates={dates} me={userId} partner={partner} onChange={load} /> : null}
      {paired.length ? <PairedDays paired={paired} partner={partner} /> : null}
      {duo?.complete ? null : <FormDuo duo={duo} given={given} onJoined={load} />}
      {duo ? <LeaveDuo complete={duo.complete} partner={partner} onLeft={load} /> : null}
    </Screen>
  );
}

function Earned() {
  return (
    <View style={styles.earned}>
      {EARNED.map((line) => <ThemedText key={line} type="small" themeColor="textSecondary">✦ {line}</ThemedText>)}
    </View>
  );
}

// What each level unlocks, reached or still ahead; « Minuit » chosen here once unlocked.
function Unlocks({ gauge }: { gauge: Complicity }) {
  const theme = useTheme();
  const { look, setLook } = useLook();
  return (
    <View style={[styles.card, { backgroundColor: theme.backgroundElement, borderColor: theme.line }]}>
      <ThemedText type="eyebrow">Vos déblocages</ThemedText>
      {LEVELS.filter((l) => l.unlock).map((l) => {
        const open = gauge.unlocked.includes(l.unlock!.key);
        return (
          <View key={l.name} style={styles.unlock}>
            <ThemedText style={{ color: open ? theme.gold : theme.textSecondary }}>{open ? '✦' : '·'}</ThemedText>
            <View style={styles.unlockText}>
              <ThemedText type="smallBold" style={{ color: open ? theme.cream : theme.textSecondary }}>{l.unlock!.label}</ThemedText>
              <ThemedText type="small" themeColor="textSecondary">{open ? `Débloqué à « ${l.name} »` : `À « ${l.name} », ${l.from} points`}</ThemedText>
            </View>
          </View>
        );
      })}
      {gauge.unlocked.includes('theme-minuit') ? (
        <TextButton onPress={() => setLook(look === 'minuit' ? 'date' : 'minuit')}>
          {look === 'minuit' ? 'Revenir au thème émeraude' : 'Passer au thème « Minuit »'}
        </TextButton>
      ) : null}
    </View>
  );
}

const GENRES = { geste: 'Un geste', rituel: 'Un rituel', sortie: 'Une sortie', jeu: 'Un jeu' } as const;

// The week's défi: ticked by each, done for the duo once both did; an outing opens the evening form on its wish. The
// badges of the défis both ticked.
function WeeksDefi({ semaine, partner, onDone }: { semaine: Semaine; partner: string; onDone: () => void }) {
  const theme = useTheme();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const { defi } = semaine;
  const both = semaine.fait_par_moi && semaine.fait_par_l_autre;
  const badges = badgesFor(semaine.valides);
  async function done() {
    setBusy(true);
    setError('');
    try {
      await defiDone();
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }
  const envie: Href | null = defi.envie ? { pathname: '/soiree', params: { formule: 'duo', envies: defi.envie } } : null;
  const status = both
    ? 'Défi relevé à deux. Rendez-vous lundi pour le suivant.'
    : semaine.fait_par_moi
      ? `Fait de votre côté. Il comptera dès que ${partner} l’aura coché.`
      : semaine.fait_par_l_autre ? `${partner} l’a relevé. À vous !` : 'À relever avant dimanche soir : chacun le coche une fois fait.';
  return (
    <View testID="defi-de-la-semaine" style={[styles.card, { backgroundColor: theme.velvet, borderColor: theme.accentSoft }]}>
      <View style={styles.head}>
        <ThemedText type="eyebrow">Le défi de la semaine</ThemedText>
        <ThemedText type="small" themeColor="textSecondary">{GENRES[defi.genre]}</ThemedText>
      </View>
      <ThemedText style={[styles.question, { color: theme.cream }]}>{defi.titre}</ThemedText>
      <ThemedText style={{ color: theme.creamSoft }}>{defi.texte}</ThemedText>
      {envie ? <TextLink href={envie}>Composer une soirée pour ce défi →</TextLink> : null}
      <ThemedText type="small" themeColor="textSecondary">{status}</ThemedText>
      {semaine.fait_par_moi ? null : <PrimaryButton wide busy={busy} onPress={done}>C’est fait</PrimaryButton>}
      {error ? <ThemedText type="small" themeColor="danger">{error}</ThemedText> : null}
      <View style={styles.badges}>
        <ThemedText type="small" themeColor="textSecondary">
          {semaine.valides
            ? `${semaine.valides} défi${semaine.valides > 1 ? 's' : ''} relevé${semaine.valides > 1 ? 's' : ''} à deux`
            : 'Aucun défi relevé à deux pour l’instant'}
        </ThemedText>
        {badges.map((b) => (
          <View key={b} style={[styles.badge, { borderColor: theme.goldSoft }]}>
            <ThemedText type="small" style={{ color: theme.gold }}>{b}</ThemedText>
          </View>
        ))}
      </View>
    </View>
  );
}

// The week's quiz: the next question not answered — one's own answer, then the guess of the other's —, the questions
// both answered shown with who guessed right, and the score.
function MonthsQuiz({ quiz, partner, onAnswered }: { quiz: Quiz; partner: string; onAnswered: () => void }) {
  const theme = useTheme();
  const next = quiz.questions.find((q) => q.moi === null) ?? null;
  const answered = quiz.questions.filter((q) => q.moi !== null).length;
  const revealed = quiz.questions.filter((q) => q.moi !== null && q.sien_moi !== null);
  return (
    <View testID="quiz-de-la-semaine" style={[styles.card, { backgroundColor: theme.velvet, borderColor: theme.accentSoft }]}>
      <View style={styles.head}>
        <ThemedText type="eyebrow">Le quiz de la semaine</ThemedText>
        <ThemedText type="small" themeColor="textSecondary">{`${answered} sur ${quiz.questions.length}`}</ThemedText>
      </View>
      <ThemedText style={[styles.question, { color: theme.cream }]}>{quiz.serie.titre}</ThemedText>
      <ThemedText type="small" style={{ color: theme.creamSoft }}>
        {`${quiz.serie.accroche}. Répondez pour vous, puis devinez ce que ${partner} a répondu.`}
      </ThemedText>
      {next ? <QuizStep key={next.id} question={next} partner={partner} onAnswered={onAnswered} /> : (
        <ThemedText type="small" themeColor="textSecondary">Toutes vos réponses sont données. Le prochain quiz arrive lundi.</ThemedText>
      )}
      {revealed.length ? (
        <View style={styles.block}>
          <ThemedText type="smallBold" style={{ color: theme.gold }}>
            {`Vos bonnes devinettes : ${quiz.score.moi} · celles de ${partner} : ${quiz.score.sien}`}
          </ThemedText>
          {revealed.length === quiz.questions.length ? (
            <ThemedText testID="verdict" style={{ color: theme.cream }}>{verdict(quiz.score.moi + quiz.score.sien)}</ThemedText>
          ) : null}
          {revealed.map((q) => (
            <View key={q.id} style={styles.revealed}>
              <ThemedText type="small" style={{ color: theme.cream }}>{q.question}</ThemedText>
              <ThemedText type="small" themeColor="textSecondary">
                {`Vous : ${q.choix[q.moi!]}${q.sien_devine === q.moi ? ` (deviné par ${partner})` : ''} · ${partner} : ${q.choix[q.sien_moi!]}${q.devine === q.sien_moi ? ' (deviné !)' : ''}`}
              </ThemedText>
            </View>
          ))}
        </View>
      ) : null}
    </View>
  );
}

function QuizStep({ question, partner, onAnswered }: { question: QuizQuestion; partner: string; onAnswered: () => void }) {
  const [mine, setMine] = useState<number | null>(null);
  const [guess, setGuess] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function send() {
    if (mine === null || guess === null) return;
    setBusy(true);
    setError('');
    try {
      await answerQuiz(question.id, mine, guess);
      onAnswered();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }
  return (
    <View style={styles.block}>
      <ThemedText style={styles.quizQuestion}>{question.question}</ThemedText>
      <Choices label="Pour vous" choices={question.choix} chosen={mine} onChoose={setMine} />
      <Choices label={`Pour ${partner}, à votre avis`} choices={question.choix} chosen={guess} onChoose={setGuess} />
      <PrimaryButton wide disabled={mine === null || guess === null} busy={busy} onPress={send}>Valider</PrimaryButton>
      {question.sienne_donnee ? <ThemedText type="small" themeColor="textSecondary">{`${partner} a déjà répondu à celle-ci.`}</ThemedText> : null}
      {error ? <ThemedText type="small" themeColor="danger">{error}</ThemedText> : null}
    </View>
  );
}

function Choices({ label, choices, chosen, onChoose }: { label: string; choices: string[]; chosen: number | null; onChoose: (i: number) => void }) {
  const theme = useTheme();
  return (
    <View style={styles.block} accessibilityRole="radiogroup" accessibilityLabel={label}>
      <ThemedText type="eyebrow" style={styles.label}>{label}</ThemedText>
      <View style={styles.choices}>
        {choices.map((c, i) => (
          <Pressable
            key={c}
            onPress={() => onChoose(i)}
            accessibilityRole="radio"
            accessibilityState={{ checked: chosen === i }}
            style={[styles.choice, { borderColor: chosen === i ? theme.accent : theme.accentHair, backgroundColor: chosen === i ? theme.backgroundSelected : 'transparent' }]}>
            <ThemedText type="small" style={{ color: chosen === i ? theme.accentInk : theme.cream }}>{c}</ThemedText>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

// The day's question: answered and sealed, then the other's answer — or, until they give theirs, a veiled leaf.
function TodaysQuestion({ jour, partner, onAnswered }: { jour: Jour; partner: string; onAnswered: () => void }) {
  const theme = useTheme();
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function seal() {
    setBusy(true);
    setError('');
    try {
      await answerToday(text);
      onAnswered();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <View testID="question-du-jour" style={[styles.card, { backgroundColor: theme.velvet, borderColor: theme.accentSoft }]}>
      <View style={styles.head}>
        <ThemedText type="eyebrow">La question du jour</ThemedText>
        <ThemedText type="small" themeColor="textSecondary">{PALIERS[jour.question.profondeur]}</ThemedText>
      </View>
      <ThemedText testID="question-texte" style={[styles.question, { color: theme.cream }]}>{jour.question.texte}</ThemedText>
      {jour.mienne ? (
        <>
          <Answer label="Votre réponse" text={jour.mienne} />
          {jour.sienne ? (
            <Answer label={`La réponse de ${partner}`} text={jour.sienne} />
          ) : (
            <View style={styles.answer}>
              <ThemedText type="eyebrow" style={styles.label}>{`La réponse de ${partner}`}</ThemedText>
              <Veil widths={['88%', '60%']} />
              <ThemedText type="small" style={{ color: theme.creamSoft }}>
                {`Pas encore donnée : elle apparaîtra ici dès que ${partner} aura scellé la sienne.`}
              </ThemedText>
            </View>
          )}
        </>
      ) : (
        <>
          <ThemedText type="small" style={{ color: theme.creamSoft }}>
            {jour.sienne_donnee
              ? `${partner} a répondu. Scellez votre réponse pour lire la sienne.`
              : `Répondez, puis lisez celle de ${partner} quand elle sera scellée.`}
          </ThemedText>
          <TextField
            multiline
            value={text}
            onChangeText={setText}
            maxLength={1000}
            accessibilityLabel="Votre réponse"
            placeholder="Votre réponse, en toute sincérité…"
            placeholderTextColor={theme.creamFaint}
            style={[styles.input, { backgroundColor: theme.background, color: theme.cream }]}
          />
          <PrimaryButton wide disabled={!text.trim()} busy={busy} onPress={seal}>{busy ? 'On scelle votre réponse…' : 'Sceller ma réponse'}</PrimaryButton>
          {error ? <ThemedText type="small" themeColor="danger">{error}</ThemedText> : null}
        </>
      )}
    </View>
  );
}

function Answer({ label, text }: { label: string; text: string }) {
  const theme = useTheme();
  return (
    <View style={styles.answer}>
      <ThemedText type="eyebrow" style={styles.label}>{label}</ThemedText>
      <ThemedText type="clue" style={{ color: theme.cream }}>« {text} »</ThemedText>
    </View>
  );
}

// The days of the week gone that both answered: the question, then the two answers.
function PairedDays({ paired, partner }: { paired: Paired[]; partner: string }) {
  const theme = useTheme();
  return (
    <View style={styles.block}>
      <ThemedText type="eyebrow">Vos derniers jours</ThemedText>
      {paired.map((p) => (
        <View key={p.day} style={[styles.card, { backgroundColor: theme.backgroundElement, borderColor: theme.line }]}>
          <ThemedText type="small" themeColor="textSecondary">{longDay(p.day)}</ThemedText>
          <ThemedText style={[styles.past, { color: theme.cream }]}>{p.question}</ThemedText>
          <Answer label="Vous" text={p.mienne} />
          <Answer label={partner} text={p.sienne} />
        </View>
      ))}
    </View>
  );
}

// No duo yet, or one waiting for its second: the code to send (a link filling it in), or the other's code to enter.
function FormDuo({ duo, given, onJoined }: { duo: Duo | null; given?: string; onJoined: () => void }) {
  const theme = useTheme();
  const [code, setCode] = useState(given ?? '');
  const [mine, setMine] = useState(duo?.code ?? null);
  const [busy, setBusy] = useState<'open' | 'join' | null>(null);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);

  async function run(which: 'open' | 'join') {
    setBusy(which);
    setError('');
    try {
      if (which === 'open') setMine(await openDuo());
      else {
        await joinDuo(code);
        onJoined();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function send(link: string) {
    if (Platform.OS === 'web') {
      await navigator.clipboard?.writeText(link);
      setCopied(true);
    } else {
      await Share.share({ message: `Formons notre duo sur Secret Date : ${link}` });
    }
  }

  const link = mine ? Linking.createURL('/couple', { queryParams: { duo: mine } }) : null;
  return (
    <View style={[styles.card, { backgroundColor: theme.backgroundElement, borderColor: theme.accentSoft }]}>
      <ThemedText type="eyebrow">Former votre duo</ThemedText>
      <ThemedText type="small" style={{ color: theme.creamSoft }}>
        Il se forme tout seul quand votre moitié rejoint une soirée à deux. Sinon, envoyez-lui votre code, ou entrez le sien.
      </ThemedText>
      {mine && link ? (
        <View style={styles.block}>
          <ThemedText type="small" themeColor="textSecondary">Votre code</ThemedText>
          <ThemedText testID="code-duo" style={[styles.code, { color: theme.gold }]}>{mine}</ThemedText>
          <PrimaryButton wide onPress={() => send(link)}>{copied ? 'Lien copié' : Platform.OS === 'web' ? 'Copier le lien' : 'Envoyer le lien'}</PrimaryButton>
        </View>
      ) : (
        <PrimaryButton wide busy={busy === 'open'} onPress={() => run('open')}>Obtenir mon code</PrimaryButton>
      )}
      <View style={styles.block}>
        <ThemedText type="small" themeColor="textSecondary">Le code de votre moitié</ThemedText>
        <TextField
          value={code}
          onChangeText={setCode}
          autoCapitalize="none"
          autoCorrect={false}
          accessibilityLabel="Le code de votre moitié"
          placeholder="8 caractères"
          placeholderTextColor={theme.creamFaint}
          style={[styles.field, { backgroundColor: theme.background, color: theme.cream }]}
        />
        <PrimaryButton wide disabled={!code.trim()} busy={busy === 'join'} onPress={() => run('join')}>Rejoindre son duo</PrimaryButton>
      </View>
      {error ? <ThemedText type="small" themeColor="danger">{error}</ThemedText> : null}
    </View>
  );
}

// Leaving dissolves the duo, its answers with it: asked twice.
function LeaveDuo({ complete, partner, onLeft }: { complete: boolean; partner: string; onLeft: () => void }) {
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  if (!confirm) {
    return (
      <View style={styles.centerRow}>
        <TextButton onPress={() => setConfirm(true)}>{complete ? 'Quitter le duo' : 'Annuler mon code'}</TextButton>
      </View>
    );
  }
  return (
    <View style={styles.block}>
      <ThemedText type="small" themeColor="textSecondary" style={styles.center}>
        {complete ? `Vos réponses avec ${partner} seront effacées. Vos soirées et votre Livre restent.` : 'Votre code ne servira plus.'}
      </ThemedText>
      <View style={styles.row}>
        <TextButton onPress={() => setConfirm(false)}>Annuler</TextButton>
        <TextButton busy={busy} onPress={() => {
          setBusy(true);
          leaveDuo().then(onLeft, () => setBusy(false));
        }}>{complete ? 'Quitter le duo' : 'Annuler le code'}</TextButton>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  block: { gap: Spacing.two },
  earned: { gap: 2, paddingHorizontal: Spacing.one },
  card: { gap: Spacing.three, padding: Spacing.three + 2, borderRadius: Radius.tile, borderWidth: 1 },
  head: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', gap: Spacing.two },
  question: { fontFamily: Fonts.headingItalic, fontSize: 24, lineHeight: 30 },
  past: { fontFamily: Fonts.headingItalic, fontSize: 19, lineHeight: 24 },
  answer: { gap: Spacing.one },
  label: { fontSize: 10, letterSpacing: 2.5 },
  input: {
    fontFamily: Fonts.headingItalic, fontSize: 18, lineHeight: 24, minHeight: 96, padding: Spacing.three,
    borderRadius: Radius.field, textAlignVertical: 'top',
  },
  field: { fontFamily: Fonts.sans, fontSize: 17, padding: Spacing.three, borderRadius: Radius.field, letterSpacing: 2 },
  code: { fontFamily: Fonts.sansBold, fontSize: 28, letterSpacing: 4 },
  center: { textAlign: 'center' },
  centerRow: { alignItems: 'center' },
  row: { flexDirection: 'row', justifyContent: 'center', gap: Spacing.four },
  unlock: { flexDirection: 'row', gap: Spacing.two, alignItems: 'flex-start' },
  unlockText: { flex: 1, gap: 2 },
  badges: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: Spacing.two },
  badge: { borderWidth: 1, borderRadius: Radius.pill, paddingHorizontal: Spacing.two + 2, paddingVertical: 2 },
  quizQuestion: { fontFamily: Fonts.heading, fontSize: 20, lineHeight: 25 },
  choices: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.two },
  choice: { borderWidth: 1, borderRadius: Radius.pill, paddingHorizontal: Spacing.three, paddingVertical: Spacing.two },
  revealed: { gap: 2 },
});

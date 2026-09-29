import { useLocalSearchParams } from 'expo-router';
import { type ReactNode, useEffect, useState } from 'react';
import { ScrollView, StyleSheet, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { AccountNav } from '@/components/account-nav';
import { PrimaryButton, PrimaryLink, TextButton } from '@/components/buttons';
import { DayField } from '@/components/day-field';
import { OptionButton, OptionRow } from '@/components/option-button';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { MaxContentWidth, Night, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { accountProfile, currentUser, saveAccountProfile } from '@/lib/account';
import { getProfile, getQuiz, saveProfile, type Question, type QuizData, type SavedProfile } from '@/lib/api';
import { longDay, nextFriday } from '@/lib/dates';
import { rememberProfile } from '@/lib/local-store';

type Phase = 'loading' | 'quiz' | 'saving' | 'error' | 'reveal';

export default function ProfilScreen() {
  const { p } = useLocalSearchParams<{ p?: string }>();
  const [quiz, setQuiz] = useState<QuizData | null>(null);
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [result, setResult] = useState<SavedProfile | null>(null);
  const [phase, setPhase] = useState<Phase>('loading');

  async function submit(finalAnswers: Record<string, unknown>) {
    setAnswers(finalAnswers);
    setPhase('saving');
    try {
      const saved = await saveProfile(finalAnswers);
      await rememberProfile(saved.id);
      // Best-effort: a signed-in couple also keeps their profile on their account, so it
      // follows them to another device. The local copy above always works, account or not.
      currentUser().then((user) => user && saveAccountProfile(finalAnswers, saved.profile).catch(() => {}));
      setResult(saved);
      setPhase('reveal');
    } catch {
      setPhase('error');
    }
  }

  useEffect(() => {
    (async () => {
      const data = await getQuiz();
      setQuiz(data);
      if (p) {
        try {
          const found = await getProfile(p);
          setAnswers(found.answers);
          setResult(found);
          setPhase('reveal');
          return;
        } catch {
          // Unknown id: fall through to a fresh quiz.
        }
      } else {
        const user = await currentUser().catch(() => null);
        if (user) {
          const found = await accountProfile().catch(() => null);
          if (found) return submit(found.answers);
        }
      }
      setPhase('quiz');
    })();
  }, [p]);


  if (phase === 'loading' || phase === 'saving' || !quiz) {
    return (
      <Screen>
        <ThemedText themeColor="textSecondary">
          {phase === 'saving' ? 'On dessine votre profil…' : 'Chargement…'}
        </ThemedText>
      </Screen>
    );
  }

  if (phase === 'error') {
    return (
      <Screen>
        <ThemedText style={{ color: '#ff5c72' }}>Le profil n&apos;a pas pu être enregistré. Réessayez.</ThemedText>
        <PrimaryLink href="/profil">Réessayer</PrimaryLink>
      </Screen>
    );
  }

  if (phase === 'reveal' && result) {
    return (
      <Screen>
        <Reveal quiz={quiz} answers={answers} profile={result} onRestart={() => { setIndex(0); setResult(null); setPhase('quiz'); }} />
      </Screen>
    );
  }

  const q = quiz.questions[index];
  const isLast = index + 1 >= quiz.questions.length;

  function goNext(finalAnswers: Record<string, unknown> = answers) {
    if (isLast) submit(finalAnswers);
    else setIndex((i) => i + 1);
  }

  return (
    <Screen>
      <AccountNav />
      <View style={styles.progressTrack}>
        <View style={[styles.progressBar, { width: `${(index / quiz.questions.length) * 100}%` }]} />
      </View>
      <ThemedText type="small" themeColor="textSecondary">
        Question {index + 1} sur {quiz.questions.length}
      </ThemedText>
      <ThemedText type="title">{q.question}</ThemedText>
      {q.hint ? <ThemedText themeColor="textSecondary">{q.hint}</ThemedText> : null}
      <QuestionBody
        question={q}
        value={answers[q.id]}
        onChange={(value) => setAnswers((a) => ({ ...a, [q.id]: value }))}
        onAnswer={(value) => goNext({ ...answers, [q.id]: value })}
      />
      <View style={styles.nav}>
        {index > 0 ? <TextButton onPress={() => setIndex((i) => i - 1)}>← Retour</TextButton> : <View />}
        {q.kind !== 'single' && q.kind !== 'scale' && (
          <PrimaryButton disabled={!answered(q, answers[q.id])} onPress={() => goNext()}>
            Suivant
          </PrimaryButton>
        )}
      </View>
    </Screen>
  );
}

function answered(q: Question, value: unknown) {
  if (q.kind === 'multi' || q.kind === 'text') return true; // "none" is an answer
  if (q.kind === 'date') return !!value;
  return value != null;
}

function QuestionBody({
  question,
  value,
  onChange,
  onAnswer,
}: {
  question: Question;
  value: unknown;
  onChange: (value: unknown) => void;
  onAnswer: (value: unknown) => void;
}) {
  const theme = useTheme();
  if (question.kind === 'single' || question.kind === 'scale') {
    return (
      <OptionRow>
        {(question.options ?? []).map((o) => (
          <OptionButton
            key={String(o.value)}
            label={o.label ?? String(o.value)}
            emoji={o.emoji}
            selected={value === o.value}
            onPress={() => onAnswer(o.value)}
          />
        ))}
      </OptionRow>
    );
  }
  if (question.kind === 'multi') {
    const chosen = new Set((value as string[] | undefined) ?? []);
    return (
      <OptionRow>
        {(question.options ?? []).map((o) => (
          <OptionButton
            key={String(o.value)}
            label={o.label ?? String(o.value)}
            emoji={o.emoji}
            selected={chosen.has(o.value as string)}
            disabled={!chosen.has(o.value as string) && !!question.max && chosen.size >= question.max}
            onPress={() => {
              const next = new Set(chosen);
              if (next.has(o.value as string)) next.delete(o.value as string);
              else next.add(o.value as string);
              onChange([...next]);
            }}
          />
        ))}
      </OptionRow>
    );
  }
  if (question.kind === 'date') {
    return <DayField value={(value as string) || nextFriday()} onChange={onChange} />;
  }
  return (
    <TextInput
      value={(value as string) || ''}
      onChangeText={onChange}
      placeholder="Léa & Sam"
      maxLength={80}
      style={[styles.input, { borderColor: theme.line, backgroundColor: theme.backgroundElement, color: theme.text }]}
    />
  );
}

function Reveal({
  quiz,
  answers,
  profile,
  onRestart,
}: {
  quiz: QuizData;
  answers: Record<string, unknown>;
  profile: SavedProfile;
  onRestart: () => void;
}) {
  const p = profile.profile;
  const eviter = quiz.questions.find((q) => q.id === 'eviter');
  const chosen = (answers.eviter as string[] | undefined) ?? [];
  const never = chosen.map((v) => eviter?.options?.find((o) => o.value === v)).filter((o): o is NonNullable<typeof o> => !!o);
  return (
    <View style={[styles.persona, { backgroundColor: Night.background, borderColor: Night.line }]}>
      <ThemedText style={[styles.eyebrow, { color: Night.gold }]}>{p.names ? `${p.names}, vous êtes…` : 'Vous êtes…'}</ThemedText>
      <ThemedText type="subtitle" style={{ color: Night.text }}>{p.persona.name}</ThemedText>
      <ThemedText style={{ color: Night.muted }}>{p.persona.text}</ThemedText>
      <OptionRow>
        {p.vibes.map((v, i) => (
          <ThemedText key={v} style={[styles.tag, { backgroundColor: i % 3 === 0 ? Night.accent : i % 3 === 1 ? Night.mint : Night.line, color: i % 3 === 2 ? Night.gold : Night.text }]}>
            {quiz.vibes[v] || v}
          </ThemedText>
        ))}
      </OptionRow>
      <View style={styles.facts}>
        <Fact label="première sortie" value={p.first_day ? longDay(p.first_day) : 'Bientôt'} />
        <Fact label="pour une soirée type" value={p.budget >= 350 ? 'sans compter' : `≈ ${p.budget} €`} />
        <View style={styles.factItem}>
          <ThemedText style={{ color: Night.text, fontSize: 16 }}>Audace</ThemedText>
          <View style={[styles.meterTrack, { backgroundColor: Night.line }]}>
            <View style={[styles.meterBar, { width: `${p.audace * 100}%`, backgroundColor: Night.gold }]} />
          </View>
        </View>
      </View>
      {never.length > 0 && (
        <ThemedText style={{ color: Night.muted, marginTop: Spacing.two }}>
          <ThemedText style={{ color: Night.text }}>Jamais : </ThemedText>
          {never.map((o) => (o.label ?? '').toLowerCase()).join(', ')}
        </ThemedText>
      )}
      <View style={styles.nav}>
        <TextButton onPress={onRestart}>Recommencer</TextButton>
        <PrimaryLink href={{ pathname: '/soiree', params: { p: profile.id } }}>Préparer une soirée</PrimaryLink>
      </View>
    </View>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <View style={[styles.factItem, { borderColor: Night.line }]}>
      <ThemedText style={{ color: Night.text, fontSize: 16 }}>{value}</ThemedText>
      <ThemedText type="small" style={{ color: Night.muted }}>{label}</ThemedText>
    </View>
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
  safeArea: { width: '100%', maxWidth: MaxContentWidth, paddingHorizontal: Spacing.four, paddingVertical: Spacing.three, gap: Spacing.three },
  progressTrack: { height: 6, borderRadius: 999, backgroundColor: '#e8dcf3', overflow: 'hidden' },
  progressBar: { height: '100%', backgroundColor: '#ff5c72' },
  nav: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: Spacing.three },
  input: { fontSize: 16, padding: 14, borderRadius: 12, borderWidth: 1.5 },
  persona: { gap: Spacing.two, padding: Spacing.four, borderRadius: 18 },
  eyebrow: { textTransform: 'uppercase', letterSpacing: 1, fontSize: 12 },
  tag: { borderRadius: 999, paddingVertical: 4, paddingHorizontal: 12, fontSize: 14, overflow: 'hidden' },
  facts: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.three, marginTop: Spacing.two },
  factItem: { flex: 1, minWidth: 130, gap: 4, borderTopWidth: 1, paddingTop: Spacing.two },
  meterTrack: { height: 8, borderRadius: 999, overflow: 'hidden', marginTop: 4 },
  meterBar: { height: '100%' },
});

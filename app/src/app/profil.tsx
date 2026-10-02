import { useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { PrimaryButton, PrimaryLink, TextButton } from '@/components/buttons';
import { DayField } from '@/components/day-field';
import { PageCard } from '@/components/intrigue-card';
import { OptionCard, OptionGrid } from '@/components/option-card';
import { PersonaCard } from '@/components/persona-card';
import { Screen } from '@/components/screen';
import { TextField } from '@/components/text-field';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { accountProfile, currentUser, saveAccountProfile } from '@/lib/account';
import { getQuiz, saveProfile, type Profile, type Question, type QuizData } from '@/lib/api';
import { nextFriday } from '@/lib/dates';
import { rememberedProfile, rememberProfile } from '@/lib/local-store';

type Phase = 'loading' | 'quiz' | 'saving' | 'error' | 'unreachable' | 'reveal';

export default function ProfilScreen() {
  // ?new=1: a blank quiz. ?modifier=1 (from the account): the quiz again, with the couple's answers already in it.
  const { new: isNew, modifier } = useLocalSearchParams<{ new?: string; modifier?: string }>();
  const theme = useTheme();
  const [quiz, setQuiz] = useState<QuizData | null>(null);
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [result, setResult] = useState<Profile | null>(null);
  const [phase, setPhase] = useState<Phase>('loading');

  async function submit(finalAnswers: Record<string, unknown>) {
    setAnswers(finalAnswers);
    setPhase('saving');
    try {
      const profile = await saveProfile(finalAnswers);
      await rememberProfile(finalAnswers, profile);
      // Best-effort: a signed-in couple also keeps their profile on their account, so it
      // follows them to another device. The local copy above always works, account or not.
      currentUser().then((user) => user && saveAccountProfile(finalAnswers, profile).catch(() => {}));
      setResult(profile);
      setPhase('reveal');
    } catch {
      setPhase('error');
    }
  }

  useEffect(() => {
    (async () => {
      let data: QuizData;
      try {
        data = await getQuiz();
      } catch {
        setPhase('unreachable');
        return;
      }
      setQuiz(data);
      if (!isNew) {
        const remembered = await rememberedProfile();
        if (remembered) {
          setAnswers(remembered.answers);
          if (!modifier) {
            setResult(remembered.profile);
            setPhase('reveal');
            return;
          }
        } else {
          const user = await currentUser().catch(() => null);
          const found = user ? await accountProfile().catch(() => null) : null;
          if (found && !modifier) return submit(found.answers);
          if (found) setAnswers(found.answers);
        }
      }
      setPhase('quiz');
    })();
  }, [isNew, modifier]);

  if (phase === 'unreachable') {
    return (
      <Screen>
        <ThemedText themeColor="danger">Le serveur ne répond pas. Vérifiez qu&apos;il est lancé (fenêtre « surprise - serveur »), puis réessayez.</ThemedText>
        <PrimaryLink href="/profil">Réessayer</PrimaryLink>
      </Screen>
    );
  }

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
        <ThemedText themeColor="danger">Le profil n&apos;a pas pu être enregistré. Réessayez.</ThemedText>
        <PrimaryLink href="/profil">Réessayer</PrimaryLink>
      </Screen>
    );
  }

  if (phase === 'reveal' && result) {
    return (
      <Screen>
        <PersonaCard profile={result} answers={answers} quiz={quiz}>
          <View style={styles.nav}>
            <TextButton onPress={() => { setIndex(0); setResult(null); setPhase('quiz'); }}>Recommencer</TextButton>
            <PrimaryLink href="/soiree">Lancer une intrigue</PrimaryLink>
          </View>
        </PersonaCard>
      </Screen>
    );
  }

  const q = quiz.questions[index];
  const isLast = index + 1 >= quiz.questions.length;

  function goNext(finalAnswers: Record<string, unknown> = answers) {
    // A date question shows next Friday until it's changed: left as is, that's the answer.
    const filled = q.kind === 'date' && !finalAnswers[q.id] ? { ...finalAnswers, [q.id]: nextFriday() } : finalAnswers;
    if (isLast) submit(filled);
    else {
      setAnswers(filled);
      setIndex((i) => i + 1);
    }
  }

  return (
    <Screen>
      <PageCard back badge={`${index + 1} / ${quiz.questions.length}`} title={q.question} text={q.hint}>
        <View style={[styles.progressTrack, { backgroundColor: theme.line }]}>
          <View style={[styles.progressBar, { width: `${((index + 1) / quiz.questions.length) * 100}%`, backgroundColor: theme.accent }]} />
        </View>
      </PageCard>
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
  if (q.kind === 'multi') return ((value as unknown[] | undefined)?.length ?? 0) >= (q.min ?? 0); // "none" is an answer, unless `min`
  if (q.kind === 'text' || q.kind === 'date') return true; // a date defaults to next Friday
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
  const options = question.options ?? [];
  if (question.kind === 'single' || question.kind === 'scale') {
    return (
      <OptionGrid>
        {options.map((o) => (
          <OptionCard
            key={String(o.value)}
            label={o.label ?? String(o.value)}
            desc={o.desc}
            icon={o.icon}
            emoji={o.emoji}
            selected={value === o.value}
            onPress={() => onAnswer(o.value)}
          />
        ))}
      </OptionGrid>
    );
  }
  if (question.kind === 'multi') {
    const chosen = new Set((value as string[] | undefined) ?? []);
    const toggle = (v: string) => {
      const next = new Set(chosen);
      if (next.has(v)) next.delete(v);
      else next.add(v);
      onChange([...next]);
    };
    return (
      <OptionGrid>
        {options.map((o) => {
          const v = o.value as string;
          return (
            <OptionCard
              key={v}
              label={o.label ?? v}
              desc={o.desc}
              icon={o.icon}
              emoji={o.emoji}
              selected={chosen.has(v)}
              disabled={!chosen.has(v) && !!question.max && chosen.size >= question.max}
              onPress={() => toggle(v)}
            />
          );
        })}
      </OptionGrid>
    );
  }
  if (question.kind === 'date') {
    return <DayField value={(value as string) || nextFriday()} onChange={onChange} />;
  }
  return (
    <TextField value={(value as string) || ''} onChangeText={onChange} placeholder="Léa & Sam" maxLength={80} />
  );
}

const styles = StyleSheet.create({
  progressTrack: { height: 3, borderRadius: 2, overflow: 'hidden', marginTop: Spacing.two },
  progressBar: { height: '100%' },
  nav: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: Spacing.one },
});

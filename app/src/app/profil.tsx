import { useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { Image, StyleSheet, View } from 'react-native';

import { PrimaryButton, PrimaryLink, TextButton } from '@/components/buttons';
import { DayField } from '@/components/day-field';
import { OptionRow } from '@/components/option-button';
import { OptionCard, OptionGrid } from '@/components/option-card';
import { Screen } from '@/components/screen';
import { TextField } from '@/components/text-field';
import { ThemedText } from '@/components/themed-text';
import { Fonts, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { accountProfile, currentUser, saveAccountProfile } from '@/lib/account';
import { getQuiz, saveProfile, type Profile, type Question, type QuizData } from '@/lib/api';
import { longDay, nextFriday } from '@/lib/dates';
import { rememberedProfile, rememberProfile } from '@/lib/local-store';
import { DEFAULT_BANNER, PERSONA_BANNERS } from '@/lib/persona-banners';

type Phase = 'loading' | 'quiz' | 'saving' | 'error' | 'unreachable' | 'reveal';

export default function ProfilScreen() {
  const { new: isNew } = useLocalSearchParams<{ new?: string }>();
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
          setResult(remembered.profile);
          setPhase('reveal');
          return;
        }
        const user = await currentUser().catch(() => null);
        if (user) {
          const found = await accountProfile().catch(() => null);
          if (found) return submit(found.answers);
        }
      }
      setPhase('quiz');
    })();
  }, [isNew]);

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
        <Reveal quiz={quiz} answers={answers} profile={result} onRestart={() => { setIndex(0); setResult(null); setPhase('quiz'); }} />
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
      <ThemedText type="eyebrow">Votre profil · question {index + 1} sur {quiz.questions.length}</ThemedText>
      <View style={[styles.progressTrack, { backgroundColor: theme.line }]}>
        <View style={[styles.progressBar, { width: `${((index + 1) / quiz.questions.length) * 100}%`, backgroundColor: theme.accent }]} />
      </View>
      <ThemedText type="title">{q.question}</ThemedText>
      {q.hint ? <ThemedText type="small" themeColor="textSecondary">{q.hint}</ThemedText> : null}
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

function Reveal({
  quiz,
  answers,
  profile: p,
  onRestart,
}: {
  quiz: QuizData;
  answers: Record<string, unknown>;
  profile: Profile;
  onRestart: () => void;
}) {
  const theme = useTheme();
  const eviter = quiz.questions.find((q) => q.id === 'eviter');
  const chosen = (answers.eviter as string[] | undefined) ?? [];
  const never = chosen.map((v) => eviter?.options?.find((o) => o.value === v)).filter((o): o is NonNullable<typeof o> => !!o);
  const banner = PERSONA_BANNERS[p.persona.name] ?? DEFAULT_BANNER;
  return (
    <View style={[styles.persona, { backgroundColor: theme.backgroundElement, borderColor: theme.accentSoft }]}>
      <Image source={banner} style={styles.banner} />
      <View style={styles.personaBody}>
        <ThemedText type="eyebrow">{p.names ? `${p.names}, vous êtes…` : 'Vous êtes…'}</ThemedText>
        <ThemedText type="title">{p.persona.name}</ThemedText>
        <ThemedText themeColor="textSecondary">{p.persona.text}</ThemedText>
        <OptionRow>
          {p.vibes.map((v) => (
            <ThemedText key={v} type="small" themeColor="accentInk" style={[styles.tag, { borderColor: theme.accentSoft }]}>
              {quiz.vibes[v] || v}
            </ThemedText>
          ))}
        </OptionRow>
        <View style={styles.facts}>
          <Fact label="première sortie" value={p.first_day ? longDay(p.first_day) : 'Bientôt'} />
          <Fact label="soirée type" value={p.budget >= 350 ? 'sans compter' : `≈ ${p.budget} €`} />
          <View style={[styles.factItem, { borderColor: theme.line }]}>
            <ThemedText style={styles.factValue}>{Math.round(p.audace * 100)} %</ThemedText>
            <ThemedText type="small" themeColor="textSecondary">audace</ThemedText>
            <View style={[styles.meterTrack, { backgroundColor: theme.line }]}>
              <View style={[styles.meterBar, { width: `${p.audace * 100}%`, backgroundColor: theme.accent }]} />
            </View>
          </View>
        </View>
        {never.length > 0 && (
          <ThemedText themeColor="textSecondary">
            <ThemedText>Jamais : </ThemedText>
            {never.map((o) => (o.label ?? '').toLowerCase()).join(', ')}
          </ThemedText>
        )}
        <View style={styles.nav}>
          <TextButton onPress={onRestart}>Recommencer</TextButton>
          <PrimaryLink href="/soiree">Lancer une intrigue</PrimaryLink>
        </View>
      </View>
    </View>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  const theme = useTheme();
  return (
    <View style={[styles.factItem, { borderColor: theme.line }]}>
      <ThemedText style={styles.factValue}>{value}</ThemedText>
      <ThemedText type="small" themeColor="textSecondary">{label}</ThemedText>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: { width: '100%', height: 120, opacity: 0.85 },
  progressTrack: { height: 3, borderRadius: 2, overflow: 'hidden' },
  progressBar: { height: '100%' },
  nav: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: Spacing.one },
  persona: { borderRadius: 24, borderWidth: 1, overflow: 'hidden' },
  personaBody: { gap: Spacing.two, padding: Spacing.three, paddingTop: Spacing.two },
  tag: { borderRadius: 999, borderWidth: 1, paddingVertical: 2, paddingHorizontal: 10, overflow: 'hidden' },
  facts: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.two },
  factItem: { flex: 1, minWidth: 0, gap: 0, borderTopWidth: 1, paddingTop: Spacing.one },
  factValue: { fontFamily: Fonts.heading, fontSize: 14, lineHeight: 18 },
  meterTrack: { height: 3, borderRadius: 2, overflow: 'hidden', marginTop: Spacing.two },
  meterBar: { height: '100%' },
});

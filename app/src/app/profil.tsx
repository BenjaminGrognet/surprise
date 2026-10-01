import { useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { Image, StyleSheet, TextInput, View } from 'react-native';

import { PrimaryButton, PrimaryLink, TextButton } from '@/components/buttons';
import { DayField } from '@/components/day-field';
import { OptionButton, OptionRow } from '@/components/option-button';
import { Screen } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { Fonts, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { accountProfile, currentUser, saveAccountProfile } from '@/lib/account';
import { getQuiz, saveProfile, type Profile, type Question, type QuizData } from '@/lib/api';
import { longDay, nextFriday } from '@/lib/dates';
import { rememberedProfile, rememberProfile } from '@/lib/local-store';

const BANNER = 'https://images.unsplash.com/photo-1545343403-03e407630152?auto=format&fit=crop&w=1600&q=60';

const PERSONA_BANNERS: Record<string, string> = {
  'Les Explorateurs': 'https://images.unsplash.com/photo-1504730513966-dfcd6e53fdc8?auto=format&fit=crop&w=1600&q=60',
  'Les Romantiques': 'https://images.unsplash.com/photo-1545343403-03e407630152?auto=format&fit=crop&w=1600&q=60',
  'Les Épicuriens': 'https://images.unsplash.com/photo-1671691302268-e316f81c7b3e?auto=format&fit=crop&w=1600&q=60',
  'Les Noctambules': 'https://images.unsplash.com/photo-1713450605268-5f8ba67f5b55?auto=format&fit=crop&w=1600&q=60',
  'Les Curieux': 'https://images.unsplash.com/photo-1708941432245-289f6add01c4?auto=format&fit=crop&w=1600&q=60',
  'Les Complices': 'https://images.unsplash.com/photo-1671032290241-b0837e7a922e?auto=format&fit=crop&w=1600&q=60',
  'Les Créatifs': 'https://images.unsplash.com/photo-1620140036708-455ed5c0426a?auto=format&fit=crop&w=1600&q=60',
  'Les Flâneurs': 'https://images.unsplash.com/photo-1782022007537-47cdc954b386?auto=format&fit=crop&w=1600&q=60',
};

type Phase = 'loading' | 'quiz' | 'saving' | 'error' | 'reveal';

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
      const data = await getQuiz();
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
    if (isLast) submit(finalAnswers);
    else setIndex((i) => i + 1);
  }

  return (
    <Screen>
      <ThemedText type="eyebrow">Votre profil · question {index + 1} sur {quiz.questions.length}</ThemedText>
      <View style={[styles.progressTrack, { backgroundColor: theme.line }]}>
        <View style={[styles.progressBar, { width: `${(index / quiz.questions.length) * 100}%`, backgroundColor: theme.accent }]} />
      </View>
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
      placeholderTextColor={theme.textSecondary}
      maxLength={80}
      style={[styles.input, { backgroundColor: theme.backgroundElement, color: theme.text, borderColor: theme.line }]}
    />
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
  const banner = PERSONA_BANNERS[p.persona.name] ?? BANNER;
  return (
    <View style={[styles.persona, { backgroundColor: theme.backgroundElement, borderColor: theme.accentSoft }]}>
      <Image source={{ uri: banner }} style={styles.banner} />
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
          <Fact label="pour une soirée type" value={p.budget >= 350 ? 'sans compter' : `≈ ${p.budget} €`} />
          <View style={[styles.factItem, { borderColor: theme.line }]}>
            <ThemedText style={styles.factValue}>Audace</ThemedText>
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
  banner: { width: '100%', height: 180, opacity: 0.85 },
  progressTrack: { height: 3, borderRadius: 2, overflow: 'hidden' },
  progressBar: { height: '100%' },
  nav: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: Spacing.three },
  input: { fontFamily: Fonts.sans, fontSize: 16, padding: 14, borderRadius: 14, borderWidth: 1 },
  persona: { borderRadius: 24, borderWidth: 1, overflow: 'hidden' },
  personaBody: { gap: Spacing.three, padding: Spacing.four },
  tag: { borderRadius: 999, borderWidth: 1, paddingVertical: 4, paddingHorizontal: 12, overflow: 'hidden' },
  facts: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.three },
  factItem: { flex: 1, minWidth: 130, gap: 4, borderTopWidth: 1, paddingTop: Spacing.two },
  factValue: { fontFamily: Fonts.heading, fontSize: 18 },
  meterTrack: { height: 3, borderRadius: 2, overflow: 'hidden', marginTop: Spacing.two },
  meterBar: { height: '100%' },
});

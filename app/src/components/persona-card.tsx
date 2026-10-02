import { Image } from 'expo-image';
import type { ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';

import { Badge } from '@/components/intrigue-card';
import { OptionRow } from '@/components/option-button';
import { ThemedText } from '@/components/themed-text';
import { Fonts, Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import type { Profile, QuizData } from '@/lib/api';
import { longDay } from '@/lib/dates';
import { DEFAULT_BANNER, PERSONA_BANNERS } from '@/lib/persona-banners';

// The couple's profile as the quiz drew it: the persona under its banner, their vibes, a few figures and their
// "never". The quiz names the vibes and the "never" (without it, the vibes stay raw and the "never" unsaid);
// `children` are the card's actions.
export function PersonaCard({
  profile: p, answers, quiz, children,
}: { profile: Profile; answers: Record<string, unknown>; quiz: QuizData | null; children?: ReactNode }) {
  const theme = useTheme();
  const eviter = quiz?.questions.find((q) => q.id === 'eviter');
  const chosen = (answers.eviter as string[] | undefined) ?? [];
  const never = chosen.map((v) => eviter?.options?.find((o) => o.value === v)).filter((o): o is NonNullable<typeof o> => !!o);
  return (
    <View style={[styles.persona, { backgroundColor: theme.backgroundElement, borderColor: theme.accentSoft }]}>
      <Image source={PERSONA_BANNERS[p.persona.name] ?? DEFAULT_BANNER} style={styles.banner} contentFit="cover" />
      <View style={styles.body}>
        <ThemedText type="eyebrow">{p.names ? `${p.names}, vous êtes…` : 'Vous êtes…'}</ThemedText>
        <ThemedText type="title">{p.persona.name}</ThemedText>
        <ThemedText themeColor="textSecondary">{p.persona.text}</ThemedText>
        <OptionRow>
          {p.vibes.map((v) => (
            <Badge key={v}>{quiz?.vibes[v] || v}</Badge>
          ))}
        </OptionRow>
        <View style={styles.facts}>
          <Fact label="première sortie" value={p.first_day ? longDay(p.first_day) : 'Bientôt'} />
          <Fact label="soirée type" value={p.budget >= 350 ? 'sans compter' : `≈ ${p.budget} €`} />
          <View style={[styles.fact, { borderColor: theme.line }]}>
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
        {children}
      </View>
    </View>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  const theme = useTheme();
  return (
    <View style={[styles.fact, { borderColor: theme.line }]}>
      <ThemedText style={styles.factValue}>{value}</ThemedText>
      <ThemedText type="small" themeColor="textSecondary">{label}</ThemedText>
    </View>
  );
}

const styles = StyleSheet.create({
  persona: { borderRadius: Radius.card, borderWidth: 1, overflow: 'hidden' },
  banner: { width: '100%', height: 120, opacity: 0.85 },
  body: { gap: Spacing.two, padding: Spacing.three, paddingTop: Spacing.two },
  facts: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.two },
  fact: { flex: 1, minWidth: 0, gap: 0, borderTopWidth: 1, paddingTop: Spacing.one },
  factValue: { fontFamily: Fonts.heading, fontSize: 19, lineHeight: 23 },
  meterTrack: { height: 3, borderRadius: 2, overflow: 'hidden', marginTop: Spacing.two },
  meterBar: { height: '100%' },
});

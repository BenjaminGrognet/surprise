import { useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { TextButton } from '@/components/buttons';
import { ThemedText } from '@/components/themed-text';
import { Fonts, Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import type { Formule } from '@/lib/api';
import { allCards, cardDepth, cardFor, type Carte } from '@/lib/cartes';
import { myComplicity } from '@/lib/complicity';

const KINDS = { conversation: 'Carte conversation', defi: 'Carte défi', gage: 'Le gage de la bande' } as const;

// A card of the evening under a step on the day (lib/cartes.ts): the same for everyone on the evening, another at a
// touch. Nothing shown if the cards cannot be read.
export function EveningCard({ evening, formule, role, position }: { evening: string; formule: Formule; role: string; position: number }) {
  const theme = useTheme();
  const [cards, setCards] = useState<Carte[]>([]);
  const [turn, setTurn] = useState(0);
  // A duo's cards deeper with the evenings it lived (this one not counted until the day after).
  const [depth, setDepth] = useState(1);
  useEffect(() => {
    allCards().then(setCards, () => {});
    if (formule === 'duo') myComplicity().then((c) => setDepth(cardDepth(c.lived)), () => {});
  }, [formule]);
  const card = cardFor(cards, formule, role, evening, position, turn, depth);
  if (!card) return null;
  return (
    <View testID={`carte-du-soir:${position}`} style={[styles.card, { borderColor: theme.goldSoft, backgroundColor: theme.background }]}>
      <ThemedText type="eyebrow" themeColor="gold" style={styles.label}>{KINDS[card.genre]}</ThemedText>
      <ThemedText style={[styles.text, { color: theme.cream }]}>{card.texte}</ThemedText>
      <TextButton onPress={() => setTurn((t) => t + 1)}>Une autre carte</TextButton>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { gap: Spacing.one, padding: Spacing.three, borderRadius: Radius.tile, borderWidth: 1, borderStyle: 'dashed', marginTop: Spacing.two },
  label: { fontSize: 10, letterSpacing: 2.5 },
  text: { fontFamily: Fonts.headingItalic, fontSize: 18, lineHeight: 23 },
});

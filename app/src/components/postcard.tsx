import { forwardRef, useRef, useState } from 'react';
import { Platform, StyleSheet, View } from 'react-native';
import Svg, { Defs, RadialGradient, Rect, Stop } from 'react-native-svg';

import { PrimaryButton } from '@/components/buttons';
import { LogoSecretDate } from '@/components/logo-secretdate';
import { ThemedText } from '@/components/themed-text';
import { Fonts, Spacing } from '@/constants/theme';
import { useNow } from '@/hooks/use-now';
import { useTheme } from '@/hooks/use-theme';
import type { SoireeRoute } from '@/lib/api';
import type { RevealMode } from '@/lib/clues';
import { postcard, postcardFile, type Postcard } from '@/lib/postcard';
import { shareImage } from '@/lib/share-image';

// The card's own size, a story's 9:16: drawn at 360 x 640, shared at 1080 x 1920.
const W = 360;
const H = 640;
const PREVIEW = 0.62;

// The evening's postcard, for both partners, to share in a story before or after (lib/postcard.ts): never more than
// the passager may know. A preview, and the image shared (a phone) or downloaded (the web).
export function PostcardShare({ route, mode, secretTitle }: { route: SoireeRoute; mode: RevealMode; secretTitle: string }) {
  const theme = useTheme();
  const now = useNow();
  const card = useRef<View>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function share() {
    if (!card.current) return;
    setBusy(true);
    setError('');
    try {
      await shareImage(card.current, postcardFile(secretTitle));
    } catch {
      setError("La carte n'a pas pu être préparée : réessayez dans un instant.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <View testID="carte-postale" style={[styles.section, { borderColor: theme.line }]}>
      <ThemedText type="eyebrow">La carte postale</ThemedText>
      <ThemedText type="small" themeColor="textSecondary">
        À partager en story : le nom de votre soirée et ses mots mystères, sans rien dévoiler de plus.
      </ThemedText>
      <View style={styles.frame}>
        <View style={styles.scaled}>
          <PostcardView ref={card} card={postcard(route, mode, secretTitle, now)} />
        </View>
      </View>
      <PrimaryButton wide disabled={busy} onPress={share}>
        {busy ? 'Préparation…' : Platform.OS === 'web' ? 'Télécharger la carte' : 'Partager la carte'}
      </PrimaryButton>
      {error ? <ThemedText type="small" themeColor="danger">{error}</ThemedText> : null}
    </View>
  );
}

// The card itself, at its own size: the night with an emerald glow, the emblem, the secret name, the words in gold.
export const PostcardView = forwardRef<View, { card: Postcard }>(function PostcardView({ card }, ref) {
  const theme = useTheme();
  return (
    <View ref={ref} collapsable={false} style={[styles.card, { backgroundColor: theme.background }]}>
      <Svg width={W} height={H} style={StyleSheet.absoluteFill}>
        <Defs>
          <RadialGradient id="postcard-glow" cx="50%" cy="0%" r="85%">
            <Stop offset="0" stopColor="#14533A" stopOpacity={0.95} />
            <Stop offset="0.55" stopColor="#071A12" stopOpacity={0.9} />
            <Stop offset="1" stopColor={theme.background} stopOpacity={1} />
          </RadialGradient>
        </Defs>
        <Rect width={W} height={H} fill="url(#postcard-glow)" />
        <Rect x={14} y={14} width={W - 28} height={H - 28} rx={22} fill="none" stroke={theme.goldSoft} strokeWidth={1} />
      </Svg>
      <View style={styles.top}>
        <LogoSecretDate size={54} round />
        <ThemedText style={[styles.brand, { color: theme.gold }]}>SECRET DATE</ThemedText>
      </View>
      <View style={styles.middle}>
        <ThemedText style={[styles.when, { color: theme.gold }]}>{card.when}</ThemedText>
        <ThemedText style={[styles.title, { color: theme.text }]}>{card.title}</ThemedText>
        <View style={styles.words}>
          {card.words.map((word, i) => (
            <ThemedText key={i} style={[styles.word, { color: word === '?' ? theme.textSecondary : theme.gold }]}>
              « {word} »
            </ThemedText>
          ))}
        </View>
        {card.steps.length ? (
          <View style={styles.steps}>
            {card.steps.map((step, i) => (
              <ThemedText key={i} style={[styles.step, { color: theme.creamSoft }]}>{step}</ThemedText>
            ))}
          </View>
        ) : null}
      </View>
      <ThemedText style={[styles.line, { color: theme.creamSoft }]}>{card.line}</ThemedText>
    </View>
  );
});

const styles = StyleSheet.create({
  section: { gap: Spacing.three, borderTopWidth: 1, paddingTop: Spacing.four },
  frame: { width: W * PREVIEW, height: H * PREVIEW, alignSelf: 'center', borderRadius: 18, overflow: 'hidden' },
  scaled: { width: W, height: H, transform: [{ scale: PREVIEW }], transformOrigin: 'top left' },
  card: { width: W, height: H, paddingHorizontal: 34, paddingVertical: 42, justifyContent: 'space-between', overflow: 'hidden' },
  top: { alignItems: 'center', gap: Spacing.two },
  brand: { fontFamily: Fonts.headingBold, fontSize: 15, letterSpacing: 4 },
  middle: { alignItems: 'center', gap: Spacing.three },
  when: { fontFamily: Fonts.sansSemiBold, fontSize: 11, letterSpacing: 2.5, textTransform: 'uppercase', textAlign: 'center' },
  title: { fontFamily: Fonts.headingItalic, fontSize: 38, lineHeight: 42, textAlign: 'center' },
  words: { alignItems: 'center', gap: 2, marginTop: Spacing.two },
  word: { fontFamily: Fonts.headingItalic, fontSize: 26, lineHeight: 32 },
  steps: { alignItems: 'center', gap: 2, marginTop: Spacing.two },
  step: { fontFamily: Fonts.sans, fontSize: 12, textAlign: 'center' },
  line: { fontFamily: Fonts.headingItalic, fontSize: 17, lineHeight: 22, textAlign: 'center' },
});

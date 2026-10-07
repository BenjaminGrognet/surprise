import { forwardRef, useRef, useState } from 'react';
import { Platform, StyleSheet, View } from 'react-native';
import Svg, { Circle, Defs, Line, Path, Polygon, RadialGradient, Rect, Stop } from 'react-native-svg';

import { PrimaryButton } from '@/components/buttons';
import { DiscoBall, GLINTS, seeded } from '@/components/disco-ball';
import { LogoSecretDate } from '@/components/logo-secretdate';
import { ThemedText } from '@/components/themed-text';
import { Brands, Fonts, Spacing } from '@/constants/theme';
import { useNow } from '@/hooks/use-now';
import { usePalette, useTheme } from '@/hooks/use-theme';
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
// A band's (Secret Squad): a club's night under its disco ball, softly lit.
export const PostcardView = forwardRef<View, { card: Postcard }>(function PostcardView({ card }, ref) {
  const theme = useTheme();
  const palette = usePalette();
  const squad = palette === 'squad';
  return (
    <View ref={ref} collapsable={false} style={[styles.card, { backgroundColor: theme.background }]}>
      {squad ? (
        <ClubNight />
      ) : (
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
      )}
      <View style={styles.top}>
        {squad ? <DiscoBall size={BALL_SIZE} /> : <LogoSecretDate size={54} round />}
        <ThemedText style={[styles.brand, squad && styles.squadBrand, { color: theme.gold }]}>{Brands[palette].toUpperCase()}</ThemedText>
      </View>
      <View style={styles.middle}>
        <View style={squad && [styles.pill, { borderColor: theme.goldSoft }]}>
          <ThemedText style={[styles.when, { color: theme.gold }]}>{card.when}</ThemedText>
        </View>
        <ThemedText style={[styles.title, squad && styles.squadTitle, { color: theme.text }]}>{card.title}</ThemedText>
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

// Secret Squad's night: the disco ball hung from the top, a few faint beams in its neons, scattered glints, a cyan
// glow above and a fuchsia one below, a neon tube for a frame.
const BALL_SIZE = 80;
const BALL = { x: W / 2, y: 42 + BALL_SIZE / 2 }; // the card's top padding, then the ball's centre
const BEAM_LENGTH = 720;
const BEAMS = [-40, -16, 16, 40].map((angle, i) => {
  const at = (deg: number) => {
    const rad = (deg * Math.PI) / 180;
    return `${BALL.x + BEAM_LENGTH * Math.sin(rad)},${BALL.y + BEAM_LENGTH * Math.cos(rad)}`;
  };
  return { points: `${BALL.x},${BALL.y} ${at(angle - 4)} ${at(angle + 4)}`, color: [0, 2, 0, 2][i] };
});
const SPARKS = (() => {
  const rand = seeded(23);
  return Array.from({ length: 18 }, () => ({
    x: 30 + rand() * (W - 60), y: 30 + rand() * (H - 60), r: 0.8 + rand() * 1.6,
    color: rand() < 0.35 ? '#FFFFFF' : GLINTS[Math.floor(rand() * GLINTS.length)], opacity: 0.25 + rand() * 0.5, star: rand() < 0.4,
  }));
})();
// A four-pointed glint, its arms curved in.
const star = (x: number, y: number, r: number) =>
  `M${x},${y - 3 * r} Q${x},${y} ${x + 3 * r},${y} Q${x},${y} ${x},${y + 3 * r} Q${x},${y} ${x - 3 * r},${y} Q${x},${y} ${x},${y - 3 * r}Z`;

function ClubNight() {
  const frame = { x: 14, y: 14, width: W - 28, height: H - 28, rx: 22, fill: 'none' };
  return (
    <Svg width={W} height={H} style={StyleSheet.absoluteFill}>
      <Defs>
        <RadialGradient id="club-cyan" cx="80%" cy="0%" r="75%">
          <Stop offset="0" stopColor={GLINTS[0]} stopOpacity={0.3} />
          <Stop offset="1" stopColor={GLINTS[0]} stopOpacity={0} />
        </RadialGradient>
        <RadialGradient id="club-fuchsia" cx="15%" cy="100%" r="80%">
          <Stop offset="0" stopColor={GLINTS[2]} stopOpacity={0.3} />
          <Stop offset="1" stopColor={GLINTS[2]} stopOpacity={0} />
        </RadialGradient>
        <RadialGradient id="club-halo" cx={BALL.x} cy={BALL.y} r={100} gradientUnits="userSpaceOnUse">
          <Stop offset="0" stopColor="#FFFFFF" stopOpacity={0.35} />
          <Stop offset="0.35" stopColor={GLINTS[0]} stopOpacity={0.15} />
          <Stop offset="1" stopColor={GLINTS[0]} stopOpacity={0} />
        </RadialGradient>
        {GLINTS.map((color, i) => (
          <RadialGradient key={i} id={`club-beam-${i}`} cx={BALL.x} cy={BALL.y} r={BEAM_LENGTH} gradientUnits="userSpaceOnUse">
            <Stop offset="0" stopColor={color} stopOpacity={0.2} />
            <Stop offset="0.6" stopColor={color} stopOpacity={0.04} />
            <Stop offset="1" stopColor={color} stopOpacity={0} />
          </RadialGradient>
        ))}
      </Defs>
      <Rect width={W} height={H} fill="url(#club-cyan)" />
      <Rect width={W} height={H} fill="url(#club-fuchsia)" />
      {BEAMS.map((beam, i) => <Polygon key={i} points={beam.points} fill={`url(#club-beam-${beam.color})`} />)}
      {SPARKS.map((s, i) =>
        s.star ? <Path key={i} d={star(s.x, s.y, s.r)} fill={s.color} fillOpacity={s.opacity} />
          : <Circle key={i} cx={s.x} cy={s.y} r={s.r * 0.7} fill={s.color} fillOpacity={s.opacity} />,
      )}
      <Circle cx={BALL.x} cy={BALL.y} r={100} fill="url(#club-halo)" />
      <Line x1={BALL.x} y1={14} x2={BALL.x} y2={BALL.y - BALL_SIZE / 2} stroke="#E2BC6E" strokeOpacity={0.5} strokeWidth={1} />
      <Rect {...frame} stroke={GLINTS[0]} strokeOpacity={0.12} strokeWidth={6} />
      <Rect {...frame} stroke={GLINTS[0]} strokeOpacity={0.8} strokeWidth={1} />
    </Svg>
  );
}

const styles = StyleSheet.create({
  section: { gap: Spacing.three, borderTopWidth: 1, paddingTop: Spacing.four },
  frame: { width: W * PREVIEW, height: H * PREVIEW, alignSelf: 'center', borderRadius: 18, overflow: 'hidden' },
  scaled: { width: W, height: H, transform: [{ scale: PREVIEW }], transformOrigin: 'top left' },
  card: { width: W, height: H, paddingHorizontal: 34, paddingVertical: 42, justifyContent: 'space-between', overflow: 'hidden' },
  top: { alignItems: 'center', gap: Spacing.two },
  brand: { fontFamily: Fonts.headingBold, fontSize: 15, letterSpacing: 4 },
  squadBrand: { fontSize: 20 },
  middle: { alignItems: 'center', gap: Spacing.three },
  when: { fontFamily: Fonts.sansSemiBold, fontSize: 11, letterSpacing: 2.5, textTransform: 'uppercase', textAlign: 'center' },
  pill: { borderWidth: 1, borderRadius: 999, paddingVertical: 6, paddingHorizontal: 14 },
  title: { fontFamily: Fonts.headingItalic, fontSize: 38, lineHeight: 42, textAlign: 'center' },
  squadTitle: { fontSize: 46 },
  words: { alignItems: 'center', gap: 2, marginTop: Spacing.two },
  word: { fontFamily: Fonts.headingItalic, fontSize: 26, lineHeight: 32 },
  steps: { alignItems: 'center', gap: 2, marginTop: Spacing.two },
  step: { fontFamily: Fonts.sans, fontSize: 12, textAlign: 'center' },
  line: { fontFamily: Fonts.headingItalic, fontSize: 17, lineHeight: 22, textAlign: 'center' },
});

import { useState } from 'react';
import { Linking, Pressable, StyleSheet, View } from 'react-native';

import { PrimaryButton, TextButton } from '@/components/buttons';
import { ThemedText } from '@/components/themed-text';
import { Colors, Radius, Spacing } from '@/constants/theme';
import { Spinner, busyStyle } from '@/components/spinner';
import { StepImage } from '@/components/step-image';
import { TasteVote } from '@/components/taste-vote';
import { useTheme } from '@/hooks/use-theme';
import type { Vote } from '@/lib/account';
import { place, type SoireeRoute, type SoireeStep } from '@/lib/api';
import { formatTime } from '@/lib/dates';

const ROLE_LABELS: Record<SoireeStep['role'], string> = { repas: 'Dîner', verre: 'Un verre', sortie: 'Sortie', nuit: 'La nuit' };
const BOOKING_LABELS: Record<SoireeStep['booking_action'], string> = { voir_lieu: 'Voir le lieu', voir_fiche: 'Voir la fiche', reserver: 'Réserver' };
// The activity cards: the night green, with the brand's own inks.
const PAPER = Colors.dark.background;
const INK = Colors.dark.text;
const INK_SOFT = Colors.dark.textSecondary;
const GOLD_INK = Colors.dark.gold;
const LINK_INK = Colors.dark.accentInk;
const BADGE_INK = { ok: Colors.dark.ok, info: Colors.dark.info, warn: Colors.dark.warn } as const;
const BADGE_KIND: Record<SoireeStep['kind'], 'ok' | 'info' | 'warn'> = { verifie: 'ok', seance: 'ok', gratuit: 'info', sans_resa: 'warn', nuit: 'warn' };

export function formatPrice(step: SoireeStep) {
  if (step.kind === 'nuit') return `${step.price_estimated ? '≈ ' : 'dès '}${step.price.toFixed(0)} € la nuit`;
  if (step.price === 0) return 'Gratuit';
  return `${step.price_estimated ? '≈ ' : ''}${step.price.toFixed(0)} € à deux`;
}

export function RouteResult({
  route,
  chosen,
  onRedo,
  onChoose,
  busyRedo,
  votes,
  onVote,
}: {
  route: SoireeRoute;
  chosen?: boolean;
  onRedo?: (redo: string) => void;
  onChoose?: () => void;
  busyRedo?: string | null;
  // The instigateur's votes on the steps (hooks/use-tastes.ts), for the evenings to come; the night is not voted on.
  votes?: Record<string, Vote>;
  onVote?: (step: SoireeStep, vote: Vote) => void;
}) {
  const theme = useTheme();
  // A route keeps one step at least: the last one cannot be taken out.
  const removable = route.steps.length > 1;
  return (
    <View style={[styles.route, { backgroundColor: theme.backgroundElement, borderColor: theme.accentSoft }, busyStyle(busyRedo === route.redo)]}>
      <View style={styles.header}>
        <ThemedText type="eyebrow" style={styles.eyebrow}>
          Intrigue {route.index + 1} · {formatTime(route.start)} → {formatTime(route.end)} · {route.price_estimated ? '≈ ' : ''}{route.price.toFixed(0)} €
        </ThemedText>
        {onRedo ? <TextButton busy={busyRedo === route.redo} onPress={() => onRedo(route.redo)}>{busyRedo === route.redo ? 'Recherche…' : '↻ Tout'}</TextButton> : null}
      </View>
      <ThemedText type="subtitle">{route.title}</ThemedText>
      {route.pitch ? <ThemedText type="small" themeColor="textSecondary" numberOfLines={1}>{route.pitch}</ThemedText> : null}

      <View style={styles.steps}>
        {route.steps.map((step, i) => (
          <View key={i}>
            {i > 0 ? <Hop previous={route.steps[i - 1]} step={step} /> : null}
            <StepRow step={step} busyRedo={busyRedo ?? null} onRedo={onRedo} removable={removable} vote={votes?.[step.id]} onVote={onVote} />
          </View>
        ))}
        {route.night ? (
          <View>
            <Hop previous={route.steps[route.steps.length - 1]} step={route.night} />
            <StepRow step={route.night} busyRedo={busyRedo ?? null} onRedo={onRedo} removable={false} />
          </View>
        ) : null}
      </View>

      {!onChoose ? null : (
        <PrimaryButton wide disabled={chosen} onPress={onChoose}>{chosen ? '✓ Gardée dans vos intrigues' : 'Garder cette intrigue'}</PrimaryButton>
      )}
    </View>
  );
}

function Hop({ previous, step }: { previous: SoireeStep; step: SoireeStep }) {
  const walking = step.distance_km <= 1.3;
  const label = `${step.travel_minutes} min` + (step.distance_km < 1 ? ` · ${(step.distance_km * 1000).toFixed(0)} m` : ` · ${step.distance_km.toFixed(1)} km`);
  const maps = `https://www.google.com/maps/dir/?api=1&origin=${previous.lat},${previous.lon}&destination=${step.lat},${step.lon}&travelmode=${walking ? 'walking' : 'transit'}`;
  return (
    <View style={styles.hop}>
      <TextButton onPress={() => Linking.openURL(maps)}>{`${walking ? '🚶' : '🚇'} ${label}`}</TextButton>
    </View>
  );
}

function StepRow({
  step,
  busyRedo,
  onRedo,
  removable,
  vote,
  onVote,
}: {
  step: SoireeStep;
  busyRedo: string | null;
  onRedo?: (redo: string) => void;
  removable: boolean;
  vote?: Vote;
  onVote?: (step: SoireeStep, vote: Vote) => void;
}) {
  const theme = useTheme();
  const remove = step.redo ? `${step.redo}/remove` : null;
  const [open, setOpen] = useState(false);
  // ponytail: length stands for "cut at two lines"; measure the text layout if it misfires.
  const long = (step.text?.length ?? 0) > 55 || step.title.length > 70;
  const where = place(step);
  const showWhere = !!where && where !== step.title && !step.title.includes(step.venue ?? "0000");
  return (
    <View style={[styles.card, { borderColor: theme.line, backgroundColor: PAPER }, busyStyle(!!busyRedo && (busyRedo === step.redo || busyRedo === remove))]}>
      <View style={styles.side}>
        <View style={[styles.thumb, { backgroundColor: theme.backgroundSelected }]}>
          <StepImage step={step} style={styles.thumbImg} />
        </View>
        {onRedo && step.redo ? <Pressable onPress={busyRedo ? undefined : () => onRedo(step.redo!)} style={styles.redoRow}>{busyRedo === step.redo ? <Spinner size={11} /> : null}<ThemedText type="small" style={{ color: INK_SOFT }}>{busyRedo === step.redo ? 'Recherche…' : '↻ Changer'}</ThemedText></Pressable> : null}
        {onRedo && removable && remove ? <Pressable onPress={() => onRedo(remove)}><ThemedText type="small" style={{ color: INK_SOFT }}>{busyRedo === remove ? 'Retrait…' : '✕ Retirer'}</ThemedText></Pressable> : null}
        {onVote ? <View style={styles.vote}><TasteVote vote={vote} onVote={(v) => onVote(step, v)} /></View> : null}
      </View>
      <View style={styles.body}>
        <ThemedText type="small" style={{ color: INK_SOFT }} numberOfLines={1}>
          <ThemedText type="smallBold" style={{ color: GOLD_INK }}>{formatTime(step.start)}</ThemedText> → {formatTime(step.end)} · {ROLE_LABELS[step.role]}
        </ThemedText>
        <ThemedText type="smallBold" style={{ color: INK }} numberOfLines={open ? undefined : 2}>{step.title}</ThemedText>
        {showWhere ? <ThemedText type="small" style={{ color: INK_SOFT }} numberOfLines={1}>{where}</ThemedText> : null}
        {step.text ? <ThemedText type="small" style={{ color: INK }} numberOfLines={open ? undefined : 1}>{step.text}</ThemedText> : null}
        {long ? (
          <Pressable onPress={() => setOpen(!open)}>
            <ThemedText type="small" style={{ color: LINK_INK }}>{open ? '− Réduire' : '+ Lire la suite'}</ThemedText>
          </Pressable>
        ) : null}
        <ThemedText type="small" style={{ color: BADGE_INK[BADGE_KIND[step.kind]] }} numberOfLines={1}>{step.basis}</ThemedText>
        <View style={styles.line}>
          <ThemedText type="smallBold" style={{ color: INK }}>{formatPrice(step)}</ThemedText>
          {step.booking_url ? (
            <Pressable
              onPress={() => Linking.openURL(step.booking_url!)}
              style={[styles.book, step.booking_action === 'reserver' ? { backgroundColor: theme.satin } : { borderColor: theme.accentFaint, borderWidth: 1 }]}>
              <ThemedText type="smallBold" style={{ color: step.booking_action === 'reserver' ? theme.onAccent : LINK_INK }}>
                {BOOKING_LABELS[step.booking_action]} ↗
              </ThemedText>
            </Pressable>
          ) : null}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  redoRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  route: { gap: Spacing.one, padding: Spacing.two + 4, borderRadius: Radius.tile, borderWidth: 1, marginTop: Spacing.one },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: Spacing.two },
  eyebrow: { flexShrink: 1 },
  steps: { gap: 2, marginVertical: 2 },
  hop: { paddingLeft: Spacing.two, paddingVertical: 0 },
  card: { flexDirection: 'row', gap: Spacing.two + 2, borderWidth: 1, borderRadius: 16, padding: Spacing.two },
  thumb: { width: 72, height: 72, borderRadius: 12, overflow: 'hidden' },
  thumbImg: { width: '100%', height: '100%' },
  body: { flex: 1, gap: 1 },
  line: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: Spacing.two, flexWrap: 'wrap', marginTop: 2 },
  side: { width: 72, gap: 2 },
  vote: { marginTop: Spacing.one },
  book: { borderRadius: 999, paddingVertical: Spacing.one + 2, paddingHorizontal: Spacing.three },
});

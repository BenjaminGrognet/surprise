import { useState } from 'react';
import { Image, Linking, Pressable, StyleSheet, View } from 'react-native';

import { PrimaryButton, TextButton } from '@/components/buttons';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { API_URL, type SoireeRoute, type SoireeStep } from '@/lib/api';
import { formatTime } from '@/lib/dates';

const ROLE_LABELS: Record<SoireeStep['role'], string> = { repas: 'Dîner', verre: 'Un verre', sortie: 'Sortie', nuit: 'La nuit' };
const BOOKING_LABELS: Record<SoireeStep['booking_action'], string> = { voir_lieu: 'Voir le lieu', voir_fiche: 'Voir la fiche', reserver: 'Réserver' };
const BADGE_KIND: Record<SoireeStep['kind'], 'ok' | 'info' | 'warn'> = { verifie: 'ok', seance: 'ok', gratuit: 'info', sans_resa: 'warn', nuit: 'warn' };

export function formatPrice(step: SoireeStep) {
  if (step.kind === 'nuit') return `${step.price_estimated ? '≈ ' : 'dès '}${step.price.toFixed(0)} € la nuit`;
  if (step.price === 0) return 'Gratuit';
  return `${step.price_estimated ? '≈ ' : ''}${step.price.toFixed(0)} € à deux`;
}

export function place(step: SoireeStep) {
  const where = step.arrondissement ? `Paris ${step.arrondissement}ᵉ` : step.town && step.town !== 'Paris' ? step.town : null;
  return [step.venue, where].filter(Boolean).join(' · ');
}

export const imageUri = (url: string) => (url.startsWith('/') ? API_URL + url : url);

export function RouteResult({
  route,
  chosen,
  onRedo,
  onChoose,
  busyRedo,
}: {
  route: SoireeRoute;
  chosen?: boolean;
  onRedo?: (redo: string) => void;
  onChoose?: () => void;
  busyRedo?: string | null;
}) {
  const theme = useTheme();
  // A route keeps one step at least: the last one cannot be taken out.
  const removable = route.steps.length > 1;
  return (
    <View style={[styles.route, { backgroundColor: theme.backgroundElement, borderColor: theme.accentSoft }]}>
      <View style={styles.header}>
        <ThemedText type="eyebrow" style={styles.eyebrow}>
          Intrigue {route.index + 1} · {formatTime(route.start)} → {formatTime(route.end)} · {route.price_estimated ? '≈ ' : ''}{route.price.toFixed(0)} €
        </ThemedText>
        {onRedo ? <TextButton onPress={() => onRedo(route.redo)}>{busyRedo === route.redo ? '↻…' : '↻ Tout'}</TextButton> : null}
      </View>
      <ThemedText type="subtitle">{route.title}</ThemedText>
      {route.pitch ? <ThemedText type="small" themeColor="textSecondary" numberOfLines={2}>{route.pitch}</ThemedText> : null}

      <View style={styles.steps}>
        {route.steps.map((step, i) => (
          <View key={i}>
            {i > 0 ? <Hop previous={route.steps[i - 1]} step={step} /> : null}
            <StepRow step={step} busyRedo={busyRedo ?? null} onRedo={onRedo} removable={removable} />
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
}: {
  step: SoireeStep;
  busyRedo: string | null;
  onRedo?: (redo: string) => void;
  removable: boolean;
}) {
  const theme = useTheme();
  const remove = step.redo ? `${step.redo}/remove` : null;
  const [open, setOpen] = useState(false);
  // ponytail: length stands for "cut at two lines"; measure the text layout if it misfires.
  const long = (step.text?.length ?? 0) > 110 || step.title.length > 70;
  return (
    <View style={[styles.card, { borderColor: theme.line, backgroundColor: theme.background }]}>
      <View style={styles.side}>
        <View style={[styles.thumb, { backgroundColor: theme.backgroundSelected }]}>
          {step.image_url ? <Image source={{ uri: imageUri(step.image_url) }} style={styles.thumbImg} /> : null}
        </View>
        {onRedo && step.redo ? <TextButton onPress={() => onRedo(step.redo!)}>{busyRedo === step.redo ? '↻…' : '↻ Changer'}</TextButton> : null}
        {onRedo && removable && remove ? <TextButton onPress={() => onRedo(remove)}>{busyRedo === remove ? '✕…' : '✕ Retirer'}</TextButton> : null}
      </View>
      <View style={styles.body}>
        <ThemedText type="small" themeColor="textSecondary" numberOfLines={1}>
          <ThemedText type="smallBold" themeColor="accentInk">{formatTime(step.start)}</ThemedText> → {formatTime(step.end)} · {ROLE_LABELS[step.role]}
        </ThemedText>
        <ThemedText type="smallBold" numberOfLines={open ? undefined : 2}>{step.title}</ThemedText>
        <ThemedText type="small" themeColor="textSecondary" numberOfLines={1}>{place(step)}</ThemedText>
        {step.text ? <ThemedText type="small" numberOfLines={open ? undefined : 2}>{step.text}</ThemedText> : null}
        {long ? <TextButton onPress={() => setOpen(!open)}>{open ? '− Réduire' : '+ Lire la suite'}</TextButton> : null}
        <ThemedText type="small" themeColor={BADGE_KIND[step.kind]} numberOfLines={1}>{step.basis}</ThemedText>
        <View style={styles.line}>
          <ThemedText type="smallBold">{formatPrice(step)}</ThemedText>
          {step.booking_url ? (
            <Pressable
              onPress={() => Linking.openURL(step.booking_url!)}
              style={[styles.book, step.booking_action === 'reserver' ? { backgroundColor: theme.satin } : { borderColor: theme.accentSoft, borderWidth: 1 }]}>
              <ThemedText type="smallBold" themeColor={step.booking_action === 'reserver' ? 'onAccent' : 'accentInk'}>
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
  route: { gap: Spacing.two, padding: Spacing.three, borderRadius: 22, borderWidth: 1, marginTop: Spacing.two },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: Spacing.two },
  eyebrow: { flexShrink: 1 },
  steps: { gap: Spacing.one, marginVertical: Spacing.one },
  hop: { paddingLeft: Spacing.two, paddingVertical: Spacing.half },
  card: { flexDirection: 'row', gap: Spacing.three, borderWidth: 1, borderRadius: 16, padding: Spacing.two + 2 },
  thumb: { width: 104, height: 104, borderRadius: 12, overflow: 'hidden' },
  thumbImg: { width: '100%', height: '100%' },
  body: { flex: 1, gap: Spacing.half },
  line: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: Spacing.two, flexWrap: 'wrap', marginTop: Spacing.one },
  side: { width: 104, gap: Spacing.one },
  book: { borderRadius: 999, paddingVertical: Spacing.one + 2, paddingHorizontal: Spacing.three },
});

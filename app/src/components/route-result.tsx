import { Image, Linking, StyleSheet, View } from 'react-native';

import { PrimaryButton, TextButton } from '@/components/buttons';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import type { SoireeRoute, SoireeStep } from '@/lib/api';
import { formatTime } from '@/lib/dates';

const ROLE_LABELS: Record<SoireeStep['role'], string> = { repas: 'Dîner', verre: 'Un verre', sortie: 'Sortie', nuit: 'La nuit' };
const BOOKING_LABELS: Record<SoireeStep['booking_action'], string> = { voir_lieu: 'Voir le lieu', voir_fiche: 'Voir la fiche', reserver: 'Réserver' };
const BADGE_KIND: Record<SoireeStep['kind'], 'ok' | 'free' | 'walk'> = { verifie: 'ok', seance: 'ok', gratuit: 'free', sans_resa: 'walk', nuit: 'walk' };

function formatPrice(step: SoireeStep) {
  if (step.kind === 'nuit') return `${step.price_estimated ? '≈ ' : 'dès '}${step.price.toFixed(0)} € la nuit`;
  if (step.price === 0) return 'Gratuit';
  return `${step.price_estimated ? '≈ ' : ''}${step.price.toFixed(0)} € à deux`;
}

function place(step: SoireeStep) {
  const where = step.arrondissement ? `Paris ${step.arrondissement}ᵉ` : step.town && step.town !== 'Paris' ? step.town : null;
  return [step.venue, where].filter(Boolean).join(' · ');
}

export function RouteResult({
  route,
  chosen,
  onRedo,
  onChoose,
  busyRedo,
}: {
  route: SoireeRoute;
  chosen: boolean;
  onRedo: (redo: string) => void;
  onChoose: () => void;
  busyRedo: string | null;
}) {
  // A route keeps one step at least: the last one cannot be taken out.
  const removable = route.steps.length > 1;
  return (
    <ThemedView type="backgroundElement" style={styles.route}>
      <View style={styles.header}>
        <ThemedText type="small" themeColor="textSecondary" style={styles.eyebrow}>
          Parcours {route.index + 1} · {formatTime(route.start)} → {formatTime(route.end)} · {route.price_estimated ? '≈ ' : ''}{route.price.toFixed(0)} €
        </ThemedText>
        <TextButton onPress={() => onRedo(route.redo)}>{busyRedo === route.redo ? '↻…' : '↻ Tout'}</TextButton>
      </View>
      <ThemedText type="smallBold">{route.title}</ThemedText>
      {route.pitch ? <ThemedText type="small" themeColor="textSecondary" numberOfLines={2}>{route.pitch}</ThemedText> : null}

      <View style={styles.steps}>
        {route.steps.map((step, i) => (
          <View key={i}>
            {i > 0 ? <Hop previous={route.steps[i - 1]} step={step} /> : null}
            <StepRow step={step} busyRedo={busyRedo} onRedo={onRedo} removable={removable} />
          </View>
        ))}
        {route.night ? (
          <View>
            <Hop previous={route.steps[route.steps.length - 1]} step={route.night} />
            <StepRow step={route.night} busyRedo={busyRedo} onRedo={onRedo} removable={false} />
          </View>
        ) : null}
      </View>

      <PrimaryButton disabled={chosen} onPress={onChoose}>{chosen ? '✓ Choisie, dans votre historique' : 'On a choisi cette soirée'}</PrimaryButton>
    </ThemedView>
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
  onRedo: (redo: string) => void;
  removable: boolean;
}) {
  const theme = useTheme();
  const badge = BADGE_KIND[step.kind];
  const badgeColor = badge === 'ok' ? '#1e7a4c' : badge === 'free' ? '#1f5fa8' : '#8a5a00';
  const remove = step.redo ? `${step.redo}/remove` : null;
  return (
    <ThemedView style={[styles.card, { borderColor: theme.line }]}>
      <View style={styles.side}>
        <View style={[styles.thumb, { backgroundColor: theme.backgroundSelected }]}>
          {step.image_url ? <Image source={{ uri: step.image_url }} style={styles.thumbImg} /> : null}
        </View>
        {step.redo ? <TextButton onPress={() => onRedo(step.redo!)}>{busyRedo === step.redo ? '↻…' : '↻ Changer'}</TextButton> : null}
        {removable && remove ? <TextButton onPress={() => onRedo(remove)}>{busyRedo === remove ? '✕…' : '✕ Retirer'}</TextButton> : null}
      </View>
      <View style={styles.body}>
        <ThemedText type="small" themeColor="textSecondary" numberOfLines={1}>
          <ThemedText type="smallBold">{formatTime(step.start)}</ThemedText> → {formatTime(step.end)} · {ROLE_LABELS[step.role]}
        </ThemedText>
        <ThemedText type="smallBold" numberOfLines={2}>{step.title}</ThemedText>
        <ThemedText type="small" themeColor="textSecondary" numberOfLines={1}>{place(step)}</ThemedText>
        {step.text ? <ThemedText type="small" numberOfLines={2}>{step.text}</ThemedText> : null}
        <ThemedText type="small" style={{ color: badgeColor }} numberOfLines={1}>{step.basis}</ThemedText>
        <View style={styles.line}>
          <ThemedText type="smallBold">{formatPrice(step)}</ThemedText>
          {step.booking_url ? <TextButton onPress={() => Linking.openURL(step.booking_url!)}>{BOOKING_LABELS[step.booking_action]}</TextButton> : null}
        </View>
      </View>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  route: { gap: Spacing.one, padding: Spacing.two + 4, borderRadius: 16, marginTop: Spacing.two },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: Spacing.two },
  eyebrow: { flexShrink: 1, textTransform: 'uppercase', letterSpacing: 0.5 },
  steps: { gap: Spacing.one, marginVertical: Spacing.one },
  hop: { paddingLeft: Spacing.two, paddingVertical: Spacing.half },
  card: { flexDirection: 'row', gap: Spacing.two, borderWidth: 1, borderRadius: 12, padding: Spacing.two },
  thumb: { width: 116, height: 116, borderRadius: 10, overflow: 'hidden' },
  thumbImg: { width: '100%', height: '100%' },
  body: { flex: 1, gap: Spacing.half },
  line: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: Spacing.two },
  side: { width: 116, gap: Spacing.one },
});

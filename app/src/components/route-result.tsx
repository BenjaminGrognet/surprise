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
  vibes,
  chosen,
  onRedo,
  onChoose,
  busyRedo,
}: {
  route: SoireeRoute;
  vibes: Record<string, string>;
  chosen: boolean;
  onRedo: (redo: string) => void;
  onChoose: () => void;
  busyRedo: string | null;
}) {
  return (
    <ThemedView type="backgroundElement" style={styles.route}>
      <View style={styles.header}>
        <ThemedText type="small" themeColor="textSecondary" style={styles.eyebrow}>Parcours {route.index + 1}</ThemedText>
        <TextButton onPress={() => onRedo(route.redo)}>{busyRedo === route.redo ? '↻ Recherche…' : '↻ Tout le parcours'}</TextButton>
      </View>
      <ThemedText type="subtitle">{route.title}</ThemedText>
      <ThemedText themeColor="textSecondary">{route.pitch}</ThemedText>
      <ThemedText type="small" themeColor="textSecondary" style={styles.meta}>
        {formatTime(route.start)} → {formatTime(route.end)} · {route.price_estimated ? '≈ ' : ''}{route.price.toFixed(0)} € pour deux · {route.steps.length} étapes
      </ThemedText>

      <View style={styles.steps}>
        {route.steps.map((step, i) => (
          <View key={i} style={styles.stepRow}>
            {i > 0 ? <Hop previous={route.steps[i - 1]} step={step} /> : null}
            <StepCard step={step} vibes={vibes} askedVibes={route.steps.flatMap((s) => s.vibes)} busy={busyRedo === step.redo} onRedo={onRedo} />
          </View>
        ))}
        {route.night ? (
          <View style={styles.stepRow}>
            <Hop previous={route.steps[route.steps.length - 1]} step={route.night} />
            <StepCard step={route.night} vibes={vibes} askedVibes={[]} busy={false} onRedo={onRedo} />
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
    <TextButton onPress={() => Linking.openURL(maps)}>{`${walking ? '🚶' : '🚇'} ${label}`}</TextButton>
  );
}

function StepCard({
  step,
  vibes,
  askedVibes,
  busy,
  onRedo,
}: {
  step: SoireeStep;
  vibes: Record<string, string>;
  askedVibes: string[];
  busy: boolean;
  onRedo: (redo: string) => void;
}) {
  const theme = useTheme();
  const shown = [...new Set([...step.vibes.filter((v) => askedVibes.includes(v)), ...step.vibes])].slice(0, 3);
  const badge = BADGE_KIND[step.kind];
  const badgeColor = badge === 'ok' ? '#1e7a4c' : badge === 'free' ? '#1f5fa8' : '#8a5a00';
  return (
    <ThemedView style={[styles.card, { borderColor: theme.line }]}>
      <View style={styles.timeRow}>
        <View style={styles.time}>
          <ThemedText type="smallBold">{formatTime(step.start)}</ThemedText>
          <ThemedText type="small" themeColor="textSecondary"> → {formatTime(step.end)}</ThemedText>
        </View>
        {step.redo ? <TextButton onPress={() => onRedo(step.redo!)}>{busy ? '↻…' : '↻ Changer'}</TextButton> : null}
      </View>
      <View style={[styles.photo, { backgroundColor: theme.backgroundSelected }]}>
        {step.image_url ? <Image source={{ uri: step.image_url }} style={styles.photoImg} /> : null}
        <View style={styles.roleBadge}><ThemedText style={styles.roleBadgeText}>{ROLE_LABELS[step.role]}</ThemedText></View>
      </View>
      <ThemedText type="smallBold">{step.title}</ThemedText>
      <ThemedText type="small" themeColor="textSecondary">{place(step)}</ThemedText>
      {step.text ? <ThemedText type="small" numberOfLines={4}>{step.text}</ThemedText> : null}
      {shown.length > 0 ? (
        <View style={styles.tags}>
          {shown.map((v) => <ThemedText key={v} type="small" style={styles.tag}>{vibes[v] || v}</ThemedText>)}
        </View>
      ) : null}
      <ThemedText type="small" style={{ color: badgeColor }}>{step.basis}</ThemedText>
      <View style={styles.foot}>
        <ThemedText type="smallBold">{formatPrice(step)}</ThemedText>
        {step.booking_url ? <TextButton onPress={() => Linking.openURL(step.booking_url!)}>{BOOKING_LABELS[step.booking_action]}</TextButton> : null}
      </View>
      <ThemedText type="small" themeColor="textSecondary">via {step.source_name}</ThemedText>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  route: { gap: Spacing.two, padding: Spacing.three, borderRadius: 18, marginTop: Spacing.three },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  eyebrow: { textTransform: 'uppercase', letterSpacing: 1 },
  meta: { marginTop: Spacing.one },
  steps: { gap: Spacing.two, marginTop: Spacing.two },
  stepRow: { gap: Spacing.one },
  card: { gap: Spacing.one, borderWidth: 1, borderRadius: 14, padding: Spacing.two + 2 },
  timeRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  time: { flexDirection: 'row', alignItems: 'baseline' },
  photo: { width: '100%', aspectRatio: 16 / 10, borderRadius: 10, overflow: 'hidden', position: 'relative' },
  photoImg: { width: '100%', height: '100%' },
  roleBadge: { position: 'absolute', top: 8, left: 8, backgroundColor: 'rgba(0,0,0,0.6)', borderRadius: 999, paddingVertical: 3, paddingHorizontal: 10 },
  roleBadgeText: { color: '#fff', fontSize: 12 },
  tags: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.one },
  tag: { borderWidth: 1, borderRadius: 999, paddingVertical: 1, paddingHorizontal: 8 },
  foot: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: Spacing.one },
});

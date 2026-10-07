import { Linking, Pressable, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Icon } from '@/components/ui-icons';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import type { SoireeStep } from '@/lib/api';
import { WALK_KM } from '@/lib/story';

// The way from a step to the next, between them: on foot or by metro as the evening was composed, its line icon in a
// round badge like the tab bar's, the time and the distance; a press opens the way in Google Maps.
export function Hop({ previous, step, style }: { previous: SoireeStep; step: SoireeStep; style?: StyleProp<ViewStyle> }) {
  const theme = useTheme();
  const walking = step.distance_km <= WALK_KM;
  const mode = walking ? 'À pied' : 'En métro';
  const distance = step.distance_km < 1 ? `${(step.distance_km * 1000).toFixed(0)} m` : `${step.distance_km.toFixed(1)} km`;
  const maps = `https://www.google.com/maps/dir/?api=1&origin=${previous.lat},${previous.lon}&destination=${step.lat},${step.lon}&travelmode=${walking ? 'walking' : 'transit'}`;
  return (
    <Pressable
      onPress={() => Linking.openURL(maps)}
      accessibilityRole="link"
      accessibilityLabel={`${mode}, ${step.travel_minutes} min, ${distance} : l'itinéraire`}
      style={({ pressed }) => [styles.hop, style, pressed && styles.pressed]}>
      <View style={[styles.badge, { borderColor: theme.accentFaint, backgroundColor: theme.velvet }]}>
        <Icon name={walking ? 'a_pied' : 'metro'} size={17} strokeWidth={1.7} color={theme.accent} />
      </View>
      <ThemedText type="smallBold" themeColor="cream">{mode}</ThemedText>
      <ThemedText type="small" themeColor="textSecondary">· {step.travel_minutes} min · {distance}</ThemedText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  hop: { flexDirection: 'row', alignItems: 'center', gap: Spacing.two, alignSelf: 'flex-start' },
  badge: { width: 32, height: 32, borderRadius: 16, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  pressed: { opacity: 0.7 },
});

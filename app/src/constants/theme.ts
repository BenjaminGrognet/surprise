/**
 * Below are the colors that are used in the app. The colors are defined in the light and dark mode.
 * There are many other ways to style your app. For example, [Nativewind](https://www.nativewind.dev/), [Tamagui](https://tamagui.dev/), [unistyles](https://reactnativeunistyles.vercel.app), etc.
 */

import '@/global.css';

import { Platform } from 'react-native';

// The "carnet insolite doré" brand (see src/surprise/client.css): warm paper background,
// coral accent, no real dark mode yet, so dark == light for now.
// ponytail: brand has no dark variant designed yet, upgrade when one is designed.
const brand = {
  text: '#211a2b',
  background: '#fbf3e7',
  backgroundElement: '#ffffff',
  backgroundSelected: '#ffe1e6',
  textSecondary: '#6f6579',
  line: '#e8dcf3',
  accent: '#ff5c72',
  accentInk: '#d6314c',
} as const;

export const Colors = { light: brand, dark: brand } as const;

// The "night" accent variant (client.css .persona.night): reserved for the moments that
// announce the evening itself — the profile reveal — never the everyday screens.
export const Night = {
  background: '#241a1f',
  surface: '#2f2420',
  text: '#fbf3e7',
  muted: '#c9b89a',
  line: '#3a2a1f',
  gold: '#caa15a',
  mint: '#35c2a0',
  accent: brand.accent,
} as const;

export type ThemeColor = keyof typeof Colors.light & keyof typeof Colors.dark;

// Brand type: Space Grotesk for body text, Fredoka for headings (loaded in _layout.tsx).
export const Fonts = {
  sans: 'SpaceGrotesk_400Regular',
  sansMedium: 'SpaceGrotesk_500Medium',
  heading: 'Fredoka_600SemiBold',
  headingBold: 'Fredoka_700Bold',
  mono: Platform.select({ ios: 'ui-monospace', default: 'monospace' }),
};

export const Spacing = {
  half: 2,
  one: 4,
  two: 8,
  three: 16,
  four: 24,
  five: 32,
  six: 64,
} as const;

export const BottomTabInset = Platform.select({ ios: 50, android: 80 }) ?? 0;
export const MaxContentWidth = 800;

/**
 * Below are the colors that are used in the app. The colors are defined in the light and dark mode.
 * There are many other ways to style your app. For example, [Nativewind](https://www.nativewind.dev/), [Tamagui](https://tamagui.dev/), [unistyles](https://reactnativeunistyles.vercel.app), etc.
 */

import '@/global.css';

import { Platform } from 'react-native';

// SecretDate's "Midnight Emerald" brand: deep emerald night, brushed champagne gold, silky cream.
// The app is dark by design, so light == dark.
const brand = {
  text: '#F4F1E8', // off-white, a soft contrast on the emerald
  background: '#082A1E',
  backgroundElement: '#0E3727',
  backgroundSelected: '#164532',
  textSecondary: '#9DB8AA',
  line: '#25513F',
  accent: '#D9B771', // brushed champagne gold: buttons, rules, gauges
  accentInk: '#EBCF8A', // gold for text, a touch lighter to read on the emerald
  accentSoft: 'rgba(217, 183, 113, 0.45)', // the fine gold borders of cards
  accentFaint: 'rgba(217, 183, 113, 0.3)', // a field's border at rest; full accent once focused
  satin: '#D2B068', // satin champagne: the gold of buttons, softer than the brushed accent
  onAccent: '#0A3524', // dark emerald, the text on a gold button
  accentHair: 'rgba(217, 183, 113, 0.15)', // a velvet card's border at rest
  glass: 'rgba(255, 253, 208, 0.04)', // a field's veil over the night, see-through
  velvet: '#05180F', // deep emerald velvet: the quiz cards, darker than the night
  cream: '#FFFDD0',
  creamSoft: 'rgba(255, 253, 208, 0.6)', // the cream of an intimate aside
  creamFaint: 'rgba(255, 253, 208, 0.35)', // a placeholder, a whisper
  danger: '#E8857A',
  ok: '#7FD1A4',
  info: '#8DB8E8',
  warn: '#E6B866',
} as const;

export const Colors = { light: brand, dark: brand } as const;

export type ThemeColor = keyof typeof Colors.light & keyof typeof Colors.dark;

// Playfair Display for titles, Inter for the body (loaded in _layout.tsx).
export const Fonts = {
  sans: 'Inter_400Regular',
  sansThin: 'Inter_200ExtraLight', // watchmaking-fine figures: the countdown
  sansLight: 'Inter_300Light',
  sansMedium: 'Inter_500Medium',
  sansSemiBold: 'Inter_600SemiBold',
  heading: 'PlayfairDisplay_400Regular',
  headingBold: 'PlayfairDisplay_600SemiBold',
  headingItalic: 'PlayfairDisplay_400Regular_Italic',
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
export const MaxContentWidth = 640;

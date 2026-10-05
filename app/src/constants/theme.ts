/**
 * Below are the colors that are used in the app. The colors are defined in the light and dark mode.
 * There are many other ways to style your app. For example, [Nativewind](https://www.nativewind.dev/), [Tamagui](https://tamagui.dev/), [unistyles](https://reactnativeunistyles.vercel.app), etc.
 */

import '@/global.css';

import { Platform } from 'react-native';

// SecretDate's "Midnight Emerald": a night so deep it is almost black, emerald for what lives (icons, the chosen
// option, the main button, a status dot), champagne gold kept for what is precious (figures, badges, a notification).
// Every surface is drawn with a gold hairline. The app is dark by design, so light == dark.
const brand = {
  text: '#E9E5D8', // warm ivory
  background: '#040F0A', // midnight emerald, nearly black
  backgroundElement: '#081A13', // the surfaces: tiles, cards, round buttons
  backgroundSelected: '#0F241C', // a chosen surface: the active tab, a veiled line
  textSecondary: '#8F9E91', // sage grey: the spaced labels, the asides
  line: 'rgba(219, 193, 140, 0.14)', // the hairline around every surface
  accent: '#3DB787', // emerald: icons, a chosen option, gauges, the main button
  accentInk: '#62CDA0', // emerald for text (links, active labels), a touch lighter to read on the night
  accentSoft: 'rgba(219, 193, 140, 0.24)', // the gold hairline of a precious card
  accentFaint: 'rgba(61, 183, 135, 0.22)', // a field's border at rest; full emerald once focused
  satin: '#3DB787', // the main button's emerald
  onAccent: '#03140D', // the ink on an emerald button
  accentHair: 'rgba(219, 193, 140, 0.14)', // a tile's hairline at rest
  glass: 'rgba(233, 229, 216, 0.03)', // a field's veil over the night, see-through
  velvet: '#081A13', // the tiles of the quiz and the book's pages
  gold: '#DBC18C', // champagne gold: figures, badges, the notification dot
  goldSoft: 'rgba(219, 193, 140, 0.5)', // a gold badge's outline
  glow: 'rgba(61, 183, 135, 0.28)', // the emerald halo under a card or a button
  cream: '#F1EDE1',
  creamSoft: 'rgba(241, 237, 225, 0.62)', // the cream of an intimate aside
  creamFaint: 'rgba(241, 237, 225, 0.36)', // a placeholder, a whisper
  danger: '#E8857A',
  dangerFaint: 'rgba(232, 133, 122, 0.14)', // a "no" chosen: the thumb down's disc
  ok: '#6FD3A8',
  info: '#8DB8E8',
  warn: '#E6B866',
} as const;

export const Colors = { light: brand, dark: brand } as const;

export type ThemeColor = keyof typeof Colors.light & keyof typeof Colors.dark;

// Cormorant Garamond for titles and names, Manrope for the text (loaded in _layout.tsx).
export const Fonts = {
  sans: 'Manrope_400Regular',
  sansThin: 'Manrope_200ExtraLight', // watchmaking-fine figures: the countdown
  sansLight: 'Manrope_300Light',
  sansMedium: 'Manrope_500Medium',
  sansSemiBold: 'Manrope_600SemiBold',
  sansBold: 'Manrope_700Bold',
  heading: 'CormorantGaramond_500Medium',
  headingBold: 'CormorantGaramond_600SemiBold',
  headingItalic: 'CormorantGaramond_500Medium_Italic',
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

// Rounded like the reference: soft tiles, cards a little rounder, pills fully round.
export const Radius = { tile: 22, card: 26, field: 16, pill: 999 } as const;

export const BottomTabInset = Platform.select({ ios: 50, android: 80 }) ?? 0;
export const MaxContentWidth = 560;

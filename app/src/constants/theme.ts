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
  secret: '#3DB787', // Secret Squad's second neon, for its secret options; the brand keeps its emerald (unused)
} as const;

export const Colors = { light: brand, dark: brand } as const;

export type ThemeColor = keyof typeof Colors.light & keyof typeof Colors.dark;

// Secret Squad's "Underground", for a band of friends' evenings: a club in a cellar, black brushed metal, cyan neon
// for what lives (its headings, icons, a chosen option, the main button), a fuchsia one for its secret options, gold
// kept from the brand for what is precious (badges, figures, the hints). Same words as the brand's: a screen wrapped in
// <PaletteProvider name="squad"> takes it whole, its headings in Anton's poster capitals, lit in cyan (themed-text.tsx).
const squad: Record<ThemeColor, string> = {
  text: '#EDEFF2', // a cold white
  background: '#0A0A0C', // black metal
  backgroundElement: '#131317',
  backgroundSelected: '#1C1C22',
  textSecondary: '#C9A66B', // the hints in old gold
  line: 'rgba(217, 178, 106, 0.3)', // a gold hairline around every surface, as the brand's
  accent: '#3FE0E6', // cyan neon: headings, icons, a chosen option, the main button
  accentInk: '#6FEAEE',
  accentSoft: 'rgba(217, 178, 106, 0.6)', // a card's frame, in gold
  accentFaint: 'rgba(63, 224, 230, 0.35)',
  satin: '#3FE0E6',
  onAccent: '#021617',
  accentHair: 'rgba(63, 224, 230, 0.45)', // an option at rest, outlined in neon
  glass: 'rgba(237, 239, 242, 0.04)',
  velvet: '#131317',
  gold: '#E2BC6E', // gold: figures, badges, the brand
  goldSoft: 'rgba(226, 188, 110, 0.6)',
  glow: 'rgba(63, 224, 230, 0.45)',
  cream: '#EDEFF2',
  creamSoft: 'rgba(237, 239, 242, 0.75)',
  creamFaint: 'rgba(237, 239, 242, 0.4)',
  danger: '#FF6B6B',
  dangerFaint: 'rgba(255, 107, 107, 0.16)',
  ok: '#3DF5A6',
  info: '#3FE0E6',
  warn: '#E2BC6E',
  secret: '#FF2BD6', // fuchsia neon: the secret options
};

// The two formulas' looks: Secret Date (a couple, the brand) and Secret Squad (a band of friends).
export type PaletteName = 'date' | 'squad';
export const Palettes: Record<PaletteName, Record<ThemeColor, string>> = { date: brand, squad };
// Each one's name, on its cards like a card issuer's.
export const Brands: Record<PaletteName, string> = { date: 'Secret Date', squad: 'Secret Squad' };

// Cormorant Garamond for titles and names, Manrope for the text, Anton for Secret Squad's headings (loaded in _layout.tsx).
export const Fonts = {
  poster: 'Anton_400Regular', // Secret Squad's headings in place of the serif, by themed-text.tsx
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

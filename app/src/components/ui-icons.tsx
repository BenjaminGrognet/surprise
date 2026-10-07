import type { ReactNode } from 'react';
import Svg, { Circle, Path, Rect } from 'react-native-svg';

import { QUIZ_ICONS } from '@/components/quiz-icons';

// The interface's own line icons, drawn like the quiz's (24×24, round strokes): the tab bar, the round buttons.
const UI_ICONS: Record<string, ReactNode> = {
  cloche: (
    <>
      <Path d="M10.27 21a2 2 0 0 0 3.46 0" />
      <Path d="M3.26 15.33A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.67C19.41 13.96 18 12.5 18 8A6 6 0 0 0 6 8c0 4.5-1.41 5.96-2.74 7.33" />
    </>
  ),
  calendrier: (
    <>
      <Path d="M8 2v4M16 2v4" />
      <Rect x="3" y="4" width="18" height="18" rx="2" />
      <Path d="M3 10h18M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01" />
    </>
  ),
  profil: (
    <>
      <Path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
      <Circle cx="12" cy="7" r="4" />
    </>
  ),
  retour: <Path d="m15 18-6-6 6-6" />,
  suite: <Path d="m9 18 6-6-6-6" />,
  livre: (
    <>
      <Path d="M12 7v14" />
      <Path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z" />
    </>
  ),
  // A step's vote: « on aime ce genre », « pas pour nous ».
  pouce_haut: (
    <>
      <Path d="M7 10v12" />
      <Path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z" />
    </>
  ),
  pouce_bas: (
    <>
      <Path d="M17 14V2" />
      <Path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z" />
    </>
  ),
  // The way from a step to the next (components/hop.tsx): footprints, a metro train seen from the front.
  a_pied: (
    <>
      <Path d="M4 16v-2.38C4 11.5 2.97 10.5 3 8c.03-2.72 1.49-6 4.5-6C9.37 2 10 3.8 10 5.5c0 3.11-2 5.66-2 8.68V16a2 2 0 1 1-4 0Z" />
      <Path d="M20 20v-2.38c0-2.12 1.03-3.12 1-5.62-.03-2.72-1.49-6-4.5-6C14.63 6 14 7.8 14 9.5c0 3.11 2 5.66 2 8.68V20a2 2 0 1 0 4 0Z" />
      <Path d="M16 17h4M4 13h4" />
    </>
  ),
  metro: (
    <>
      <Rect x="4" y="3" width="16" height="16" rx="2" />
      <Path d="M4 11h16M12 3v8M8 19l-2 3M18 22l-2-3M8 15h.01M16 15h.01" />
    </>
  ),
  // The couple's evenings: a closed grimoire, the secrets' ✦ on its cover.
  grimoire: (
    <>
      <Path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H19a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H6.5a1 1 0 0 1 0-5H20" />
      <Path d="M13 6l1 2.5 2.5 1-2.5 1-1 2.5-1-2.5-2.5-1 2.5-1z" />
    </>
  ),
};

// One icon by name: the interface's, or else the quiz's.
export function Icon({ name, size = 22, color, strokeWidth = 1.6 }: { name: string; size?: number; color: string; strokeWidth?: number }) {
  const shape = UI_ICONS[name] ?? QUIZ_ICONS[name];
  if (!shape) return null;
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
      {shape}
    </Svg>
  );
}

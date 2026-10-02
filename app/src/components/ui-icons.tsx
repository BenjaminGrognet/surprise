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

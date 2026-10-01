import type { ReactNode } from 'react';
import { Circle, Ellipse, Path, Rect } from 'react-native-svg';

// The quiz's gold line icons (24×24, stroked by OptionCard), named by the server's `icon` (quiz.py).
export const QUIZ_ICONS: Record<string, ReactNode> = {
  // Votre histoire en est où ?
  pousse: (
    <>
      <Path d="M7 20h10" />
      <Path d="M10 20c5.5-2.5.8-6.4 3-10" />
      <Path d="M9.5 9.4c1.1.8 1.8 2.2 2.3 3.7-2 .4-3.5.4-4.8-.3-1.2-.6-2.3-1.9-3-4.2 2.8-.5 4.4 0 5.5.8z" />
      <Path d="M14.1 6a7 7 0 0 0-1.1 4c1.9-.1 3.3-.6 4.3-1.4 1-1 1.6-2.3 1.7-4.6-2.7.1-4 1-4.9 2z" />
    </>
  ),
  coeur: (
    <Path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z" />
  ),
  flamme: (
    <Path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.07-2.14-.22-4.05 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.15.43-2.29 1-3a2.5 2.5 0 0 0 2.5 2.5z" />
  ),
  infini: (
    <Path d="M12 12c-2-2.67-4-4-6-4a4 4 0 1 0 0 8c2 0 4-1.33 6-4Zm0 0c2 2.67 4 4 6 4a4 4 0 0 0 0-8c-2 0-4 1.33-6 4Z" />
  ),

  // Votre soirée idéale commence par…
  couchant: (
    <>
      <Path d="M12 10V2" />
      <Path d="m4.93 10.93 1.41 1.41M2 18h2M20 18h2M19.07 10.93l-1.41 1.41M22 22H2" />
      <Path d="m16 6-4 4-4-4" />
      <Path d="M16 18a4 4 0 0 0-8 0" />
    </>
  ),
  monument: (
    <>
      <Path d="M3 22h18M6 18v-7M10 18v-7M14 18v-7M18 18v-7M4 18h16" />
      <Path d="M12 2 20 7H4z" />
    </>
  ),
  cible: (
    <>
      <Circle cx="12" cy="12" r="10" />
      <Circle cx="12" cy="12" r="6" />
      <Circle cx="12" cy="12" r="2" />
    </>
  ),
  bougie: (
    <>
      <Path d="M12 2c-1 2-2 3-2 4.5a2 2 0 0 0 4 0C14 5 13 4 12 2z" />
      <Rect x="9" y="10" width="6" height="12" rx="1" />
    </>
  ),
  pinceau: (
    <>
      <Path d="m9.06 11.9 8.07-8.06a2.85 2.85 0 1 1 4.03 4.03l-8.06 8.08" />
      <Path d="M7.07 14.94c-1.66 0-3 1.35-3 3.02 0 1.33-2.5 1.52-2 2.02 1.08 1.1 2.49 2.02 4 2.02 2.2 0 4-1.8 4-4.04a3.01 3.01 0 0 0-3-3.02z" />
    </>
  ),

  // Plutôt cocooning ou dancefloor ?
  lune: <Path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />,
  tasse: (
    <>
      <Path d="M6 2v2M10 2v2M14 2v2" />
      <Path d="M16 8a1 1 0 0 1 1 1v8a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4V9a1 1 0 0 1 1-1h14a4 4 0 1 1 0 8h-1" />
    </>
  ),
  boussole: (
    <>
      <Circle cx="12" cy="12" r="10" />
      <Path d="m16.24 7.76-1.8 5.41a2 2 0 0 1-1.27 1.27L7.76 16.24l1.8-5.41a2 2 0 0 1 1.27-1.27z" />
    </>
  ),
  etincelles: (
    <>
      <Path d="M9.94 15.5A2 2 0 0 0 8.5 14.06l-6.14-1.58a.5.5 0 0 1 0-.96L8.5 9.94A2 2 0 0 0 9.94 8.5l1.58-6.14a.5.5 0 0 1 .96 0l1.58 6.14a2 2 0 0 0 1.44 1.44l6.14 1.58a.5.5 0 0 1 0 .96l-6.14 1.58a2 2 0 0 0-1.44 1.44l-1.58 6.14a.5.5 0 0 1-.96 0z" />
      <Path d="M20 3v4M22 5h-4" />
    </>
  ),
  disco: (
    <>
      <Path d="M12 1v2" />
      <Circle cx="12" cy="13" r="9" />
      <Ellipse cx="12" cy="13" rx="4" ry="9" />
      <Path d="M3 13h18M4.5 8.5h15M4.5 17.5h15" />
    </>
  ),

  // Une soirée réussie, c'est quand…
  rires: (
    <>
      <Circle cx="12" cy="12" r="10" />
      <Path d="M8 14s1.5 2 4 2 4-2 4-2" strokeLinecap="round" />
      <Path d="M9 9h.01M15 9h.01" strokeLinecap="round" strokeWidth={2} />
    </>
  ),
  yeux: (
    <>
      <Path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z" />
      <Circle cx="12" cy="12" r="3" />
    </>
  ),
  esprit: (
    <>
      <Path d="M12 22c5.52 0 10-4.48 10-10S17.52 2 12 2 2 6.48 2 12s4.48 10 10 10z" />
      <Path d="M12 6v6l4 2" strokeLinecap="round" />
    </>
  ),
  objet: <Path d="M6 3h12l2 6H4l2-6zM4 9v10a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9" />,
  musique: (
    <>
      <Path d="M9 18V5l12-2v13" />
      <Circle cx="6" cy="18" r="3" />
      <Circle cx="18" cy="16" r="3" />
    </>
  ),
  frissons: <Path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z" strokeLinecap="round" strokeLinejoin="round" />,

  // Jusqu'où osez-vous ?
  ancre: (
    <>
      <Path d="M12 22V8" />
      <Path d="M5 12H2a10 10 0 0 0 20 0h-3" />
      <Circle cx="12" cy="5" r="3" />
    </>
  ),
  plume: (
    <>
      <Path d="M20.24 12.24a6 6 0 0 0-8.49-8.49L5 10.5V19h8.5z" />
      <Path d="M16 8 2 22M17.5 15H9" />
    </>
  ),
  cadeau: (
    <>
      <Rect x="3" y="8" width="18" height="4" rx="1" />
      <Path d="M12 8v13" />
      <Path d="M19 12v7a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-7" />
      <Path d="M7.5 8a2.5 2.5 0 0 1 0-5A4.8 8 0 0 1 12 8a4.8 8 0 0 1 4.5-5 2.5 2.5 0 0 1 0 5" />
    </>
  ),
  fusee: (
    <>
      <Path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z" />
      <Path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z" />
      <Path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5" />
    </>
  ),

  // La bande-son de votre couple ?
  note: (
    <>
      <Circle cx="8" cy="18" r="4" />
      <Path d="M12 18V2l7 4" />
    </>
  ),
  piano: (
    <>
      <Path d="M18.5 8c-1.4 0-2.6-.8-3.2-2A6.87 6.87 0 0 0 2 9v11a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-8.5C22 9.6 20.4 8 18.5 8" />
      <Path d="M2 14h20M6 14v4M10 14v4M14 14v4M18 14v4" />
    </>
  ),
  casque: (
    <Path d="M3 14h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a9 9 0 0 1 18 0v7a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3" />
  ),
  enceinte: (
    <>
      <Rect x="4" y="2" width="16" height="20" rx="2" />
      <Circle cx="12" cy="14" r="4" />
      <Path d="M12 6h.01" strokeLinecap="round" strokeWidth={2} />
    </>
  ),
  micro: (
    <>
      <Rect x="9" y="2" width="6" height="13" rx="3" />
      <Path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v3" />
    </>
  ),
  tambour: (
    <>
      <Path d="m2 2 8 8M22 2l-8 8" />
      <Ellipse cx="12" cy="9" rx="10" ry="5" />
      <Path d="M7 13.4v7.9M12 14v8M17 13.4v7.9M2 9v8a10 5 0 0 0 20 0V9" />
    </>
  ),

  // Ce que vous ne voulez jamais
  vagues: (
    <Path d="M2 6c.6.5 1.2 1 2.5 1C7 7 7 5 9.5 5c2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1M2 12c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1M2 18c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1" />
  ),
  oeil_ferme: (
    <>
      <Path d="M10.73 5.08a10.74 10.74 0 0 1 11.2 6.57 1 1 0 0 1 0 .7 10.75 10.75 0 0 1-1.44 2.49" />
      <Path d="M14.08 14.16a3 3 0 0 1-4.24-4.24" />
      <Path d="M17.48 17.5a10.75 10.75 0 0 1-15.42-5.15 1 1 0 0 1 0-.7 10.75 10.75 0 0 1 4.45-5.14" />
      <Path d="m2 2 20 20" />
    </>
  ),
  fantome: (
    <>
      <Path d="M9 10h.01M15 10h.01" strokeLinecap="round" strokeWidth={2} />
      <Path d="M12 2a8 8 0 0 0-8 8v12l3-3 2.5 2.5L12 19l2.5 2.5L17 19l3 3V10a8 8 0 0 0-8-8z" />
    </>
  ),
  goutte: <Path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z" />,
  verre: (
    <>
      <Path d="M8 22h8M7 10h10M12 15v7" />
      <Path d="M12 15a5 5 0 0 0 5-5c0-2-.5-4-2-8H9c-1.5 4-2 6-2 8a5 5 0 0 0 5 5Z" />
    </>
  ),
  projecteur: (
    <>
      <Path d="M9 2h6l-1 5h-4z" />
      <Path d="M10 7 5 21h14L14 7" />
      <Path d="M3 22h18" />
    </>
  ),
  fauteuil: (
    <>
      <Path d="M19 9V6a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v3" />
      <Path d="M3 16a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-5a2 2 0 0 0-4 0v1.5a.5.5 0 0 1-.5.5h-9a.5.5 0 0 1-.5-.5V11a2 2 0 0 0-4 0z" />
      <Path d="M5 18v2M19 18v2" />
    </>
  ),
  voilier: (
    <>
      <Path d="M22 18H2a4 4 0 0 0 4 4h12a4 4 0 0 0 4-4Z" />
      <Path d="M21 14 10 2 3 14h18Z" />
      <Path d="M10 2v16" />
    </>
  ),
  ecran: (
    <>
      <Rect x="2" y="3" width="20" height="14" rx="2" />
      <Path d="M8 21h8M12 17v4" />
    </>
  ),
  levres: (
    <>
      <Path d="M2 12c3-4 6-5.5 8-4.5L12 8.5l2-1c2-1 5 .5 8 4.5-3 4-6 6-10 6S5 16 2 12z" />
      <Path d="M2 12c4 1.5 16 1.5 20 0" />
    </>
  ),

  // Votre budget pour deux ?
  pieces: (
    <>
      <Circle cx="8" cy="8" r="6" />
      <Path d="M18.09 10.37A6 6 0 1 1 10.34 18" />
      <Path d="M7 6h1v4M16.71 13.88l.7.71-2.82 2.82" />
    </>
  ),
  portefeuille: (
    <>
      <Path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1" />
      <Path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4" />
    </>
  ),
  carte: (
    <>
      <Rect x="2" y="5" width="20" height="14" rx="2" />
      <Path d="M2 10h20" />
    </>
  ),
  diamant: (
    <>
      <Path d="M6 3h12l4 6-10 13L2 9Z" />
      <Path d="M11 3 8 9l4 13 4-13-3-6M2 9h20" />
    </>
  ),
};

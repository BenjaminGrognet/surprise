import { createContext, createElement, type ReactNode, useContext } from 'react';

import { Palettes, type PaletteName } from '@/constants/theme';

// The look of what is shown: Secret Date's (the brand, by default), or Secret Squad's for a band of friends' evening —
// its screens and cards wrapped in <PaletteProvider name="squad">. The app is dark by design: no light scheme.
const PaletteContext = createContext<PaletteName>('date');

export function PaletteProvider({ name, children }: { name: PaletteName; children: ReactNode }) {
  return createElement(PaletteContext.Provider, { value: name }, children);
}

export const usePalette = () => useContext(PaletteContext);

export function useTheme() {
  return Palettes[useContext(PaletteContext)];
}

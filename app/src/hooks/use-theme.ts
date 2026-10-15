import { createContext, createElement, type ReactNode, useContext } from 'react';

import { Palettes, type DateLook, type PaletteName } from '@/constants/theme';

// The look of what is shown: Secret Date's (the brand, by default), or Secret Squad's for a band of friends' evening —
// its screens and cards wrapped in <PaletteProvider name="squad">. The app is dark by design: no light scheme.
// Secret Date's look is the couple's choice on this device (LookContext, set at the root): the brand's, or « Minuit »
// once the complicity gauge unlocks it; every `date` palette then shows in it.
const PaletteContext = createContext<PaletteName>('date');

export const LookContext = createContext<{ look: DateLook; setLook: (look: DateLook) => void }>({ look: 'date', setLook: () => {} });
export const useLook = () => useContext(LookContext);

export function PaletteProvider({ name, children }: { name: PaletteName; children: ReactNode }) {
  return createElement(PaletteContext.Provider, { value: name }, children);
}

export function usePalette(): PaletteName {
  const name = useContext(PaletteContext);
  const { look } = useContext(LookContext);
  return name === 'date' ? look : name;
}

export function useTheme() {
  return Palettes[usePalette()];
}

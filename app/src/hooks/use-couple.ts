import { createContext, useContext } from 'react';

import type { AccountRole } from '@/lib/couple';

// Who the signed-in account is in its couple, read once by the root layout and shared with every screen.
export type CoupleContextValue = { role: AccountRole; refresh: () => Promise<void> };

export const CoupleContext = createContext<CoupleContextValue>({
  role: 'instigateur',
  refresh: async () => {},
});

export const useCouple = () => useContext(CoupleContext);

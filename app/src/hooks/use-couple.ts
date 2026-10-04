import { createContext, useContext } from 'react';

import type { AccountRole } from '@/lib/couple';

// Who the signed-in account is in its couple, read once by the root layout and shared with every screen; `userId`
// tells, evening by evening, which side the account is on (eveningRole).
export type CoupleContextValue = { role: AccountRole; userId: string | null; refresh: () => Promise<void> };

export const CoupleContext = createContext<CoupleContextValue>({
  role: 'instigateur',
  userId: null,
  refresh: async () => {},
});

export const useCouple = () => useContext(CoupleContext);

import { useEffect, useState } from 'react';

import { TextLink } from '@/components/buttons';
import { OptionRow } from '@/components/option-button';
import { currentUser } from '@/lib/account';
import { supabaseConfigured } from '@/lib/supabase';

// Invisible while accounts aren't configured.
export function AccountNav() {
  const [signedIn, setSignedIn] = useState(false);

  useEffect(() => {
    if (!supabaseConfigured) return;
    currentUser().then((u) => setSignedIn(!!u));
  }, []);

  if (!supabaseConfigured) return null;
  return (
    <OptionRow>
      <TextLink href={signedIn ? '/historique' : '/compte'}>{signedIn ? 'Mon historique' : 'Se connecter'}</TextLink>
      {signedIn && <TextLink href="/compte">Mon compte</TextLink>}
    </OptionRow>
  );
}

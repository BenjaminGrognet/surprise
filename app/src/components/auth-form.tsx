import { type ReactNode, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { PrimaryButton } from '@/components/buttons';
import { TextField } from '@/components/text-field';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { signIn, signUp } from '@/lib/account';

type TabKey = 'in' | 'up';

// Sign in or create an account (Supabase Auth, email + password); `onSignedIn` decides what comes next.
export function AuthForm({ onSignedIn, startWith = 'in', signUpLabel = 'Créer notre compte' }: {
  onSignedIn: () => void;
  startWith?: TabKey;
  signUpLabel?: string;
}) {
  const theme = useTheme();
  const [tab, setTab] = useState<TabKey>(startWith);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  async function submit() {
    setError('');
    try {
      if (tab === 'in') await signIn(email, password);
      else await signUp(email, password);
      onSignedIn();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <>
      <View style={[styles.tabs, { backgroundColor: theme.backgroundElement, borderColor: theme.line }]}>
        <Tab label="Se connecter" active={tab === 'in'} onPress={() => setTab('in')} />
        <Tab label="Créer un compte" active={tab === 'up'} onPress={() => setTab('up')} />
      </View>
      <View style={styles.form}>
        <Field label="Email">
          <TextField value={email} onChangeText={setEmail} autoComplete="email" keyboardType="email-address" autoCapitalize="none" />
        </Field>
        <Field label="Mot de passe">
          <TextField
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            autoComplete={tab === 'in' ? 'current-password' : 'new-password'}
          />
        </Field>
        {error ? <ThemedText themeColor="danger">{error}</ThemedText> : null}
        <PrimaryButton wide onPress={submit}>{tab === 'in' ? 'Se connecter' : signUpLabel}</PrimaryButton>
      </View>
    </>
  );
}

function Tab({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  const theme = useTheme();
  return (
    <Pressable onPress={onPress} style={[styles.tab, active && { backgroundColor: theme.satin }]}>
      <ThemedText type="smallBold" themeColor={active ? 'onAccent' : 'textSecondary'}>{label}</ThemedText>
    </Pressable>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <View style={styles.field}>
      <ThemedText type="smallBold">{label}</ThemedText>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  tabs: { flexDirection: 'row', gap: 4, borderRadius: 999, borderWidth: 1, padding: 4, alignSelf: 'flex-start' },
  tab: { paddingVertical: Spacing.two, paddingHorizontal: Spacing.three, borderRadius: 999 },
  form: { gap: Spacing.three, maxWidth: 420 },
  field: { gap: Spacing.two },
});

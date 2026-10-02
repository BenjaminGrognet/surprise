import { type ReactNode, useRef, useState } from 'react';
import { Pressable, TextInput, StyleSheet, View } from 'react-native';

import { PrimaryButton } from '@/components/buttons';
import { TextField } from '@/components/text-field';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { signIn, signUp } from '@/lib/account';

type TabKey = 'in' | 'up';

// Sign in or create an account (Supabase Auth, email + password); `onSignedIn` decides what comes next.
export function AuthForm({ onSignedIn, startWith = 'in', signUpLabel = 'Créer notre compte', compact }: {
  compact?: boolean;
  onSignedIn: () => void;
  startWith?: TabKey;
  signUpLabel?: string;
}) {
  const theme = useTheme();
  const [tab, setTab] = useState<TabKey>(startWith);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const emailRef = useRef<TextInput>(null);
  const pick = (key: TabKey) => { setTab(key); emailRef.current?.focus(); };

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
      <View style={[styles.tabs, compact && styles.tabsCompact, { backgroundColor: theme.backgroundElement, borderColor: theme.line }]}>
        <Tab label="Se connecter" active={tab === 'in'} onPress={() => pick('in')} />
        <Tab label="Créer un compte" active={tab === 'up'} onPress={() => pick('up')} />
      </View>
      <View style={[styles.form, compact && styles.formCompact]}>
        <Field label="Email" compact={compact}>
          <TextField ref={emailRef} style={compact ? styles.inputCompact : undefined} placeholder={compact ? "Email" : undefined} accessibilityLabel="Email" value={email} onChangeText={setEmail} autoComplete="email" keyboardType="email-address" autoCapitalize="none" />
        </Field>
        <Field label="Mot de passe" compact={compact}>
          <TextField
            style={compact ? styles.inputCompact : undefined}
            placeholder={compact ? "Mot de passe" : undefined}
            accessibilityLabel="Mot de passe"
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            returnKeyType="go"
            onSubmitEditing={submit}
            autoComplete={tab === 'in' ? 'current-password' : 'new-password'}
          />
        </Field>
        {error ? <ThemedText themeColor="danger">{error}</ThemedText> : null}
        <PrimaryButton wide compact={compact} onPress={submit}>{tab === 'in' ? 'Se connecter' : signUpLabel}</PrimaryButton>
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

function Field({ label, children, compact }: { label: string; children: ReactNode; compact?: boolean }) {
  return (
    <View style={styles.field}>
      {compact ? null : <ThemedText type="smallBold">{label}</ThemedText>}
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  tabs: { flexDirection: 'row', gap: 4, borderRadius: 999, borderWidth: 1, padding: 4, alignSelf: 'flex-start' },
  tab: { paddingVertical: 6, paddingHorizontal: Spacing.three, borderRadius: 999 },
  form: { gap: Spacing.three, maxWidth: 420 },
  tabsCompact: { padding: 3 },
  inputCompact: { paddingVertical: 9, paddingHorizontal: 12, fontSize: 15, borderRadius: 12 },
  formCompact: { gap: Spacing.two, maxWidth: '100%', alignSelf: 'stretch' },
  field: { gap: Spacing.two },
});

import AsyncStorage from '@react-native-async-storage/async-storage';
import { createClient } from '@supabase/supabase-js';
import { Platform } from 'react-native';

const supabaseUrl = process.env.EXPO_PUBLIC_SUPABASE_URL ?? '';
const supabaseAnonKey = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY ?? '';

export const supabaseConfigured = !!supabaseUrl;

// createClient() throws on an empty URL — pass a placeholder when accounts aren't configured
// (supabaseConfigured is checked everywhere before this client is actually used).
// On web, localStorage is fine and avoids pulling AsyncStorage into the web bundle's critical path.
export const supabase = createClient(supabaseUrl || 'https://placeholder.supabase.co', supabaseAnonKey || 'placeholder', {
  auth: {
    storage: Platform.OS === 'web' ? undefined : AsyncStorage,
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: false,
  },
});

// The signed-in account, if any.
export async function currentUser() {
  const { data } = await supabase.auth.getSession();
  return data.session?.user ?? null;
}

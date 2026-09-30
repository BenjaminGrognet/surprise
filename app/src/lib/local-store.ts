import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform } from 'react-native';

import type { Profile } from '@/lib/api';

// The couple's last profile, kept only on this device (mirrors the old localStorage use).
// A signed-in couple's profile also lives in Supabase, see lib/account.ts.
const KEY = 'surprise.profile';

export type RememberedProfile = { answers: Record<string, unknown>; profile: Profile };

async function getItem(key: string) {
  return Platform.OS === 'web' ? localStorage.getItem(key) : AsyncStorage.getItem(key);
}
async function setItem(key: string, value: string) {
  if (Platform.OS === 'web') return localStorage.setItem(key, value);
  await AsyncStorage.setItem(key, value);
}

export async function rememberProfile(answers: Record<string, unknown>, profile: Profile) {
  await setItem(KEY, JSON.stringify({ answers, profile }));
}

export async function forgetProfile() {
  if (Platform.OS === 'web') return localStorage.removeItem(KEY);
  await AsyncStorage.removeItem(KEY);
}

export async function rememberedProfile(): Promise<RememberedProfile | null> {
  try {
    return JSON.parse((await getItem(KEY)) || 'null');
  } catch {
    return null;
  }
}

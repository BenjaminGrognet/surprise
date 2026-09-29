import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform } from 'react-native';

// The couple's last profile id, kept only on this device (mirrors the old localStorage use).
const KEY = 'surprise.profile';

export async function rememberProfile(id: string) {
  if (Platform.OS === 'web') return localStorage.setItem(KEY, id);
  await AsyncStorage.setItem(KEY, id);
}

export async function rememberedProfile(): Promise<string | null> {
  if (Platform.OS === 'web') return localStorage.getItem(KEY);
  return AsyncStorage.getItem(KEY);
}

import { Image } from 'expo-image';

// `round`: in a circle, like a portrait (the headers); else the app icon's rounded square.
export function LogoSecretDate({ size = 40, round }: { size?: number; round?: boolean }) {
  return (
    <Image
      source={require('@/assets/images/logo-secretdate.png')}
      style={{ width: size, height: size, borderRadius: round ? size / 2 : size * 0.22 }}
      contentFit="cover"
      accessibilityLabel="Secret Date"
    />
  );
}

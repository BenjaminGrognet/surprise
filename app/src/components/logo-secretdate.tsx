import { Image } from 'expo-image';

// `round`: in a circle, like a portrait (the headers); else the app icon's rounded square. Its 256 px copy (20 KB):
// shown at 30 to 54 pt, three times that on the story postcard; the 1024 px one (1.6 MB) is for the app's icons.
export function LogoSecretDate({ size = 40, round }: { size?: number; round?: boolean }) {
  return (
    <Image
      source={require('@/assets/images/logo-secretdate-256.jpg')}
      style={{ width: size, height: size, borderRadius: round ? size / 2 : size * 0.22 }}
      contentFit="cover"
      accessibilityLabel="Secret Date"
    />
  );
}

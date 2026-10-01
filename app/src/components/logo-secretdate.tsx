import { Image } from 'expo-image';

export function LogoSecretDate({ size = 40 }: { size?: number }) {
  return (
    <Image
      source={require('@/assets/images/logo-secretdate.png')}
      style={{ width: size, height: size, borderRadius: size * 0.22 }}
      contentFit="cover"
      accessibilityLabel="Secret Date"
    />
  );
}

import * as Location from 'expo-location';

const NEAR_METERS = 250;

function meters(a: { lat: number; lon: number }, b: { lat: number; lon: number }) {
  const rad = Math.PI / 180;
  const h =
    Math.sin(((b.lat - a.lat) * rad) / 2) ** 2 +
    Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(((b.lon - a.lon) * rad) / 2) ** 2;
  return 12_742_000 * Math.asin(Math.sqrt(h));
}

// "Je suis arrivé(e)": near the step by the phone's position → true; far → false; position unavailable or
// refused → null (the passager is trusted: it's their own surprise).
export async function nearStep(step: { lat: number; lon: number }): Promise<boolean | null> {
  try {
    const { status } = await Location.requestForegroundPermissionsAsync();
    if (status !== 'granted') return null;
    const here = await Location.getCurrentPositionAsync({});
    return meters({ lat: here.coords.latitude, lon: here.coords.longitude }, step) <= NEAR_METERS;
  } catch {
    return null;
  }
}

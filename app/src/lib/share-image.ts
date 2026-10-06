// A view shared as an image, on a phone: captured at 1080 px wide (react-native-view-shot), then offered to the share
// sheet (expo-sharing): a story, a message, the photos. The web has its own (share-image.web.ts).
import * as Sharing from 'expo-sharing';
import { PixelRatio, type View } from 'react-native';
import { captureRef } from 'react-native-view-shot';

const WIDTH = 1080;

export async function shareImage(view: View, name: string) {
  // view-shot sizes in points: 1080 pixels whatever the phone's density.
  const uri = await captureRef(view, { format: 'png', quality: 1, width: WIDTH / PixelRatio.get(), result: 'tmpfile', fileName: name });
  await Sharing.shareAsync(uri, { mimeType: 'image/png', UTI: 'public.png', dialogTitle: 'Partager la carte' });
}

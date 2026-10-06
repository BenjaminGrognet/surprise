// A view shared as an image, on the web: drawn at 1080 px wide with its fonts (html-to-image), then offered to the
// share sheet on a phone's browser, else downloaded.
import { toBlob } from 'html-to-image';
import type { View } from 'react-native';

const WIDTH = 1080;

export async function shareImage(view: View, name: string) {
  // On the web, a View's ref is its element.
  const node = view as unknown as HTMLElement;
  const blob = await toBlob(node, { pixelRatio: WIDTH / node.offsetWidth });
  if (!blob) throw new Error("L'image n'a pas pu être dessinée.");
  const file = new File([blob], `${name}.png`, { type: 'image/png' });
  if (matchMedia('(pointer: coarse)').matches && navigator.canShare?.({ files: [file] })) {
    await navigator.share({ files: [file] });
    return;
  }
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = file.name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

// A card printed from a phone (expo-print): the system's print sheet, or a PDF to send or keep. The web has its own
// (print-card.web.ts).
import * as Print from 'expo-print';
import * as Sharing from 'expo-sharing';

// A6 landscape, in points.
const A6 = { width: 420, height: 298 };

export async function printCard(html: string) {
  await Print.printAsync({ html, ...A6 });
}

export async function shareCardPdf(html: string) {
  const { uri } = await Print.printToFileAsync({ html, ...A6 });
  await Sharing.shareAsync(uri, { mimeType: 'application/pdf', UTI: 'com.adobe.pdf', dialogTitle: "Carton d'invitation" });
}

export const canShareCardPdf = true;

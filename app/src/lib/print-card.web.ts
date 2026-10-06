// A card printed from the browser: the page opens in a window of its own and asks to print once its fonts are in,
// where the browser also offers to save it as a PDF.
export async function printCard(html: string) {
  const page = window.open('', '_blank');
  if (!page) throw new Error('Autorisez les fenêtres de ce site pour imprimer le carton.');
  page.document.write(html.replace('</body>', '<script>window.addEventListener("load", () => document.fonts.ready.then(() => window.print()));</script></body>'));
  page.document.close();
}

// The browser saves the PDF from its print window.
export async function shareCardPdf() {}

export const canShareCardPdf = false;

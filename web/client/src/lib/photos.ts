// Photos of the listener's kit (0.83.0): shrunk and re-saved here before they leave the phone, so what's sent is a
// plain JPEG of about half a megabyte with none of the original's metadata (where it was taken among it). The server
// re-saves each again and keeps none once the coach's turn has read it.

/** Photos in one message: a few corners of a room. The server holds the same number (webapp/photos.py). */
export const MOST_PHOTOS = 3;
/** Pixels on the longer side: enough to read the numbers on a dumbbell. */
const EDGE = 1600;
const QUALITY = 0.85;

/** The photo's pixels, upright, as the browser draws them. */
async function drawable(file: Blob): Promise<{ source: CanvasImageSource; width: number; height: number; done: () => void }> {
  if (typeof createImageBitmap === "function") {
    const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
    return { source: bitmap, width: bitmap.width, height: bitmap.height, done: () => bitmap.close() };
  }
  const url = URL.createObjectURL(file);
  const img = new Image();
  img.src = url;
  await img.decode();
  return { source: img, width: img.naturalWidth, height: img.naturalHeight, done: () => URL.revokeObjectURL(url) };
}

/** A photo as the server takes it: drawn again at most EDGE pixels on its longer side, a JPEG in base64. */
export async function shrink(file: Blob): Promise<string> {
  const { source, width, height, done } = await drawable(file);
  try {
    const scale = Math.min(1, EDGE / Math.max(width, height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(width * scale));
    canvas.height = Math.max(1, Math.round(height * scale));
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("This browser can't read photos.");
    ctx.drawImage(source, 0, 0, canvas.width, canvas.height);
    const url = canvas.toDataURL("image/jpeg", QUALITY);
    return url.slice(url.indexOf(",") + 1);
  } finally {
    done();
  }
}

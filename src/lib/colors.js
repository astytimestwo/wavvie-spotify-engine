export async function extractDominantColor(url) {
  if (!url) return "#7C3AED";

  return new Promise((resolve) => {
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => {
      try {
        const canvas = document.createElement("canvas");
        canvas.width = 10;
        canvas.height = 10;
        const ctx = canvas.getContext("2d", { willReadFrequently: true });
        const sx = Math.max(0, image.naturalWidth / 2 - 5);
        const sy = Math.max(0, image.naturalHeight / 2 - 5);
        ctx.drawImage(image, sx, sy, 10, 10, 0, 0, 10, 10);
        const pixels = ctx.getImageData(0, 0, 10, 10).data;
        let r = 0;
        let g = 0;
        let b = 0;
        for (let i = 0; i < pixels.length; i += 4) {
          r += pixels[i];
          g += pixels[i + 1];
          b += pixels[i + 2];
        }
        const count = pixels.length / 4;
        const toHex = (value) => Math.round(value / count).toString(16).padStart(2, "0");
        resolve(`#${toHex(r)}${toHex(g)}${toHex(b)}`);
      } catch {
        resolve("#7C3AED");
      }
    };
    image.onerror = () => resolve("#7C3AED");
    image.src = url;
  });
}

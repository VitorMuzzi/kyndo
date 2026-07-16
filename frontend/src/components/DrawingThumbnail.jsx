import React, { useEffect, useRef } from 'react';

const CANVAS_BG = '#0f172a';

// Renders a small preview of a drawing's dataURL, auto-cropped to the actual
// drawn content instead of the full (mostly empty) 2400x1400 canvas — a plain
// scaled-down <img> squeezes the artwork into an unrecognizable corner.
export default function DrawingThumbnail({ src, size = 56 }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = CANVAS_BG;
    ctx.fillRect(0, 0, size, size);
    if (!src) return;

    let cancelled = false;
    const img = new Image();
    img.onload = () => {
      if (cancelled || !img.width) return;
      const sampleW = 300;
      const scale = sampleW / img.width;
      const sampleH = Math.round(img.height * scale);
      const off = document.createElement('canvas');
      off.width = sampleW; off.height = sampleH;
      const octx = off.getContext('2d');
      octx.drawImage(img, 0, 0, sampleW, sampleH);

      let minX = sampleW, minY = sampleH, maxX = 0, maxY = 0, found = false;
      const { data } = octx.getImageData(0, 0, sampleW, sampleH);
      for (let y = 0; y < sampleH; y++) {
        for (let x = 0; x < sampleW; x++) {
          if (data[(y * sampleW + x) * 4 + 3] > 10) {
            found = true;
            if (x < minX) minX = x;
            if (x > maxX) maxX = x;
            if (y < minY) minY = y;
            if (y > maxY) maxY = y;
          }
        }
      }
      if (!found) return; // blank drawing — leave the plain background

      const pad = 6;
      minX = Math.max(0, minX - pad); minY = Math.max(0, minY - pad);
      maxX = Math.min(sampleW, maxX + pad); maxY = Math.min(sampleH, maxY + pad);

      const origX = minX / scale, origY = minY / scale;
      const origW = (maxX - minX) / scale, origH = (maxY - minY) / scale;
      const fitScale = Math.min(size / origW, size / origH);
      const drawW = origW * fitScale, drawH = origH * fitScale;

      ctx.drawImage(img, origX, origY, origW, origH, (size - drawW) / 2, (size - drawH) / 2, drawW, drawH);
    };
    img.src = src;
    return () => { cancelled = true; };
  }, [src, size]);

  return <canvas ref={canvasRef} width={size} height={size} className="rounded border border-gray-200 shrink-0"/>;
}

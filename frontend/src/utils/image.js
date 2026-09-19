// Turns a camera frame or a picked file into a small JPEG.
//
// Why: phones hand over multi-megabyte photos and iPhones default to HEIC,
// which the server (Pillow) rejects with "not a valid image". Decoding in the
// browser and re-encoding as a ~1280px JPEG makes every source uniform, and
// uploads over shop Wi-Fi in a fraction of the time.
const MAX_SIDE = 1280
const QUALITY = 0.85

async function decode(file) {
  if (window.createImageBitmap) {
    try {
      // 'from-image' applies the EXIF rotation so portrait photos aren't sideways.
      return await createImageBitmap(file, { imageOrientation: 'from-image' })
    } catch {
      try {
        return await createImageBitmap(file) // older Safari has no options argument
      } catch {
        // fall through to the <img> decoder
      }
    }
  }
  const url = URL.createObjectURL(file)
  try {
    const img = new Image()
    img.src = url
    await img.decode()
    return img
  } finally {
    URL.revokeObjectURL(url)
  }
}

function drawScaled(source, width, height) {
  const scale = Math.min(1, MAX_SIDE / Math.max(width, height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.max(1, Math.round(width * scale))
  canvas.height = Math.max(1, Math.round(height * scale))
  const context = canvas.getContext('2d')
  context.fillStyle = '#ffffff' // JPEG has no transparency (PNG logos would go black)
  context.fillRect(0, 0, canvas.width, canvas.height)
  context.drawImage(source, 0, 0, canvas.width, canvas.height)
  return canvas
}

function toJpegFile(canvas) {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) =>
        blob
          ? resolve(new File([blob], 'photo.jpg', { type: 'image/jpeg' }))
          : reject(new Error('encode failed')),
      'image/jpeg',
      QUALITY,
    )
  })
}

export function jpegFromVideo(video) {
  return toJpegFile(drawScaled(video, video.videoWidth, video.videoHeight))
}

export async function jpegFromFile(file) {
  const source = await decode(file)
  try {
    const width = source.naturalWidth || source.width
    const height = source.naturalHeight || source.height
    return await toJpegFile(drawScaled(source, width, height))
  } finally {
    source.close?.()
  }
}

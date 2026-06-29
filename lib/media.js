export async function downloadMedia(mediaId) {
  try {
    const res = await fetch(
      `https://waba-v2.360dialog.io/media/${mediaId}`,
      {
        headers: {
          'D360-API-KEY': process.env.DIALOG360_API_KEY
        }
      }
    )

    if (!res.ok) {
      console.error('Media download failed:', res.status)
      return null
    }

    const buffer = await res.arrayBuffer()
    const base64 = Buffer.from(buffer).toString('base64')
    const mimeType = res.headers.get('content-type') || 'image/jpeg'

    return { base64, mimeType }

  } catch (err) {
    console.error('Media download error:', err.message)
    return null
  }
}
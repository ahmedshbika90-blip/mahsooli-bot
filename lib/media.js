import axios from 'axios'

export async function downloadMedia(mediaId, mediaUrl) {
  try {
    console.log('Downloading from URL:', mediaUrl)

    const res = await axios.get(
      mediaUrl,
      {
        headers: {
          'D360-API-KEY': process.env.DIALOG360_API_KEY
        },
        responseType: 'arraybuffer',
        timeout: 10000
      }
    )

    console.log('Media download status:', res.status)

    const base64 = Buffer.from(res.data).toString('base64')
    const mimeType = res.headers['content-type'] || 'image/jpeg'

    console.log('Media downloaded successfully')
    return { base64, mimeType }

  } catch (err) {
    console.error('Media download failed:', err.response?.status)
    console.error('Media download error:', err.message)
    return null
  }
}
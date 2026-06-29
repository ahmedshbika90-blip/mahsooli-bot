import axios from 'axios'

export async function downloadMedia(mediaId, mediaUrl) {
  try {
    console.log('Downloading from URL:', mediaUrl)

    // Use the full Facebook URL but proxy through 360dialog
    // Extract the path from the lookaside URL
    const urlObj = new URL(mediaUrl)
    const mid = urlObj.searchParams.get('mid')
    const ext = urlObj.searchParams.get('ext')
    const hash = urlObj.searchParams.get('hash')

   const dlUrl = `https://waba-v2.360dialog.io/whatsapp_business/attachments/?mid=${mid}&source=webhook&ext=${ext}&hash=${hash}`
    console.log('Constructed URL:', dlUrl)

    const res = await axios.get(dlUrl, {
      headers: {
        'D360-API-KEY': process.env.DIALOG360_API_KEY
      },
      responseType: 'arraybuffer',
      timeout: 10000
    })

    console.log('Media download status:', res.status)

    const base64 = Buffer.from(res.data).toString('base64')
    const mimeType = res.headers['content-type'] || 'image/jpeg'

    console.log('Media downloaded successfully, size:', res.data.byteLength)
    return { base64, mimeType }

  } catch (err) {
    console.error('Media download failed:', err.response?.status)
    console.error('Media download error:', err.response?.data?.toString() || err.message)
    return null
  }
}
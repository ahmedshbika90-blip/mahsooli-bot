import { getAdmin } from './firestore.js'

export async function uploadIdPhoto(mediaBase64, mimeType, phone) {
  try {
    const { admin } = await getAdmin()
    const bucket = admin.storage().bucket()
    
    const extension = mimeType.includes('png') ? 'png' : 'jpg'
    const filename = `id-photos/${phone}_${Date.now()}.${extension}`
    const file = bucket.file(filename)

    const buffer = Buffer.from(mediaBase64, 'base64')

    await file.save(buffer, {
      metadata: { contentType: mimeType },
      public: false
    })

    const [url] = await file.getSignedUrl({
      action:  'read',
      expires: '01-01-2035'
    })

    return url

  } catch (err) {
    console.error('Storage upload failed:', err.message)
    return null
  }
}
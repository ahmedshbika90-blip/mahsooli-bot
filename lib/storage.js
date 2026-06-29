import admin from 'firebase-admin'

export async function uploadIdPhoto(mediaBase64, mimeType, phone) {
  try {
    const bucket = admin.storage().bucket()
    
    const extension = mimeType.includes('png') ? 'png' : 'jpg'
    const filename = `id-photos/${phone}_${Date.now()}.${extension}`
    const file = bucket.file(filename)

    const buffer = Buffer.from(mediaBase64, 'base64')

    await file.save(buffer, {
      metadata: { contentType: mimeType },
      public: false
    })

    // Get a signed URL valid for 10 years
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
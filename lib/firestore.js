import admin from 'firebase-admin'

if (!admin.apps.length) {
  admin.initializeApp({
    credential: admin.credential.cert({
      projectId:   process.env.FIREBASE_ADMIN_PROJECT_ID,
      clientEmail: process.env.FIREBASE_ADMIN_CLIENT_EMAIL,
      privateKey:  process.env.FIREBASE_ADMIN_PRIVATE_KEY?.replace(/\\n/g, '\n')
    })
  })
}

const db = admin.firestore()

export async function saveToFirestore(phone, data) {
  try {
    await db.collection('registrations').doc(phone).set({
      ...data,
      registered_at: new Date().toISOString(),
      timestamp:     admin.firestore.FieldValue.serverTimestamp()
    })
    return true
  } catch (err) {
    console.error('Firestore save failed:', err.message)
    return false
  }
}
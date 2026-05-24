const DB_URL = process.env.FIREBASE_DATABASE_URL
const SECRET = process.env.FIREBASE_SECRET

export async function getSession(phone) {
  try {
    const res = await fetch(
      `${DB_URL}/sessions/${phone}.json?auth=${SECRET}`
    )
    const data = await res.json()

    console.log('Firebase raw data:', JSON.stringify(data))

    if (!data) return { step: 1, started: false, data: {} }

    return {
      step: data.step || 1,
      started: data.started || false,
      data: data.data || {}
    }

  } catch (err) {
    console.error('getSession failed:', err.message)
    return { step: 1, started: false, data: {} }
  }
}
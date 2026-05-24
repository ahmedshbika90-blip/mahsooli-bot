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

export async function saveSession(phone, session) {
  try {
    const res = await fetch(
      `${DB_URL}/sessions/${phone}.json?auth=${SECRET}`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(session)
      }
    )

    if (!res.ok) {
      console.error('saveSession failed:', res.status)
      return false
    }

    return true

  } catch (err) {
    console.error('saveSession failed:', err.message)
    return false
  }
}

export async function clearSession(phone) {
  try {
    await fetch(
      `${DB_URL}/sessions/${phone}.json?auth=${SECRET}`,
      { method: 'DELETE' }
    )
    return true
  } catch (err) {
    console.error('clearSession failed:', err.message)
    return false
  }
}
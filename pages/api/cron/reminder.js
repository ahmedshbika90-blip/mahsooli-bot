import { sendWhatsApp } from '../../../lib/whatsapp'

const DB_URL = process.env.FIREBASE_DATABASE_URL
const SECRET = process.env.FIREBASE_SECRET
const ONE_MINUTE = 1 * 60 * 1000
const TEN_MINUTES = 10 * 60 * 1000
const MAX_REMINDERS = 2

export default async function handler(req, res) {
  // temporarily disabled for debugging
   if (req.headers.authorization !== `Bearer ${process.env.CRON_SECRET}`) {
     return res.status(401).json({ error: 'Unauthorized' })
   }

  try {
    const response = await fetch(`${DB_URL}/sessions.json?auth=${SECRET}`)
    const sessions = await response.json()

    console.log('All sessions:', JSON.stringify(sessions))

    if (!sessions) return res.status(200).json({ sent: 0 })

    const now = Date.now()
    let sent = 0

    for (const [phone, session] of Object.entries(sessions)) {
      console.log(`Checking ${phone}:`, {
        completed:     session.completed,
        started:       session.started,
        last_activity: session.last_activity,
        inactive_ms:   session.last_activity ? now - session.last_activity : 'no activity',
        reminder_count: session.reminder_count
      })

      if (session.completed)      { console.log('skip: completed');      continue }
      if (!session.started)       { console.log('skip: not started');     continue }
      if (!session.last_activity) { console.log('skip: no last_activity'); continue }
      if (now - session.last_activity < ONE_MINUTE) { console.log('skip: too recent'); continue }
      if ((session.reminder_count || 0) >= MAX_REMINDERS) { console.log('skip: max reminders'); continue }

      console.log(`Sending reminder to ${phone}`)
      await sendWhatsApp(phone,
        `نذكّرك بأن استمارة التسجيل في برنامج التمويل الزراعي لا تزال غير مكتملة.\n\nإتمام التسجيل يضمن لك الاستفادة من البرنامج.\n\nاكتب  *2*  للمتابعة من حيث توقفت.`
      )

      await fetch(`${DB_URL}/sessions/${phone}.json?auth=${SECRET}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          last_reminder:   now,
          reminder_count:  (session.reminder_count || 0) + 1,
          awaiting_resume: true
        })
      })

      sent++
    }

    console.log(`Reminders sent: ${sent}`)
    return res.status(200).json({ sent })

  } catch (err) {
    console.error('Reminder cron error:', err.message)
    return res.status(500).json({ error: err.message })
  }
}
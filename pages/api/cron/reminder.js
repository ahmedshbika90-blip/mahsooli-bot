import { sendWhatsApp } from '../../../lib/whatsapp'

const DB_URL = process.env.FIREBASE_DATABASE_URL
const SECRET = process.env.FIREBASE_SECRET
const FIVE_MINUTES = 1 * 60 * 1000
const TEN_MINUTES  = 10 * 60 * 1000
const MAX_REMINDERS = 2

export default async function handler(req, res) {
  // Verify this is a legitimate Vercel cron call
  if (req.headers.authorization !== `Bearer ${process.env.CRON_SECRET}`) {
    return res.status(401).json({ error: 'Unauthorized' })
  }

  try {
    const response = await fetch(`${DB_URL}/sessions.json?auth=${SECRET}`)
    const sessions = await response.json()

    if (!sessions) return res.status(200).json({ sent: 0 })

    const now = Date.now()
    let sent = 0

    for (const [phone, session] of Object.entries(sessions)) {
      // Skip: completed, not started, no activity recorded
      if (session.completed)      continue
      if (!session.started)       continue
      if (!session.last_activity) continue

      // Skip: active in last 5 minutes
      if (now - session.last_activity < FIVE_MINUTES) continue

      // Skip: hit reminder limit
      if ((session.reminder_count || 0) >= MAX_REMINDERS) continue

      // Skip: reminder sent less than 10 minutes ago
      if (session.last_reminder && now - session.last_reminder < TEN_MINUTES) continue

      // Send reminder
  await sendWhatsApp(phone,
  `نذكّرك بأن استمارة التسجيل في برنامج التمويل الزراعي لا تزال غير مكتملة.\n\nإتمام التسجيل يضمن لك الاستفادة من البرنامج.\n\nاكتب  *2*  للمتابعة من حيث توقفت.`
)
      // Update session — mark awaiting_resume so we re-send the question on next message
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
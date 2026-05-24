import { getSession, advanceStep, saveAnswer, isAlreadyProcessed } from '../../utils/session'
import { validateAnswer } from '../../utils/validate'
import { sendWhatsApp } from '../../lib/whatsapp'
import { saveToSheets } from '../../lib/sheets'

const QUESTIONS = {
  1: 'What is your full name?',
  2: 'What is your phone number?',
  3: 'What is your email address?',
}

const ANSWER_KEYS = {
  1: 'name',
  2: 'phone_number',
  3: 'email',
}

const TOTAL_STEPS = 3

export default async function handler(req, res) {
  // verification handshake with 360dialog
  if (req.method === 'GET') {
    const token = req.headers['webhook_verify_token']
    if (token === process.env.WEBHOOK_VERIFY_TOKEN) {
      return res.status(200).send('Webhook verified')
    }
    return res.status(403).end()
  }

  if (req.method !== 'POST') return res.status(405).end()

  // acknowledge 360dialog immediately
  res.status(200).json({ status: 'ok' })

  // log raw body to see exact 360dialog payload structure
  console.log('BODY:', JSON.stringify(req.body))

  const messages = req.body?.messages
  if (!messages?.length) {
    console.log('No messages found — body keys:', Object.keys(req.body || {}))
    return
  }

  for (const message of messages) {
    const phone = message.from

    // skip duplicates
    if (isAlreadyProcessed(message.id)) continue

    // only handle text messages
    if (message.type !== 'text') {
      await sendWhatsApp(phone, 'Please reply with a text message only.')
      continue
    }

    const text = message.text.body.trim()
    if (!text) continue

    await handleMessage(phone, text)
  }
}

async function handleMessage(phone, text) {
  const session = getSession(phone)

  // validate the answer
  const error = validateAnswer(session.step, text)
  if (error) {
    await sendWhatsApp(phone, error)
    return
  }

  // save the answer to session
  const key = ANSWER_KEYS[session.step]
  saveAnswer(phone, key, text)

  // last step — save everything to Sheets
  if (session.step === TOTAL_STEPS) {
    const saved = await saveToSheets({
      phone,
      ...session.data,
      [key]: text
    })

    if (!saved) {
      await sendWhatsApp(phone, 'Something went wrong. Please try again.')
      return
    }

    await sendWhatsApp(phone, 'Thank you! Your registration is complete.')
    return
  }

  // advance to next step and ask next question
  advanceStep(phone)
  const nextSession = getSession(phone)
  await sendWhatsApp(phone, QUESTIONS[nextSession.step])
}
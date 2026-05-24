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
  if (req.method === 'GET') {
    const token = req.headers['webhook_verify_token']
    if (token === process.env.WEBHOOK_VERIFY_TOKEN) {
      return res.status(200).send('Webhook verified')
    }
    return res.status(403).end()
  }

  if (req.method !== 'POST') return res.status(405).end()

  const entry = req.body?.entry?.[0]
  const changes = entry?.changes?.[0]
  const messages = changes?.value?.messages

  if (!messages?.length) {
    return res.status(200).json({ status: 'ok' })
  }

  for (const message of messages) {
    const phone = message.from

    if (isAlreadyProcessed(message.id)) continue

    if (message.type !== 'text') {
      await sendWhatsApp(phone, 'Please reply with a text message only.')
      continue
    }

    const text = message.text.body.trim()
    if (!text) continue

    await handleMessage(phone, text)
  }

  return res.status(200).json({ status: 'ok' })
}

async function handleMessage(phone, text) {
  const session = getSession(phone)

  // new user — send the first question
  if (!session.started) {
    session.started = true
    await sendWhatsApp(phone, QUESTIONS[1])
    return
  }

  const error = validateAnswer(session.step, text)
  if (error) {
    await sendWhatsApp(phone, error)
    return
  }

  const key = ANSWER_KEYS[session.step]
  saveAnswer(phone, key, text)

  if (session.step === TOTAL_STEPS) {
    const dataToSave = { phone, ...session.data, [key]: text }

    const saved = await saveToSheets(dataToSave)

    if (!saved) {
      await sendWhatsApp(phone, 'Something went wrong saving your data. Please try again.')
      return
    }

    await sendWhatsApp(phone, 'Thank you! Your registration is complete.')
    return
  }

  advanceStep(phone)
  const nextSession = getSession(phone)
  await sendWhatsApp(phone, QUESTIONS[nextSession.step])
}
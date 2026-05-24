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

  res.status(200).json({ status: 'ok' })

  console.log('BODY:', JSON.stringify(req.body))

  const entry = req.body?.entry?.[0]
  const changes = entry?.changes?.[0]
  const messages = changes?.value?.messages

  if (!messages?.length) {
    console.log('No messages found')
    return
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
}

async function handleMessage(phone, text) {
  const session = getSession(phone)

  const error = validateAnswer(session.step, text)
  if (error) {
    await sendWhatsApp(phone, error)
    return
  }

  const key = ANSWER_KEYS[session.step]
  saveAnswer(phone, key, text)

  if (session.step === TOTAL_STEPS) {
    const dataToSave = { phone, ...session.data, [key]: text }

    // send confirmation immediately
    await sendWhatsApp(phone, 'Thank you! Your registration is complete.')

    // save to sheets in background — don't block
    saveToSheets(dataToSave).catch(err =>
      console.error('Sheets save failed:', err.message)
    )
    return
  }

  // advance and send next question
  advanceStep(phone)
  const nextSession = getSession(phone)
  await sendWhatsApp(phone, QUESTIONS[nextSession.step])
}
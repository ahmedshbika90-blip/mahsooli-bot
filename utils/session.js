const sessions = {}
const processedIds = new Set()

export function getSession(phone) {
  if (!sessions[phone]) {
    sessions[phone] = { step: 1, data: {}, started: false }
  }
  return sessions[phone]
}

export function advanceStep(phone) {
  if (sessions[phone]) {
    sessions[phone].step++
  }
}

export function resetSession(phone) {
  sessions[phone] = { step: 1, data: {}, started: false }
}

export function saveAnswer(phone, key, value) {
  if (!sessions[phone]) getSession(phone)
  sessions[phone].data[key] = value
}

export function isAlreadyProcessed(messageId) {
  if (processedIds.has(messageId)) return true
  processedIds.add(messageId)
  return false
}
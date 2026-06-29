const processedIds = new Set()

export function isAlreadyProcessed(messageId) {
  if (processedIds.has(messageId)) return true
  processedIds.add(messageId)
  return false
}
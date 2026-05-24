import { saveToSheets } from '../../lib/sheets'

export default async function handler(req, res) {
  const result = await saveToSheets({
    phone: '249916406516',
    name: 'Test Name',
    phone_number: '0501234567',
    email: 'test@test.com'
  })

  res.status(200).json({ success: result })
}
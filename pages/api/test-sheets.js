import { google } from 'googleapis'

export default async function handler(req, res) {
  try {
    const auth = new google.auth.GoogleAuth({
      credentials: {
        client_email: process.env.GOOGLE_SERVICE_ACCOUNT_EMAIL,
        private_key: process.env.GOOGLE_PRIVATE_KEY,
      },
      scopes: ['https://www.googleapis.com/auth/spreadsheets']
    })

    const sheets = google.sheets({ version: 'v4', auth })

    await sheets.spreadsheets.values.append({
      spreadsheetId: process.env.SHEET_ID,
      range: 'Sheet1!A:E',
      valueInputOption: 'RAW',
      requestBody: {
        values: [['test_phone', 'test_name', 'test_number', 'test@email.com', new Date().toISOString()]]
      }
    })

    res.status(200).json({ success: true })

  } catch (err) {
    console.error('Error:', err.message)
    res.status(200).json({ success: false, error: err.message })
  }
}
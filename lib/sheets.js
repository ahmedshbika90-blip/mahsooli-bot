import { google } from 'googleapis'

const SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

function getAuthClient() {
  return new google.auth.GoogleAuth({
    credentials: {
      client_email: process.env.GOOGLE_SERVICE_ACCOUNT_EMAIL,
      private_key: process.env.GOOGLE_PRIVATE_KEY,
    },
    scopes: SCOPES
  })
}

export async function saveToSheets(data) {
  try {
    const auth = getAuthClient()
    const sheets = google.sheets({ version: 'v4', auth })

    await sheets.spreadsheets.values.append({
      spreadsheetId: process.env.SHEET_ID,
      range: 'mahsooli!A:G',
      valueInputOption: 'RAW',
      requestBody: {
        values: [[
          data.phone,
          data.name         || '',
          data.phone_number || '',
          data.email        || '',
          data.step         || '',
          new Date().toISOString()
        ]]
      }
    })

    return true

  } catch (err) {
    console.error('Sheets save failed:', err.message)
    return false
  }
}
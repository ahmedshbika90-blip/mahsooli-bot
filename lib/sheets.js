 import { google } from 'googleapis'

const SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

function getAuthClient() {
  return new google.auth.JWT(
    process.env.GOOGLE_SERVICE_ACCOUNT_EMAIL,
    null,
    process.env.GOOGLE_PRIVATE_KEY,
    SCOPES
  )
}

export async function saveToSheets(data) {
  try {
    const auth = getAuthClient()
    const sheets = google.sheets({ version: 'v4', auth })

    await sheets.spreadsheets.values.append({
      spreadsheetId: process.env.SHEET_ID,
      range: 'Sheet1!A:F',
      valueInputOption: 'RAW',
      requestBody: {
        values: [[
          data.phone,
          data.name         || '',
          data.phone_number || '',
          data.email        || '',
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
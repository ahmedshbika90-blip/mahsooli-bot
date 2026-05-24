import { google } from 'googleapis'

function getAuthClient() {
  return new google.auth.GoogleAuth({
    credentials: {
      client_email: process.env.GOOGLE_SERVICE_ACCOUNT_EMAIL,
      private_key: process.env.GOOGLE_PRIVATE_KEY,
    },
    scopes: ['https://www.googleapis.com/auth/spreadsheets']
  })
}

async function getSheetsClient() {
  const auth = getAuthClient()
  return google.sheets({ version: 'v4', auth })
}

export async function getSession(phone) {
  try {
    const sheets = await getSheetsClient()
    const res = await sheets.spreadsheets.values.get({
      spreadsheetId: process.env.SHEET_ID,
      range: 'Sessions!A:D'
    })

    const rows = res.data.values || []
    const dataRows = rows.slice(1)
    const row = dataRows.find(r => r[0] === phone)

    console.log('getSession — match:', JSON.stringify(row))

    if (!row) return { step: 1, started: false, data: {} }

    return {
      step: parseInt(row[1]) || 1,
      started: row[2] === 'true',
      data: row[3] ? JSON.parse(row[3]) : {}
    }

  } catch (err) {
    console.error('getSession failed:', err.message)
    return { step: 1, started: false, data: {} }
  }
}

export async function saveSession(phone, session) {
  try {
    const sheets = await getSheetsClient()

    const res = await sheets.spreadsheets.values.get({
      spreadsheetId: process.env.SHEET_ID,
      range: 'Sessions!A:D'
    })

    const rows = res.data.values || []
    const dataRows = rows.slice(1)
    const dataRowIndex = dataRows.findIndex(r => r[0] === phone)
    const rowIndex = dataRowIndex === -1 ? -1 : dataRowIndex + 2

    console.log('saveSession — rowIndex:', rowIndex, '| session:', JSON.stringify(session))

    const values = [[
      phone,
      session.step,
      String(session.started),
      JSON.stringify(session.data)
    ]]

    if (rowIndex === -1) {
      await sheets.spreadsheets.values.append({
        spreadsheetId: process.env.SHEET_ID,
        range: 'Sessions!A:D',
        valueInputOption: 'RAW',
        requestBody: { values }
      })
      console.log('saveSession — appended new row')
    } else {
      await sheets.spreadsheets.values.update({
        spreadsheetId: process.env.SHEET_ID,
        range: `Sessions!A${rowIndex}:D${rowIndex}`,
        valueInputOption: 'RAW',
        requestBody: { values }
      })
      console.log('saveSession — updated row', rowIndex)
    }

    return true

  } catch (err) {
    console.error('saveSession failed:', err.message)
    return false
  }
}

export async function saveToSheets(data) {
  try {
    const sheets = await getSheetsClient()

    await sheets.spreadsheets.values.append({
      spreadsheetId: process.env.SHEET_ID,
      range: 'mahsooli!A:E',
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
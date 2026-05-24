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

export async function saveToSheets(data) {
  try {
    const sheets = await getSheetsClient()

    await sheets.spreadsheets.values.append({
      spreadsheetId: process.env.SHEET_ID,
      range: 'mahsooli!A:BM',
      valueInputOption: 'RAW',
      requestBody: {
        values: [[
          data.phone,
          data.first_name,
          data.second_name,
          data.third_name,
          data.last_name,
          data.dob,
          data.gender,
          data.phone_primary,
          data.phone_secondary,
          data.has_national_id,
          data.national_id,
          data.state,
          data.locality,
          data.education,
          data.has_smartphone,
          data.network_coverage,
          data.best_network,
          data.has_bank,
          data.banks,
          data.banking_apps,
          data.union_member,
          data.union_name,
          data.farm_size,
          data.land_ownership,
          data.rent_amount,
          data.ownership_docs,
          data.has_guarantees,
          data.guarantee_types,
          data.other_guarantee,
          data.crops_last3,
          data.yield_sesame,
          data.yield_sorghum,
          data.yield_groundnut,
          data.yield_cotton,
          data.yield_watermelon,
          data.yield_millet,
          data.yield_sunflower,
          data.finance_source,
          data.finance_amount,
          data.repaid,
          data.no_repay_reason,
          data.finance_use,
          data.finance_bank,
          data.preferred_crops,
          data.why_preferred,
          data.finance_crop,
          data.seed_variety,
          data.use_fertiliser,
          data.use_pesticides,
          data.requested_amount,
          data.marital_status,
          data.wives,
          data.has_children,
          data.total_children,
          data.children_under18,
          data.other_dependents,
          data.dependents_count,
          data.other_income,
          data.income_sources,
          data.remittances,
          data.challenges,
          data.timestamp
        ]]
      }
    })

    return true

  } catch (err) {
    console.error('Sheets save failed:', err.message)
    return false
  }
}
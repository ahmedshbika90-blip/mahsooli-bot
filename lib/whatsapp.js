const BASE_URL = 'https://waba-v2.360dialog.io/messages'

export async function sendWhatsApp(phone, message) {
  try {
    console.log('Sending to:', phone, '| Message:', message)

    const res = await fetch(BASE_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'D360-API-KEY': process.env.DIALOG360_API_KEY
      },
      body: JSON.stringify({
        messaging_product: 'whatsapp',
        recipient_type: 'individual',
        to: phone,
        type: 'text',
        text: {
          preview_url: false,
          body: message
        }
      })
    })

    const data = await res.json()
    console.log('360dialog status:', res.status)
    console.log('360dialog data:', JSON.stringify(data))

    return res.ok

  } catch (err) {
    console.error('WhatsApp send error:', err.message)
    return false
  }
}
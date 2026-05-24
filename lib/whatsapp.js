import axios from 'axios'

const BASE_URL = 'https://waba-v2.360dialog.io/messages'

export async function sendWhatsApp(phone, message) {
  try {
    console.log('Sending to:', phone, '| Message:', message)

    const res = await axios.post(
      BASE_URL,
      {
        messaging_product: 'whatsapp',
        recipient_type: 'individual',
        to: phone,
        type: 'text',
        text: {
          preview_url: false,
          body: message
        }
      },
      {
        headers: {
          'Content-Type': 'application/json',
          'D360-API-KEY': process.env.DIALOG360_API_KEY
        }
      }
    )

    console.log('360dialog response status:', res.status)
    console.log('360dialog response data:', JSON.stringify(res.data))

    return true

  } catch (err) {
    console.error('WhatsApp send failed:', err.response?.status)
    console.error('WhatsApp error data:', JSON.stringify(err.response?.data))
    return false
  }
}
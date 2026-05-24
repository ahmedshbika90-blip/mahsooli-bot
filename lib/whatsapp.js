import axios from 'axios'

const BASE_URL = 'https://waba.360dialog.io/v1/messages'

export async function sendWhatsApp(phone, message) {
  try {
    console.log('Sending to:', phone, '| Message:', message)
    
    const res = await axios.post(
      BASE_URL,
      {
        to: phone,
        type: 'text',
        text: { body: message }
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

    if (res.status !== 201) {
      console.error('360dialog unexpected status:', res.status)
      return false
    }

    return true

  } catch (err) {
    console.error('WhatsApp send failed:', err.response?.status)
    console.error('WhatsApp send error data:', JSON.stringify(err.response?.data))
    console.error('WhatsApp send error message:', err.message)
    return false
  }
}
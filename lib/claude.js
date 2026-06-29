export async function verifyNationalId(imageBase64, mimeType) {
  try {
    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type':      'application/json',
        'x-api-key':         process.env.ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01'
      },
      body: JSON.stringify({
        model:      'claude-sonnet-4-6',
        max_tokens: 200,
        messages: [{
          role: 'user',
          content: [
            {
              type:   'image',
              source: {
                type:       'base64',
                media_type: mimeType,
                data:       imageBase64
              }
            },
            {
              type: 'text',
             text: `You are verifying a Sudanese identity document.

Valid Sudanese identity documents include ANY of the following:
- بطاقة الرقم الوطني (National Number Card)
- جواز السفر (Passport) 
- البطاقة القومية (National Card)
- شهادة القيد المدني (Civil Registration Certificate) — a document issued by the Civil Registration Directorate showing الرقم الوطني
- Any official Sudanese government document that contains الرقم الوطني or رقم البطاقة

Look at this image and answer in JSON only, no other text:

{
  "is_valid_id": true or false,
  "id_number": "the number found after الرقم الوطني, remove any dashes, or null if not found",
  "reason": "brief reason in Arabic if not valid, or null"
}

Rules:
- If the image contains الرقم الوطني → is_valid_id: true, extract the number
- If the image is blurry or unreadable → is_valid_id: false
- If the image has no national number at all → is_valid_id: false
- The number may be formatted as 120-0114646-5, extract digits only: 12001146465`
            }
          ]
        }]
      })
    })

    const data = await response.json()
    const text = data.content?.[0]?.text || ''

    const clean = text.replace(/```json|```/g, '').trim()
    const result = JSON.parse(clean)

    return result

  } catch (err) {
    console.error('Claude verify failed:', err.message)
    return { is_valid_id: false, id_number: null, reason: 'تعذر التحقق من الصورة' }
  }
}
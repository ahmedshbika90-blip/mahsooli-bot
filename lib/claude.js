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

A valid Sudanese identity document is one of:
- بطاقة الرقم الوطني (National Number Card): a small card with an 11-digit national number, the person's name in Arabic, date of birth, and the Sudan coat of arms
- جواز السفر (Passport): a booklet with "جمهورية السودان" or "Republic of Sudan" on the cover
- البطاقة القومية (National Card): older Sudanese ID with name, photo, and ID number

Look at this image and answer in JSON only, no other text:

{
  "is_valid_id": true or false,
  "id_number": "the 11-digit number if found, or null",
  "reason": "brief reason in Arabic if not valid, or null"
}

Rules:
- If the image is blurry, dark, or unreadable → is_valid_id: false
- If the image is not an ID document → is_valid_id: false  
- If it is a valid Sudanese ID → extract the 11-digit number
- The ID number is usually labeled: الرقم الوطني or رقم البطاقة`
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
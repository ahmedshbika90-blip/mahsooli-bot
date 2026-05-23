export function validateAnswer(step, text) {
  switch (step) {
    case 1: // name
      if (text.length < 2)
        return 'Please enter your full name.'
      if (/\d/.test(text))
        return 'Name should not contain numbers.'
      return null

    case 2: // phone number
      const digits = text.replace(/\D/g, '')
      if (digits.length < 9 || digits.length > 15)
        return 'Please enter a valid phone number.'
      return null

    case 3: // email
      if (!text.includes('@') || !text.includes('.'))
        return 'Please enter a valid email address.'
      return null

    default:
      return null
  }
}
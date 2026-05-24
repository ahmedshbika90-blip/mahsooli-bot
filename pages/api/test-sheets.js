function getAuthClient() {
  const email = process.env.GOOGLE_SERVICE_ACCOUNT_EMAIL
  const key = process.env.GOOGLE_PRIVATE_KEY

  console.log('Email:', email)
  console.log('Key length:', key?.length)
  console.log('Key start:', key?.substring(0, 50))
  console.log('Key end:', key?.substring(key.length - 50))

  return new google.auth.JWT(email, null, key, SCOPES)
}
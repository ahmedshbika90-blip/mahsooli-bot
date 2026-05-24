import { validateAnswer } from '../../utils/validate'
import { sendWhatsApp } from '../../lib/whatsapp'
import { saveToSheets } from '../../lib/sheets'
import { getSession, saveSession } from '../../lib/firebase'
import { isAlreadyProcessed } from '../../utils/session'

// ─── Lookup tables ────────────────────────────────────────────────────────────
const STATES = {
  '1':'الخرطوم','2':'الجزيرة','3':'سنار','4':'النيل الأبيض','5':'النيل الأزرق',
  '6':'شمال كردفان','7':'جنوب كردفان','8':'غرب كردفان','9':'شمال دارفور',
  '10':'جنوب دارفور','11':'شرق دارفور','12':'غرب دارفور','13':'وسط دارفور',
  '14':'كسلا','15':'البحر الأحمر','16':'القضارف','17':'نهر النيل','18':'الشمالية'
}
const EDUCATION = {
  '1':'لا يوجد','2':'خلوة (يقرأ ويكتب)','3':'مرحلة أساسية',
  '4':'مرحلة ثانوية','5':'دبلوم','6':'بكالوريوس','7':'ماجستير','8':'دكتوراه'
}
const NETWORKS = {'1':'زين','2':'سوداني','3':'MTN'}
const BANKS = {
  '1':'بنك الخرطوم','2':'بنك فيصل الإسلامي','3':'بنك النيل',
  '4':'SAB','5':'بنك أمدرمان الوطني','6':'بنك النيلين','7':'أخرى'
}
const BANK_APPS = {
  '1':'تطبيق بنك الخرطوم','2':'تطبيق بنك فيصل','3':'تطبيق بنك النيل',
  '4':'تطبيق SAB','5':'تطبيق ONB','6':'تطبيق بنك النيلين','7':'لا أستخدم تطبيقاً'
}
const CROPS = {
  '1':'سمسم','2':'ذرة رفيعة','3':'فول سوداني',
  '4':'قطن','5':'بذرة بطيخ','6':'دخن','7':'عباد الشمس'
}
const GUARANTEES = {'1':'شيك','2':'معدات','3':'أرض','4':'أخرى'}
const FINANCE_HOW = {'1':'بنك','2':'تمويل ذاتي','3':'ائتمان تاجر','4':'منظمة','5':'أخرى'}
const NO_REPAY_REASON = {'1':'إنتاج منخفض','2':'تكلفة مدخلات عالية','3':'لا يوجد إنتاج','4':'أخرى'}
const FINANCE_USE = {
  '1':'بذور','2':'سماد','3':'مبيدات','4':'إيجار آلات','5':'وقود','6':'حصاد'
}
const MARITAL = {'1':'أعزب','2':'متزوج','3':'أرمل','4':'مطلق'}
const INCOME_SOURCES = {
  '1':'وظيفة رسمية','2':'تجارة','3':'رعي','4':'حوالات','5':'دعم نقدي من منظمة'
}

function lookup(map, val) {
  return val.split(/[,،\s]+/).map(v => map[v.trim()] || v).join('، ')
}

function isYes(val) {
  return val === 'نعم' || val === '1'
}

// ─── Questions ────────────────────────────────────────────────────────────────
function getQuestion(step, data) {
  switch(step) {
    case 1:  return '👤 *القسم الأول: المعلومات الشخصية*\n\nما هو اسمك الأول؟'
    case 2:  return 'ما هو اسمك الثاني؟'
    case 3:  return 'ما هو اسمك الثالث؟\n_(إذا لم يكن لديك اكتب: لا يوجد)_'
    case 4:  return 'ما هو اسم العائلة؟'
    case 5:  return 'ما هو تاريخ ميلادك؟\n📅 الصيغة: YYYY/MM/DD\nمثال: 1990/05/15'
    case 6:  return 'ما هو جنسك؟\n1 - ذكر\n2 - أنثى'
    case 7:  return 'ما هو رقم هاتفك الأساسي؟\n📱 يجب أن يكون 10 أرقام ويبدأ بـ 0\nمثال: 0912345678'
    case 8:  return 'ما هو رقم هاتفك الثانوي؟ (اختياري)\n_(إذا لم يكن لديك اكتب: لا يوجد)_'
    case 9:  return 'هل لديك بطاقة هوية وطنية؟\n1 - نعم\n2 - لا'
    case 10: return 'أدخل رقم هويتك الوطنية:\n🔢 يجب أن يكون 11 رقماً'
    case 11: return '📍 *القسم: الموقع والتعليم*\n\nما هي ولايتك؟\n1. الخرطوم\n2. الجزيرة\n3. سنار\n4. النيل الأبيض\n5. النيل الأزرق\n6. شمال كردفان\n7. جنوب كردفان\n8. غرب كردفان\n9. شمال دارفور\n10. جنوب دارفور\n11. شرق دارفور\n12. غرب دارفور\n13. وسط دارفور\n14. كسلا\n15. البحر الأحمر\n16. القضارف\n17. نهر النيل\n18. الشمالية'
    case 12: return 'ما هي محليتك؟'
    case 13: return 'ما أعلى مستوى تعليمي حصلت عليه؟\n1. لا يوجد\n2. خلوة (يقرأ ويكتب)\n3. مرحلة أساسية\n4. مرحلة ثانوية\n5. دبلوم\n6. بكالوريوس\n7. ماجستير\n8. دكتوراه'
    case 14: return 'هل تمتلك هاتفاً ذكياً؟\n1 - نعم\n2 - لا'
    case 15: return 'هل لديك تغطية شبكة جيدة في منطقتك؟\n1 - نعم\n2 - لا'
    case 16: return 'ما أفضل شبكة في منطقتك؟\n1 - زين\n2 - سوداني\n3 - MTN'
    case 17: return 'هل لديك حساب بنكي؟\n1 - نعم\n2 - لا'
    case 18: return '🏦 في أي بنك (أو بنوك) لديك حساب؟\n1. بنك الخرطوم\n2. بنك فيصل الإسلامي\n3. بنك النيل\n4. SAB\n5. بنك أمدرمان الوطني\n6. بنك النيلين\n7. أخرى\n\n_(يمكن اختيار أكثر من بنك، مثال: 1,3)_'
    case 19: return 'أي تطبيق بنكي تمتلك أو تستخدم؟\n1. تطبيق بنك الخرطوم\n2. تطبيق بنك فيصل\n3. تطبيق بنك النيل\n4. تطبيق SAB\n5. تطبيق ONB\n6. تطبيق بنك النيلين\n7. لا أستخدم تطبيقاً\n\n_(يمكن اختيار أكثر من واحد، مثال: 1,3)_'
    case 20: return '🌾 *القسم الثاني: الزراعة والتمويل*\n\nهل أنت عضو في اتحاد زراعي؟\n1 - نعم\n2 - لا'
    case 21: return 'ما اسم الاتحاد أو الجمعية التي تنتمي إليها؟'
    case 22: return 'ما مساحة أرضك الزراعية؟\n🌱 أدخل العدد بالفدان\nمثال: 25 أو 7.5'
    case 23: return 'هل أرضك مملوكة أم مستأجرة؟\n1 - مملوكة\n2 - مستأجرة'
    case 24: return 'كم تدفع إيجاراً في الموسم؟\n💰 أدخل المبلغ بالجنيه السوداني\nمثال: 500000'
    case 25: return 'هل لديك وثائق تثبت ملكية أرضك؟\n1 - نعم\n2 - لا'
    case 26: return 'هل لديك ضمانات يمكنك تقديمها؟\n1 - نعم\n2 - لا'
    case 27: return 'ما نوع الضمان؟\n1. شيك\n2. معدات\n3. أرض\n4. أخرى\n\n_(يمكن اختيار أكثر من واحد، مثال: 1,3)_'
    case 28: return 'يرجى تحديد نوع الضمان الآخر:'
    case 29: return 'ما المحاصيل التي زرعتها في آخر 3 مواسم؟\n1. سمسم\n2. ذرة رفيعة\n3. فول سوداني\n4. قطن\n5. بذرة بطيخ\n6. دخن\n7. عباد الشمس\n\n_(يمكن اختيار أكثر من واحد، مثال: 1,2,3)_'
    case 30: return '📊 *متوسط الإنتاجية (آخر 3 مواسم)*\n\nالسمسم — متوسط الإنتاجية (وحدة/فدان):\n_(اكتب: لا يوجد إذا لم تزرعه)_'
    case 31: return 'الذرة الرفيعة — متوسط الإنتاجية (وحدة/فدان):\n_(اكتب: لا يوجد إذا لم تزرعها)_'
    case 32: return 'الفول السوداني — متوسط الإنتاجية (وحدة/فدان):\n_(اكتب: لا يوجد إذا لم تزرعه)_'
    case 33: return 'القطن — متوسط الإنتاجية (وحدة/فدان):\n_(اكتب: لا يوجد إذا لم تزرعه)_'
    case 34: return 'بذرة البطيخ — متوسط الإنتاجية (وحدة/فدان):\n_(اكتب: لا يوجد إذا لم تزرعها)_'
    case 35: return 'الدخن — متوسط الإنتاجية (وحدة/فدان):\n_(اكتب: لا يوجد إذا لم تزرعه)_'
    case 36: return 'عباد الشمس — متوسط الإنتاجية (وحدة/فدان):\n_(اكتب: لا يوجد إذا لم تزرعه)_'
    case 37: return 'كيف موّلت زراعتك في الموسم الماضي؟\n1. بنك\n2. تمويل ذاتي\n3. ائتمان تاجر\n4. منظمة\n5. أخرى'
    case 38: return 'ما مقدار التمويل الذي حصلت عليه؟\n💰 أدخل المبلغ بالجنيه السوداني\nمثال: 5000000'
    case 39: return 'هل تمكنت من سداد التمويل؟\n1 - نعم\n2 - لا'
    case 40: return 'لماذا لم تتمكن من السداد؟\n1. إنتاج منخفض\n2. تكلفة مدخلات عالية\n3. لا يوجد إنتاج\n4. أخرى'
    case 41: return 'كيف استخدمت التمويل؟\n1. بذور\n2. سماد\n3. مبيدات\n4. إيجار آلات\n5. وقود\n6. حصاد\n\n_(يمكن اختيار أكثر من واحد، مثال: 1,2)_'
    case 42: return 'من أي بنك حصلت على التمويل؟\n1. بنك الخرطوم\n2. بنك فيصل الإسلامي\n3. بنك النيل\n4. SAB\n5. بنك أمدرمان الوطني\n6. بنك النيلين\n7. أخرى'
    case 43: return '🌱 *تفضيلات المحاصيل وطلب التمويل*\n\nما المحاصيل التي تفضل زراعتها هذا الموسم؟\n1. سمسم\n2. ذرة رفيعة\n3. فول سوداني\n4. قطن\n5. بذرة بطيخ\n6. دخن\n7. عباد الشمس\n\n_(يمكن اختيار أكثر من واحد، مثال: 1,3)_'
    case 44: return 'لماذا تفضل هذه المحاصيل؟\n_(اختياري — اكتب: لا يوجد إذا لم تشأ الإجابة)_'
    case 45: return 'ما المحصول الذي تطلب تمويلاً له؟\n1. سمسم\n2. ذرة رفيعة\n3. فول سوداني\n4. قطن\n5. بذرة بطيخ\n6. دخن\n7. عباد الشمس'
    case 46: return 'ما صنف البذرة؟\n_(اختياري — اكتب: لا يوجد إذا لم تعرف)_'
    case 47: return 'هل تخطط لاستخدام الأسمدة؟\n1 - نعم\n2 - لا'
    case 48: return 'هل تخطط لاستخدام المبيدات؟\n1 - نعم\n2 - لا'
    case 49: return 'ما مبلغ التمويل المطلوب؟\n💰 أدخل المبلغ بالجنيه السوداني\nمثال: 5000000'
    case 50: return '👨‍👩‍👧 *القسم الثالث: معلومات الأسرة*\n\nما حالتك الاجتماعية؟\n1. أعزب\n2. متزوج\n3. أرمل\n4. مطلق'
    case 51: return 'كم عدد زوجاتك؟\n_(أدخل رقماً من 1 إلى 4)_'
    case 52: return 'هل لديك أطفال؟\n1 - نعم\n2 - لا'
    case 53: return 'كم عدد أطفالك الإجمالي؟'
    case 54: return 'كم عدد أطفالك دون سن 18؟'
    case 55: return 'هل تعول أشخاصاً آخرين غير أطفالك؟\n1 - نعم\n2 - لا'
    case 56: return 'كم عددهم؟'
    case 57: return 'هل لديك مصادر دخل أخرى غير الزراعة؟\n1 - نعم\n2 - لا'
    case 58: return 'ما مصادر دخلك الأخرى؟\n1. وظيفة رسمية\n2. تجارة\n3. رعي\n4. حوالات\n5. دعم نقدي من منظمة\n\n_(يمكن اختيار أكثر من واحد، مثال: 1,4)_'
    case 59: return 'إذا كنت تتلقى حوالات، ما المبلغ التقريبي الذي تتلقاه سنوياً؟\n💰 بالجنيه السوداني\n_(اختياري — اكتب: لا يوجد أو "لا أرغب في الإجابة")_'
    case 60: return '✍️ *ملاحظات ختامية*\n\nما التحديات العامة التي تواجهها في الزراعة كل موسم، وما الحلول التي تقترحها؟\n_(اختياري — اكتب: لا يوجد إذا لم تشأ الإجابة)_'
    default: return null
  }
}

// ─── Conditional logic — what step comes next ─────────────────────────────────
function getNextStep(currentStep, answer, data) {
  const t = answer.trim()

  switch(currentStep) {
    case 9:
      // Has national ID? Yes → ask Q10, No → skip to Q11
      return isYes(t) ? 10 : 11

    case 17:
      // Bank account? Yes → ask Q18, No → skip to Q20
      return isYes(t) ? 18 : 20

    case 20:
      // Union member? Yes → ask Q21, No → skip to Q22
      return isYes(t) ? 21 : 22

    case 23:
      // Owned → Q25, Rented → Q24
      return (t === 'مملوكة' || t === '1') ? 25 : 24

    case 24:
      // After rent → Q26
      return 26

    case 26:
      // Guarantees? Yes → Q27, No → Q29
      return isYes(t) ? 27 : 29

    case 27:
      // Chose "Other" (4)? → Q28, else → Q29
      return t.includes('4') ? 28 : 29

    case 37:
      // Bank → Q38, else → skip to Q43
      return (t === '1') ? 38 : 43

    case 39:
      // Repaid? No → Q40, Yes → Q41
      return isYes(t) ? 41 : 40

    case 40:
      return 41

    case 50:
      // Married (2) → Q51, else → Q52
      return (t === '2') ? 51 : 52

    case 52:
      // Has children? Yes → Q53, No → Q55
      return isYes(t) ? 53 : 55

    case 55:
      // Other dependents? Yes → Q56, No → Q57
      return isYes(t) ? 56 : 57

    case 57:
      // Other income? Yes → Q58, No → Q60
      return isYes(t) ? 58 : 60

    default:
      return currentStep + 1
  }
}

const TOTAL_STEPS = 60

// ─── Handler ──────────────────────────────────────────────────────────────────
export default async function handler(req, res) {
  if (req.method === 'GET') {
    const token = req.headers['webhook_verify_token']
    if (token === process.env.WEBHOOK_VERIFY_TOKEN) {
      return res.status(200).send('Webhook verified')
    }
    return res.status(403).end()
  }

  if (req.method !== 'POST') return res.status(405).end()

  const entry = req.body?.entry?.[0]
  const changes = entry?.changes?.[0]
  const messages = changes?.value?.messages

  if (!messages?.length) {
    return res.status(200).json({ status: 'ok' })
  }

  for (const message of messages) {
    const phone = message.from
    if (isAlreadyProcessed(message.id)) continue
    if (message.type !== 'text') {
      await sendWhatsApp(phone, '❌ يرجى الرد برسالة نصية فقط.')
      continue
    }
    const text = message.text.body.trim()
    if (!text) continue
    await handleMessage(phone, text)
  }

  return res.status(200).json({ status: 'ok' })
}

// ─── Main handler ─────────────────────────────────────────────────────────────
async function handleMessage(phone, text) {
  const session = await getSession(phone)

  if (session.completed) return

  if (!session.started) {
    session.started = true
    await saveSession(phone, session)
    await sendWhatsApp(phone,
      `*مرحباً بك في برنامج التمويل الزراعي* 🌾\n\nسيتم تسجيلك من خلال هذا النموذج.\nجميع المعلومات ستُحفظ بسرية تامة.\n\nسيستغرق التسجيل حوالي 10 دقائق.\n\nلنبدأ! ✅`
    )
    await sendWhatsApp(phone, getQuestion(1, {}))
    return
  }

  const error = validateAnswer(session.step, text)
  if (error) {
    await sendWhatsApp(phone, error)
    return
  }

  // Save the answer
  const key = `q${session.step}`
  session.data[key] = text

  // Get next step
  const nextStep = getNextStep(session.step, text, session.data)

  if (nextStep > TOTAL_STEPS) {
    // Save to Sheets
    const saved = await saveToSheets(buildSheetsRow(phone, session.data))
    if (!saved) {
      await sendWhatsApp(phone, '❌ حدث خطأ في حفظ البيانات. يرجى المحاولة مرة أخرى.')
      return
    }
    await saveSession(phone, { completed: true, step: TOTAL_STEPS, started: true, data: {} })
    await sendWhatsApp(phone,
      `✅ *شكراً لك! تم تسجيلك بنجاح.*\n\nسيتواصل معك فريقنا قريباً.\nنتمنى لك موسماً زراعياً ناجحاً 🌱`
    )
    return
  }

  session.step = nextStep
  await saveSession(phone, session)
  await sendWhatsApp(phone, getQuestion(nextStep, session.data))
}

// ─── Build sheets row ─────────────────────────────────────────────────────────
function buildSheetsRow(phone, d) {
  return {
    phone,
    first_name:         d.q1 || '',
    second_name:        d.q2 || '',
    third_name:         d.q3 || '',
    last_name:          d.q4 || '',
    dob:                d.q5 || '',
    gender:             d.q6 === '1' ? 'ذكر' : d.q6 === '2' ? 'أنثى' : d.q6 || '',
    phone_primary:      d.q7 || '',
    phone_secondary:    d.q8 || '',
    has_national_id:    isYes(d.q9 || '') ? 'نعم' : 'لا',
    national_id:        d.q10 || '',
    state:              STATES[d.q11] || d.q11 || '',
    locality:           d.q12 || '',
    education:          EDUCATION[d.q13] || d.q13 || '',
    has_smartphone:     isYes(d.q14 || '') ? 'نعم' : 'لا',
    network_coverage:   isYes(d.q15 || '') ? 'نعم' : 'لا',
    best_network:       NETWORKS[d.q16] || d.q16 || '',
    has_bank:           isYes(d.q17 || '') ? 'نعم' : 'لا',
    banks:              d.q18 ? lookup(BANKS, d.q18) : '',
    banking_apps:       d.q19 ? lookup(BANK_APPS, d.q19) : '',
    union_member:       isYes(d.q20 || '') ? 'نعم' : 'لا',
    union_name:         d.q21 || '',
    farm_size:          d.q22 || '',
    land_ownership:     (d.q23 === '1' || d.q23 === 'مملوكة') ? 'مملوكة' : 'مستأجرة',
    rent_amount:        d.q24 || '',
    ownership_docs:     isYes(d.q25 || '') ? 'نعم' : 'لا',
    has_guarantees:     isYes(d.q26 || '') ? 'نعم' : 'لا',
    guarantee_types:    d.q27 ? lookup(GUARANTEES, d.q27) : '',
    other_guarantee:    d.q28 || '',
    crops_last3:        d.q29 ? lookup(CROPS, d.q29) : '',
    yield_sesame:       d.q30 || '',
    yield_sorghum:      d.q31 || '',
    yield_groundnut:    d.q32 || '',
    yield_cotton:       d.q33 || '',
    yield_watermelon:   d.q34 || '',
    yield_millet:       d.q35 || '',
    yield_sunflower:    d.q36 || '',
    finance_source:     d.q37 ? FINANCE_HOW[d.q37] || d.q37 : '',
    finance_amount:     d.q38 || '',
    repaid:             d.q39 ? (isYes(d.q39) ? 'نعم' : 'لا') : '',
    no_repay_reason:    d.q40 ? NO_REPAY_REASON[d.q40] || d.q40 : '',
    finance_use:        d.q41 ? lookup(FINANCE_USE, d.q41) : '',
    finance_bank:       d.q42 ? BANKS[d.q42] || d.q42 : '',
    preferred_crops:    d.q43 ? lookup(CROPS, d.q43) : '',
    why_preferred:      d.q44 || '',
    finance_crop:       d.q45 ? CROPS[d.q45] || d.q45 : '',
    seed_variety:       d.q46 || '',
    use_fertiliser:     isYes(d.q47 || '') ? 'نعم' : 'لا',
    use_pesticides:     isYes(d.q48 || '') ? 'نعم' : 'لا',
    requested_amount:   d.q49 || '',
    marital_status:     d.q50 ? MARITAL[d.q50] || d.q50 : '',
    wives:              d.q51 || '',
    has_children:       d.q52 ? (isYes(d.q52) ? 'نعم' : 'لا') : '',
    total_children:     d.q53 || '',
    children_under18:   d.q54 || '',
    other_dependents:   d.q55 ? (isYes(d.q55) ? 'نعم' : 'لا') : '',
    dependents_count:   d.q56 || '',
    other_income:       d.q57 ? (isYes(d.q57) ? 'نعم' : 'لا') : '',
    income_sources:     d.q58 ? lookup(INCOME_SOURCES, d.q58) : '',
    remittances:        d.q59 || '',
    challenges:         d.q60 || '',
    timestamp:          new Date().toISOString()
  }
}
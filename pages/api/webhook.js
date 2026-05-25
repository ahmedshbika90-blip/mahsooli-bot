import { validateAnswer } from '../../utils/validate'
import { sendWhatsApp } from '../../lib/whatsapp'
import { saveToSheets } from '../../lib/sheets'
import { getSession, saveSession } from '../../lib/firebase'
import { isAlreadyProcessed } from '../../utils/session'

const TOTAL_STEPS = 58

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
const NETWORKS  = {'1':'زين','2':'سوداني','3':'MTN'}
const BANKS     = {'1':'بنك الخرطوم','2':'بنك فيصل الإسلامي','3':'بنك النيل','4':'SAB','5':'بنك أمدرمان الوطني','6':'بنك النيلين','7':'أخرى'}
const BANK_APPS = {'1':'تطبيق بنك الخرطوم','2':'تطبيق بنك فيصل','3':'تطبيق بنك النيل','4':'تطبيق SAB','5':'تطبيق ONB','6':'تطبيق بنك النيلين','7':'لا أستخدم تطبيقاً'}
const CROPS     = {'1':'سمسم','2':'ذرة رفيعة','3':'فول سوداني','4':'قطن','5':'بذرة بطيخ','6':'دخن','7':'عباد الشمس'}
const GUARANTEES= {'1':'شيك','2':'معدات','3':'أرض','4':'أخرى'}
const FINANCE_HOW={'1':'بنك','2':'تمويل ذاتي','3':'ائتمان تاجر','4':'منظمة','5':'أخرى'}
const NO_REPAY  = {'1':'إنتاج منخفض','2':'تكلفة مدخلات عالية','3':'لا يوجد إنتاج','4':'أخرى'}
const FINANCE_USE={'1':'بذور','2':'سماد','3':'مبيدات','4':'إيجار آلات','5':'وقود','6':'حصاد'}
const MARITAL   = {'1':'أعزب','2':'متزوج','3':'أرمل','4':'مطلق'}
const INCOME_SRC= {'1':'وظيفة رسمية','2':'تجارة','3':'رعي','4':'حوالات','5':'دعم نقدي من منظمة'}

function lookup(map, val) {
  return val.split(/[,،\s]+/).map(v => map[v.trim()] || v).join('، ')
}
function isYes(val) { return val === 'نعم' || val === '1' }
function progress(step) {
  return `_(${Math.round((step / TOTAL_STEPS) * 100)}% مكتمل ✅)_\n\n`
}

function getQuestion(step) {
  const p = progress(step)
  switch(step) {
    case 1:  return `${p}👤 *القسم الأول: المعلومات الشخصية*\n\nأدخل اسمك الكامل (الاسم الأول والثاني والثالث إن وجد):\nمثال: أحمد عبدالله إبراهيم`
    case 2:  return `${p}ما هو اسم العائلة؟`
    case 3:  return `${p}ما هو تاريخ ميلادك؟\n📅 الصيغة: DD/MM/YYYY\nمثال: 15/05/1990`
    case 4:  return `${p}ما هو جنسك؟\n1 - ذكر\n2 - أنثى`
    case 5:  return `${p}ما هو رقم هاتفك الأساسي؟\n📱 10 أرقام تبدأ بـ 0\nمثال: 0912345678`
    case 6:  return `${p}ما هو رقم هاتفك الثانوي؟ (اختياري)\n_(اكتب: لا يوجد إذا لم يكن لديك)_`
    case 7:  return `${p}هل لديك بطاقة هوية وطنية؟\n1 - نعم\n2 - لا`
    case 8:  return `${p}أدخل رقم هويتك الوطنية:\n🔢 11 رقماً بالضبط`
    case 9:  return `${p}📍 *الموقع والتعليم*\n\nما هي ولايتك؟\n1. الخرطوم\n2. الجزيرة\n3. سنار\n4. النيل الأبيض\n5. النيل الأزرق\n6. شمال كردفان\n7. جنوب كردفان\n8. غرب كردفان\n9. شمال دارفور\n10. جنوب دارفور\n11. شرق دارفور\n12. غرب دارفور\n13. وسط دارفور\n14. كسلا\n15. البحر الأحمر\n16. القضارف\n17. نهر النيل\n18. الشمالية`
    case 10: return `${p}ما هي محليتك؟`
    case 11: return `${p}ما أعلى مستوى تعليمي حصلت عليه؟\n1. لا يوجد\n2. خلوة (يقرأ ويكتب)\n3. مرحلة أساسية\n4. مرحلة ثانوية\n5. دبلوم\n6. بكالوريوس\n7. ماجستير\n8. دكتوراه`
    case 12: return `${p}هل تمتلك هاتفاً ذكياً؟\n1 - نعم\n2 - لا`
    case 13: return `${p}هل لديك تغطية شبكة جيدة في منطقتك؟\n1 - نعم\n2 - لا`
    case 14: return `${p}ما أفضل شبكة في منطقتك؟\n1 - زين\n2 - سوداني\n3 - MTN`
    case 15: return `${p}هل لديك حساب بنكي؟\n1 - نعم\n2 - لا`
    case 16: return `${p}🏦 في أي بنك لديك حساب؟\n1. بنك الخرطوم\n2. بنك فيصل الإسلامي\n3. بنك النيل\n4. SAB\n5. بنك أمدرمان الوطني\n6. بنك النيلين\n7. أخرى\n\n_(أكثر من اختيار: مثال 1,3)_`
    case 17: return `${p}أي تطبيق بنكي تستخدم؟\n1. تطبيق بنك الخرطوم\n2. تطبيق بنك فيصل\n3. تطبيق بنك النيل\n4. تطبيق SAB\n5. تطبيق ONB\n6. تطبيق بنك النيلين\n7. لا أستخدم تطبيقاً\n\n_(أكثر من اختيار: مثال 1,3)_`
    case 18: return `${p}🌾 *القسم الثاني: الزراعة والتمويل*\n\nهل أنت عضو في اتحاد زراعي؟\n1 - نعم\n2 - لا`
    case 19: return `${p}ما اسم الاتحاد أو الجمعية التي تنتمي إليها؟`
    case 20: return `${p}ما مساحة أرضك الزراعية بالفدان؟\nمثال: 25 أو 7.5`
    case 21: return `${p}هل أرضك مملوكة أم مستأجرة؟\n1 - مملوكة\n2 - مستأجرة`
    case 22: return `${p}كم تدفع إيجاراً في الموسم؟\n💰 بالجنيه السوداني\nمثال: 500000`
    case 23: return `${p}هل لديك وثائق تثبت ملكية أرضك؟\n1 - نعم\n2 - لا`
    case 24: return `${p}هل لديك ضمانات يمكنك تقديمها؟\n1 - نعم\n2 - لا`
    case 25: return `${p}ما نوع الضمان؟\n1. شيك\n2. معدات\n3. أرض\n4. أخرى\n\n_(أكثر من اختيار: مثال 1,3)_`
    case 26: return `${p}يرجى تحديد نوع الضمان الآخر:`
    case 27: return `${p}ما المحاصيل التي زرعتها في آخر 3 مواسم؟\n1. سمسم\n2. ذرة رفيعة\n3. فول سوداني\n4. قطن\n5. بذرة بطيخ\n6. دخن\n7. عباد الشمس\n\n_(أكثر من اختيار: مثال 1,2,3)_`
    case 28: return `${p}📊 *متوسط الإنتاجية (آخر 3 مواسم)*\nاختر من: 1 — 1.5 — 2 — 2.5 — 3 — 3.5 — 4\nأو اكتب: لا يوجد\n\n*السمسم* — متوسط الإنتاجية (شوال/فدان):`
    case 29: return `${p}اختر من: 1 — 1.5 — 2 — 2.5 — 3 — 3.5 — 4\nأو اكتب: لا يوجد\n\n*الذرة الرفيعة* — متوسط الإنتاجية (شوال/فدان):`
    case 30: return `${p}اختر من: 1 — 1.5 — 2 — 2.5 — 3 — 3.5 — 4\nأو اكتب: لا يوجد\n\n*الفول السوداني* — متوسط الإنتاجية (شوال/فدان):`
    case 31: return `${p}اختر من: 1 — 1.5 — 2 — 2.5 — 3 — 3.5 — 4\nأو اكتب: لا يوجد\n\n*القطن* — متوسط الإنتاجية (شوال/فدان):`
    case 32: return `${p}اختر من: 1 — 1.5 — 2 — 2.5 — 3 — 3.5 — 4\nأو اكتب: لا يوجد\n\n*بذرة البطيخ* — متوسط الإنتاجية (شوال/فدان):`
    case 33: return `${p}اختر من: 1 — 1.5 — 2 — 2.5 — 3 — 3.5 — 4\nأو اكتب: لا يوجد\n\n*الدخن* — متوسط الإنتاجية (شوال/فدان):`
    case 34: return `${p}اختر من: 1 — 1.5 — 2 — 2.5 — 3 — 3.5 — 4\nأو اكتب: لا يوجد\n\n*عباد الشمس* — متوسط الإنتاجية (شوال/فدان):`
    case 35: return `${p}كيف موّلت زراعتك في الموسم الماضي؟\n1. بنك\n2. تمويل ذاتي\n3. ائتمان تاجر\n4. منظمة\n5. أخرى`
    case 36: return `${p}ما مقدار التمويل الذي حصلت عليه؟\n💰 بالجنيه السوداني\nمثال: 5000000`
    case 37: return `${p}هل تمكنت من سداد التمويل؟\n1 - نعم\n2 - لا`
    case 38: return `${p}لماذا لم تتمكن من السداد؟\n1. إنتاج منخفض\n2. تكلفة مدخلات عالية\n3. لا يوجد إنتاج\n4. أخرى`
    case 39: return `${p}كيف استخدمت التمويل؟\n1. بذور\n2. سماد\n3. مبيدات\n4. إيجار آلات\n5. وقود\n6. حصاد\n\n_(أكثر من اختيار: مثال 1,2)_`
    case 40: return `${p}من أي بنك حصلت على التمويل؟\n1. بنك الخرطوم\n2. بنك فيصل الإسلامي\n3. بنك النيل\n4. SAB\n5. بنك أمدرمان الوطني\n6. بنك النيلين\n7. أخرى`
    case 41: return `${p}🌱 *تفضيلات المحاصيل وطلب التمويل*\n\nما المحاصيل التي تفضل زراعتها هذا الموسم؟\n1. سمسم\n2. ذرة رفيعة\n3. فول سوداني\n4. قطن\n5. بذرة بطيخ\n6. دخن\n7. عباد الشمس\n\n_(أكثر من اختيار: مثال 1,3)_`
    case 42: return `${p}لماذا تفضل هذه المحاصيل؟\n_(اختياري — اكتب: لا يوجد إذا لم تشأ)_`
    case 43: return `${p}ما المحصول الذي تطلب تمويلاً له؟\n1. سمسم\n2. ذرة رفيعة\n3. فول سوداني\n4. قطن\n5. بذرة بطيخ\n6. دخن\n7. عباد الشمس`
    case 44: return `${p}ما صنف البذرة؟\n_(اختياري — اكتب: لا يوجد إذا لم تعرف)_`
    case 45: return `${p}هل تخطط لاستخدام الأسمدة؟\n1 - نعم\n2 - لا`
    case 46: return `${p}هل تخطط لاستخدام المبيدات؟\n1 - نعم\n2 - لا`
    case 47: return `${p}ما مبلغ التمويل المطلوب؟\n💰 بالجنيه السوداني\nمثال: 5000000`
    case 48: return `${p}👨‍👩‍👧 *القسم الثالث: معلومات الأسرة*\n\nما حالتك الاجتماعية؟\n1. أعزب\n2. متزوج\n3. أرمل\n4. مطلق`
    case 49: return `${p}كم عدد زوجاتك؟ (من 1 إلى 4)`
    case 50: return `${p}هل لديك أطفال؟\n1 - نعم\n2 - لا`
    case 51: return `${p}كم عدد أطفالك الإجمالي؟`
    case 52: return `${p}كم عدد أطفالك دون سن 18؟`
    case 53: return `${p}هل تعول أشخاصاً آخرين غير أطفالك؟\n1 - نعم\n2 - لا`
    case 54: return `${p}كم عددهم؟`
    case 55: return `${p}هل لديك مصادر دخل أخرى غير الزراعة؟\n1 - نعم\n2 - لا`
    case 56: return `${p}ما مصادر دخلك الأخرى؟\n1. وظيفة رسمية\n2. تجارة\n3. رعي\n4. حوالات\n5. دعم نقدي من منظمة\n\n_(أكثر من اختيار: مثال 1,4)_`
    case 57: return `${p}إذا كنت تتلقى حوالات، ما المبلغ التقريبي سنوياً؟\n💰 بالجنيه السوداني\n_(اختياري — اكتب: لا يوجد)_`
    case 58: return `${p}✍️ *ملاحظات ختامية*\n\nما التحديات العامة التي تواجهها في الزراعة كل موسم، وما الحلول التي تقترحها؟\n_(اختياري — اكتب: لا يوجد)_`
    default: return null
  }
}

function getNextStep(step, answer) {
  const t = answer.trim()
  switch(step) {
    case 7:  return isYes(t) ? 8 : 9           // has national ID
    case 15: return isYes(t) ? 16 : 18         // has bank account
    case 18: return isYes(t) ? 19 : 20         // union member
    case 21: return (t==='1'||t==='مملوكة') ? 23 : 22  // owned→docs, rented→rent
    case 22: return 24                          // after rent → guarantees
    case 24: return isYes(t) ? 25 : 27         // has guarantees
    case 25: return t.includes('4') ? 26 : 27  // other guarantee
    case 35: return t === '1' ? 36 : 41        // bank finance → amount, else → preferred crops
    case 37: return isYes(t) ? 39 : 38         // repaid → use, not repaid → why
    case 38: return 39                          // why not repaid → use
    case 48:                                    // marital status
      return t === '2' ? 49 : 53              // married → wives, else → dependents
    case 49: return 50                          // wives → children
    case 50: return isYes(t) ? 51 : 53        // has children → count, else → dependents
    case 53: return isYes(t) ? 54 : 55        // other dependents
    case 55: return isYes(t) ? 56 : 57        // other income
    default: return step + 1
  }
}

function buildSheetsRow(phone, d) {
  const nameParts = (d.q1 || '').split(/\s+/).filter(Boolean)
  return {
    phone,
    first_name:       nameParts[0] || '',
    second_name:      nameParts[1] || '',
    third_name:       nameParts[2] || '',
    last_name:        d.q2 || '',
    dob:              d.q3 || '',
    gender:           d.q4 === '1' ? 'ذكر' : d.q4 === '2' ? 'أنثى' : d.q4 || '',
    phone_primary:    d.q5 || '',
    phone_secondary:  d.q6 || '',
    has_national_id:  isYes(d.q7||'') ? 'نعم' : 'لا',
    national_id:      d.q8 || '',
    state:            STATES[d.q9] || d.q9 || '',
    locality:         d.q10 || '',
    education:        EDUCATION[d.q11] || d.q11 || '',
    has_smartphone:   isYes(d.q12||'') ? 'نعم' : 'لا',
    network_coverage: isYes(d.q13||'') ? 'نعم' : 'لا',
    best_network:     NETWORKS[d.q14] || d.q14 || '',
    has_bank:         isYes(d.q15||'') ? 'نعم' : 'لا',
    banks:            d.q16 ? lookup(BANKS, d.q16) : '',
    banking_apps:     d.q17 ? lookup(BANK_APPS, d.q17) : '',
    union_member:     isYes(d.q18||'') ? 'نعم' : 'لا',
    union_name:       d.q19 || '',
    farm_size:        d.q20 || '',
    land_ownership:   (d.q21==='1'||d.q21==='مملوكة') ? 'مملوكة' : 'مستأجرة',
    rent_amount:      d.q22 || '',
    ownership_docs:   isYes(d.q23||'') ? 'نعم' : 'لا',
    has_guarantees:   isYes(d.q24||'') ? 'نعم' : 'لا',
    guarantee_types:  d.q25 ? lookup(GUARANTEES, d.q25) : '',
    other_guarantee:  d.q26 || '',
    crops_last3:      d.q27 ? lookup(CROPS, d.q27) : '',
    yield_sesame:     d.q28 || '',
    yield_sorghum:    d.q29 || '',
    yield_groundnut:  d.q30 || '',
    yield_cotton:     d.q31 || '',
    yield_watermelon: d.q32 || '',
    yield_millet:     d.q33 || '',
    yield_sunflower:  d.q34 || '',
    finance_source:   FINANCE_HOW[d.q35] || d.q35 || '',
    finance_amount:   d.q36 || '',
    repaid:           d.q37 ? (isYes(d.q37) ? 'نعم' : 'لا') : '',
    no_repay_reason:  d.q38 ? NO_REPAY[d.q38] || d.q38 : '',
    finance_use:      d.q39 ? lookup(FINANCE_USE, d.q39) : '',
    finance_bank:     d.q40 ? BANKS[d.q40] || d.q40 : '',
    preferred_crops:  d.q41 ? lookup(CROPS, d.q41) : '',
    why_preferred:    d.q42 || '',
    finance_crop:     d.q43 ? CROPS[d.q43] || d.q43 : '',
    seed_variety:     d.q44 || '',
    use_fertiliser:   isYes(d.q45||'') ? 'نعم' : 'لا',
    use_pesticides:   isYes(d.q46||'') ? 'نعم' : 'لا',
    requested_amount: d.q47 || '',
    marital_status:   MARITAL[d.q48] || d.q48 || '',
    wives:            d.q49 || '',
    has_children:     d.q50 ? (isYes(d.q50) ? 'نعم' : 'لا') : '',
    total_children:   d.q51 || '',
    children_under18: d.q52 || '',
    other_dependents: d.q53 ? (isYes(d.q53) ? 'نعم' : 'لا') : '',
    dependents_count: d.q54 || '',
    other_income:     d.q55 ? (isYes(d.q55) ? 'نعم' : 'لا') : '',
    income_sources:   d.q56 ? lookup(INCOME_SRC, d.q56) : '',
    remittances:      d.q57 || '',
    challenges:       d.q58 || '',
    timestamp:        new Date().toISOString()
  }
}

export default async function handler(req, res) {
  if (req.method === 'GET') {
    const token = req.headers['webhook_verify_token']
    if (token === process.env.WEBHOOK_VERIFY_TOKEN)
      return res.status(200).send('Webhook verified')
    return res.status(403).end()
  }
  if (req.method !== 'POST') return res.status(405).end()

  const entry   = req.body?.entry?.[0]
  const changes = entry?.changes?.[0]
  const messages= changes?.value?.messages

  if (!messages?.length) return res.status(200).json({ status: 'ok' })

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

async function handleMessage(phone, text) {
  const session = await getSession(phone)
  if (session.completed) return

  if (!session.started) {
    session.started = true
    await saveSession(phone, session)
    await sendWhatsApp(phone,
      `*مرحباً بك في برنامج التمويل الزراعي* 🌾\n\nسيتم تسجيلك من خلال هذا النموذج.\nجميع المعلومات ستُحفظ بسرية تامة.\n\nسيستغرق التسجيل حوالي 10 دقائق. ✅`
    )
    await sendWhatsApp(phone, getQuestion(1))
    return
  }

  const error = validateAnswer(session.step, text)
  if (error) {
    await sendWhatsApp(phone, error)
    return
  }

  session.data[`q${session.step}`] = text

  const nextStep = getNextStep(session.step, text)

  if (nextStep > TOTAL_STEPS) {
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
  await sendWhatsApp(phone, getQuestion(nextStep))
}
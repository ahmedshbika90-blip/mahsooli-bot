import { validateAnswer } from '../../utils/validate'
import { sendWhatsApp } from '../../lib/whatsapp'
import { saveToSheets } from '../../lib/sheets'
import { getSession, saveSession } from '../../lib/firebase'
import { isAlreadyProcessed } from '../../utils/session'

const TOTAL_STEPS = 58

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
const NETWORKS   = { '1':'زين','2':'سوداني','3':'MTN' }
const BANKS      = { '1':'بنك الخرطوم','2':'بنك فيصل الإسلامي','3':'بنك النيل','4':'SAB','5':'بنك أمدرمان الوطني','6':'بنك النيلين','7':'أخرى' }
const BANK_APPS  = { '1':'تطبيق بنك الخرطوم','2':'تطبيق بنك فيصل','3':'تطبيق بنك النيل','4':'تطبيق SAB','5':'تطبيق ONB','6':'تطبيق بنك النيلين','7':'لا أستخدم تطبيقاً' }
const CROPS      = { '1':'سمسم','2':'ذرة رفيعة','3':'فول سوداني','4':'قطن','5':'بذرة بطيخ','6':'دخن','7':'عباد الشمس' }
const GUARANTEES = { '1':'شيك','2':'معدات','3':'أرض','4':'أخرى' }
const FINANCE_HOW= { '1':'بنك','2':'تمويل ذاتي','3':'ائتمان تاجر','4':'منظمة','5':'أخرى' }
const NO_REPAY   = { '1':'إنتاج منخفض','2':'تكلفة مدخلات عالية','3':'لا يوجد إنتاج','4':'أخرى' }
const FINANCE_USE= { '1':'بذور','2':'سماد','3':'مبيدات','4':'إيجار آلات','5':'وقود','6':'حصاد' }
const MARITAL    = { '1':'أعزب','2':'متزوج','3':'أرمل','4':'مطلق' }
const INCOME_SRC = { '1':'وظيفة رسمية','2':'تجارة','3':'رعي','4':'حوالات','5':'دعم نقدي من منظمة' }

function lookup(map, val) {
  return val.split(/[,،\s]+/).map(v => map[v.trim()] || v).join('، ')
}
function isYes(val) { return val === 'نعم' || val === '1' }

// ─── Progress header ──────────────────────────────────────────────────────────
function header(step) {
  const pct = Math.round((step / TOTAL_STEPS) * 100)
  const filled = Math.round(pct / 10)
  const bar = '■'.repeat(filled) + '□'.repeat(10 - filled)
  const arabicPct = pct.toString().replace(/\d/g, d => '٠١٢٣٤٥٦٧٨٩'[d])
  const arabicStep = step.toString().replace(/\d/g, d => '٠١٢٣٤٥٦٧٨٩'[d])
  const arabicTotal = TOTAL_STEPS.toString().replace(/\d/g, d => '٠١٢٣٤٥٦٧٨٩'[d])
  return `${bar}  ${arabicPct}٪  •  ${arabicStep} / ${arabicTotal}\n\n`
}
// ─── Welcome message ──────────────────────────────────────────────────────────
const WELCOME = `*برنامج التمويل الزراعي*
استمارة تسجيل المزارعين
────────────────────────

أهلاً بك.

هذه الاستمارة جزء من مبادرة  لدعم المزارعين وتيسير حصولهم على التمويل الزراعي. مشاركتك تُسهم مباشرةً في تطوير هذا البرنامج.

────────────────────────

*تعليمات الإجابة*

· أجب برقم الخيار فقط
  مثال: للاختيار "ذكر" اكتب  1

· لاختيار أكثر من إجابة، افصل بفاصلة
  مثال: 1,3,4

· للأسئلة الاختيارية اكتب  لا يوجد

· جميع بياناتك محفوظة بسرية تامة ولن تُشارك مع أي جهة خارج البرنامج.

────────────────────────

اكتب  *1*  للبدء`
// ─── Questions ────────────────────────────────────────────────────────────────
function getQuestion(step, data = {}) {
  const h = header(step)
  const isMarried = data.q48 === '2'

  switch(step) {

    // ── القسم الأول: المعلومات الشخصية ──────────────────────────────────────

    case 1: return `${h}*القسم الأول — المعلومات الشخصية*
────────────────────────

اسمك الكامل
(الاسم الأول والثاني والثالث إن وُجد)

مثال: أحمد عبدالله إبراهيم`

    case 2: return `${h}اسم العائلة`

    case 3: return `${h}تاريخ الميلاد

الصيغة:  يوم / شهر / سنة
مثال:  15/05/1990`

    case 4: return `${h}الجنس

1 — ذكر
2 — أنثى`

    case 5: return `${h}رقم الهاتف الأساسي

10 أرقام تبدأ بـ 0
مثال: 0912345678`

    case 6: return `${h}رقم الهاتف الثانوي  (اختياري)

اكتب  لا يوجد  إذا لم يكن لديك`

    case 7: return `${h}هل لديك بطاقة هوية وطنية؟

1 — نعم
2 — لا`

    case 8: return `${h}رقم الهوية الوطنية

11 رقماً بالضبط`

    // ── الموقع والتعليم ──────────────────────────────────────────────────────

    case 9: return `${h}*الموقع والتعليم*
────────────────────────

الولاية

1 — الخرطوم       10 — جنوب دارفور
2 — الجزيرة       11 — شرق دارفور
3 — سنار          12 — غرب دارفور
4 — النيل الأبيض  13 — وسط دارفور
5 — النيل الأزرق  14 — كسلا
6 — شمال كردفان   15 — البحر الأحمر
7 — جنوب كردفان   16 — القضارف
8 — غرب كردفان    17 — نهر النيل
9 — شمال دارفور   18 — الشمالية`

    case 10: return `${h}المحلية`

    case 11: return `${h}أعلى مستوى تعليمي

1 — لا يوجد
2 — خلوة (يقرأ ويكتب)
3 — مرحلة أساسية
4 — مرحلة ثانوية
5 — دبلوم
6 — بكالوريوس
7 — ماجستير
8 — دكتوراه`

    case 12: return `${h}هل تمتلك هاتفاً ذكياً؟

1 — نعم
2 — لا`

    case 13: return `${h}هل لديك تغطية شبكة جيدة في منطقتك؟

1 — نعم
2 — لا`

    case 14: return `${h}أفضل شبكة في منطقتك

1 — زين
2 — سوداني
3 — MTN`

    // ── البنوك ───────────────────────────────────────────────────────────────

    case 15: return `${h}هل لديك حساب بنكي؟

1 — نعم
2 — لا`

    case 16: return `${h}البنوك التي لديك حساب فيها

1 — بنك الخرطوم
2 — بنك فيصل الإسلامي
3 — بنك النيل
4 — SAB
5 — بنك أمدرمان الوطني
6 — بنك النيلين
7 — أخرى

أكثر من اختيار: مثال  1,3`

    case 17: return `${h}التطبيقات البنكية التي تستخدمها

1 — تطبيق بنك الخرطوم
2 — تطبيق بنك فيصل
3 — تطبيق بنك النيل
4 — تطبيق SAB
5 — تطبيق ONB
6 — تطبيق بنك النيلين
7 — لا أستخدم تطبيقاً

أكثر من اختيار: مثال  1,3`

    // ── القسم الثاني: الزراعة والتمويل ──────────────────────────────────────

    case 18: return `${h}*القسم الثاني — الزراعة والتمويل*
────────────────────────

هل أنت عضو في اتحاد زراعي أو جمعية؟

1 — نعم
2 — لا`

    case 19: return `${h}اسم الاتحاد أو الجمعية`

    case 20: return `${h}مساحة الأرض الزراعية
بالفدان

مثال: 25  أو  7.5`

    case 21: return `${h}حالة الأرض

1 — مملوكة
2 — مستأجرة`

    case 22: return `${h}مبلغ الإيجار في الموسم
بالجنيه السوداني

مثال: 500000`

    case 23: return `${h}هل لديك وثائق تثبت ملكية الأرض؟

1 — نعم
2 — لا`

    case 24: return `${h}هل لديك ضمانات يمكنك تقديمها؟

1 — نعم
2 — لا`

    case 25: return `${h}نوع الضمان

1 — شيك
2 — معدات
3 — أرض
4 — أخرى

أكثر من اختيار: مثال  1,3`

    case 26: return `${h}يرجى تحديد نوع الضمان الآخر`

    case 27: return `${h}المحاصيل التي زرعتها في آخر 3 مواسم

1 — سمسم
2 — ذرة رفيعة
3 — فول سوداني
4 — قطن
5 — بذرة بطيخ
6 — دخن
7 — عباد الشمس

أكثر من اختيار: مثال  1,2,3`

    // ── متوسط الإنتاجية ──────────────────────────────────────────────────────

    case 28: return `${h}*متوسط الإنتاجية — السمسم*
آخر 3 مواسم  •  شوال / فدان
────────────────────────
اختر قيمة: 1 · 1.5 · 2 · 2.5 · 3 · 3.5 · 4
أو اكتب: لا يوجد`


    case 29: return `${h}*متوسط الإنتاجية — الذرة الرفيعة*
آخر 3 مواسم  •  شوال / فدان
────────────────────────
اختر قيمة: 1 · 1.5 · 2 · 2.5 · 3 · 3.5 · 4
أو اكتب: لا يوجد`

    case 30: return `${h}*متوسط الإنتاجية — الفول السوداني*
آخر 3 مواسم  •  شوال / فدان
────────────────────────
اختر قيمة: 1 · 1.5 · 2 · 2.5 · 3 · 3.5 · 4
أو اكتب: لا يوجد`

    case 31: return `${h}*متوسط الإنتاجية — القطن*
آخر 3 مواسم  •  شوال / فدان
────────────────────────
اختر قيمة: 1 · 1.5 · 2 · 2.5 · 3 · 3.5 · 4
أو اكتب: لا يوجد`

    case 32: return `${h}*متوسط الإنتاجية — بذرة البطيخ*
آخر 3 مواسم  •  شوال / فدان
────────────────────────
اختر قيمة: 1 · 1.5 · 2 · 2.5 · 3 · 3.5 · 4
أو اكتب: لا يوجد`

    case 33: return `${h}*متوسط الإنتاجية — الدخن*
آخر 3 مواسم  •  شوال / فدان
────────────────────────
اختر قيمة: 1 · 1.5 · 2 · 2.5 · 3 · 3.5 · 4
أو اكتب: لا يوجد`

    case 34: return `${h}*متوسط الإنتاجية — عباد الشمس*
آخر 3 مواسم  •  شوال / فدان
────────────────────────
اختر قيمة: 1 · 1.5 · 2 · 2.5 · 3 · 3.5 · 4
أو اكتب: لا يوجد`

    // ── تمويل الموسم الماضي ──────────────────────────────────────────────────

    case 35: return `${h}كيف موّلت زراعتك في الموسم الماضي؟

1 — بنك
2 — تمويل ذاتي
3 — ائتمان تاجر
4 — منظمة
5 — أخرى`

    case 36: return `${h}مبلغ التمويل الذي حصلت عليه
بالجنيه السوداني

مثال: 5000000`

    case 37: return `${h}هل تمكنت من سداد التمويل؟

1 — نعم
2 — لا`

    case 38: return `${h}سبب عدم السداد

1 — إنتاج منخفض
2 — تكلفة مدخلات عالية
3 — لا يوجد إنتاج
4 — أخرى`

    case 39: return `${h}كيف استخدمت التمويل؟

1 — بذور
2 — سماد
3 — مبيدات
4 — إيجار آلات
5 — وقود
6 — حصاد

أكثر من اختيار: مثال  1,2`

    case 40: return `${h}البنك الذي قدّم التمويل

1 — بنك الخرطوم
2 — بنك فيصل الإسلامي
3 — بنك النيل
4 — SAB
5 — بنك أمدرمان الوطني
6 — بنك النيلين
7 — أخرى`

    // ── تفضيلات الموسم القادم ────────────────────────────────────────────────

    case 41: return `${h}*تفضيلات الموسم القادم*
────────────────────────

المحاصيل التي تفضل زراعتها هذا الموسم

1 — سمسم
2 — ذرة رفيعة
3 — فول سوداني
4 — قطن
5 — بذرة بطيخ
6 — دخن
7 — عباد الشمس

أكثر من اختيار: مثال  1,3`

    case 42: return `${h}لماذا تفضل هذه المحاصيل؟
(اختياري — اكتب  لا يوجد  للتخطي)`

    case 43: return `${h}المحصول الذي تطلب تمويلاً له

1 — سمسم
2 — ذرة رفيعة
3 — فول سوداني
4 — قطن
5 — بذرة بطيخ
6 — دخن
7 — عباد الشمس`

    case 44: return `${h}صنف البذرة
(اختياري — اكتب  لا يوجد  إذا لم تعرف)`

    case 45: return `${h}هل تخطط لاستخدام الأسمدة؟

1 — نعم
2 — لا`

    case 46: return `${h}هل تخطط لاستخدام المبيدات؟

1 — نعم
2 — لا`

    case 47: return `${h}مبلغ التمويل المطلوب
بالجنيه السوداني

مثال: 5000000`

    // ── القسم الثالث: معلومات الأسرة ─────────────────────────────────────────

    case 48: return `${h}*القسم الثالث — معلومات الأسرة*
────────────────────────

الحالة الاجتماعية

1 — أعزب
2 — متزوج
3 — أرمل
4 — مطلق`

    case 49: return `${h}عدد الزوجات
(أدخل رقماً من 1 إلى 4)`

    case 50: return `${h}هل لديك أطفال؟

1 — نعم
2 — لا`

    case 51: return `${h}عدد الأطفال الإجمالي`

    case 52: return `${h}عدد الأطفال دون سن 18`

    case 53: {
      if (isMarried) {
        return `${h}هل تعول أشخاصاً آخرين غير أطفالك؟

1 — نعم
2 — لا`
      }
      return `${h}هل هناك أشخاص يعتمدون عليك في معيشتهم؟

1 — نعم
2 — لا`
    }

    case 54: return `${h}كم عددهم؟`

    case 55: return `${h}هل لديك مصادر دخل أخرى غير الزراعة؟

1 — نعم
2 — لا`

    case 56: return `${h}مصادر الدخل الأخرى

1 — وظيفة رسمية
2 — تجارة
3 — رعي
4 — حوالات
5 — دعم نقدي من منظمة

أكثر من اختيار: مثال  1,4`

    case 57: return `${h}المبلغ التقريبي للحوالات سنوياً
بالجنيه السوداني
(اختياري — اكتب  لا يوجد)`

    case 58: return `${h}*ملاحظات ختامية*
────────────────────────

ما التحديات التي تواجهها في الزراعة كل موسم، وما الحلول التي تقترحها؟
(اختياري — اكتب  لا يوجد)`

    default: return null
  }
}

// ─── Skip logic ───────────────────────────────────────────────────────────────
function getNextStep(step, answer) {
  const t = answer.trim()
  switch(step) {
    case 7:  return isYes(t) ? 8 : 9
    case 15: return isYes(t) ? 16 : 18
    case 18: return isYes(t) ? 19 : 20
    case 21: return (t==='1'||t==='مملوكة') ? 23 : 22
    case 22: return 24
    case 24: return isYes(t) ? 25 : 27
    case 25: return t.includes('4') ? 26 : 27
    case 35: return t === '1' ? 36 : 41
    case 37: return isYes(t) ? 39 : 38
    case 38: return 39
    case 48: return t === '2' ? 49 : 53   // married → wives, else → dependents
    case 49: return 50
    case 50: return isYes(t) ? 51 : 53
    case 53: return isYes(t) ? 54 : 55
    case 55: return isYes(t) ? 56 : 57
    default: return step + 1
  }
}

// ─── Sheets row builder ───────────────────────────────────────────────────────
function buildSheetsRow(phone, d) {
  const nameParts = (d.q1 || '').split(/\s+/).filter(Boolean)
  return {
    phone,
    first_name:       nameParts[0] || '',
    second_name:      nameParts[1] || '',
    third_name:       nameParts[2] || '',
    last_name:        d.q2  || '',
    dob:              d.q3  || '',
    gender:           d.q4==='1' ? 'ذكر' : d.q4==='2' ? 'أنثى' : d.q4 || '',
    phone_primary:    d.q5  || '',
    phone_secondary:  d.q6  || '',
    has_national_id:  isYes(d.q7 ||'') ? 'نعم' : 'لا',
    national_id:      d.q8  || '',
    state:            STATES[d.q9]   || d.q9  || '',
    locality:         d.q10 || '',
    education:        EDUCATION[d.q11] || d.q11 || '',
    has_smartphone:   isYes(d.q12||'') ? 'نعم' : 'لا',
    network_coverage: isYes(d.q13||'') ? 'نعم' : 'لا',
    best_network:     NETWORKS[d.q14]  || d.q14 || '',
    has_bank:         isYes(d.q15||'') ? 'نعم' : 'لا',
    banks:            d.q16 ? lookup(BANKS,     d.q16) : '',
    banking_apps:     d.q17 ? lookup(BANK_APPS, d.q17) : '',
    union_member:     isYes(d.q18||'') ? 'نعم' : 'لا',
    union_name:       d.q19 || '',
    farm_size:        d.q20 || '',
    land_ownership:   (d.q21==='1'||d.q21==='مملوكة') ? 'مملوكة' : 'مستأجرة',
    rent_amount:      d.q22 || '',
    ownership_docs:   isYes(d.q23||'') ? 'نعم' : 'لا',
    has_guarantees:   isYes(d.q24||'') ? 'نعم' : 'لا',
    guarantee_types:  d.q25 ? lookup(GUARANTEES,  d.q25) : '',
    other_guarantee:  d.q26 || '',
    crops_last3:      d.q27 ? lookup(CROPS,       d.q27) : '',
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
    no_repay_reason:  d.q38 ? NO_REPAY[d.q38]   || d.q38 : '',
    finance_use:      d.q39 ? lookup(FINANCE_USE, d.q39) : '',
    finance_bank:     d.q40 ? BANKS[d.q40]       || d.q40 : '',
    preferred_crops:  d.q41 ? lookup(CROPS,       d.q41) : '',
    why_preferred:    d.q42 || '',
    finance_crop:     d.q43 ? CROPS[d.q43]       || d.q43 : '',
    seed_variety:     d.q44 || '',
    use_fertiliser:   isYes(d.q45||'') ? 'نعم' : 'لا',
    use_pesticides:   isYes(d.q46||'') ? 'نعم' : 'لا',
    requested_amount: d.q47 || '',
    marital_status:   MARITAL[d.q48]   || d.q48 || '',
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

// ─── Webhook handler ──────────────────────────────────────────────────────────
export default async function handler(req, res) {
  if (req.method === 'GET') {
    const token = req.headers['webhook_verify_token']
    if (token === process.env.WEBHOOK_VERIFY_TOKEN)
      return res.status(200).send('Webhook verified')
    return res.status(403).end()
  }
  if (req.method !== 'POST') return res.status(405).end()

  const entry    = req.body?.entry?.[0]
  const changes  = entry?.changes?.[0]
  const messages = changes?.value?.messages

  if (!messages?.length) return res.status(200).json({ status: 'ok' })

  for (const message of messages) {
    const phone = message.from
    if (isAlreadyProcessed(message.id)) continue
    if (message.type !== 'text') {
      await sendWhatsApp(phone, 'يرجى الرد برسالة نصية فقط.')
      continue
    }
    const text = message.text.body.trim()
    if (!text) continue
    await handleMessage(phone, text)
  }

  return res.status(200).json({ status: 'ok' })
}

// ─── Main message handler ─────────────────────────────────────────────────────
async function handleMessage(phone, text) {
  const session = await getSession(phone)
  if (session.completed) return

  if (!session.greeted) {
    session.greeted = true
    await saveSession(phone, session)
    await sendWhatsApp(phone, WELCOME)
    return
  }

  if (!session.started) {
    if (text === '1') {
      session.started = true
      session.step = 1
      session.last_activity = Date.now()
      await Promise.all([
        saveSession(phone, session),
        sendWhatsApp(phone, getQuestion(1, session.data))
      ])
    } else {
      await sendWhatsApp(phone, 'اكتب  *1*  للبدء في التسجيل')
    }
    return
  }

  // ── User resuming after reminder ─────────────────────────────────────────
 if (session.awaiting_resume) {
  if (text === '2') {
    session.awaiting_resume = false
    session.last_activity = Date.now()
    await Promise.all([
      saveSession(phone, session),
      sendWhatsApp(phone, getQuestion(session.step, session.data))
    ])
  } else {
    await sendWhatsApp(phone,
      `اكتب  *2*  للمتابعة من حيث توقفت.`
    )
  }
  return
}

  // ── Normal flow ──────────────────────────────────────────────────────────
  const error = validateAnswer(session.step, text)
  if (error) {
    await sendWhatsApp(phone, error)
    return
  }

  session.data[`q${session.step}`] = text
  session.last_activity = Date.now()
  const nextStep = getNextStep(session.step, text)

  if (nextStep > TOTAL_STEPS) {
    const [saved] = await Promise.all([
      saveToSheets(buildSheetsRow(phone, session.data)),
      saveSession(phone, { completed: true, step: TOTAL_STEPS, started: true, greeted: true, data: {} })
    ])

    if (!saved) {
      await sendWhatsApp(phone, 'حدث خطأ في حفظ البيانات. يرجى المحاولة مرة أخرى.')
      return
    }

    await sendWhatsApp(phone,
      `تم التسجيل بنجاح ✓\n────────────────────────\nشكراً لك. سيتواصل معك فريقنا قريباً.\n\nنتمنى لك موسماً زراعياً موفقاً.`
    )
    return
  }

  session.step = nextStep
  await Promise.all([
    saveSession(phone, session),
    sendWhatsApp(phone, getQuestion(nextStep, session.data))
  ])
}
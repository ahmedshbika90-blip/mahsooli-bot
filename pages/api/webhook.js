import { uploadIdPhoto } from '../../lib/storage'
import { validateAnswer, getLocalities, getVarieties } from '../../utils/validate'
import { sendWhatsApp } from '../../lib/whatsapp'
import { saveToSheets } from '../../lib/sheets'
import { getSession, saveSession } from '../../lib/firebase'
import { saveToFirestore } from '../../lib/firestore'
import { isAlreadyProcessed } from '../../utils/session'
import { verifyNationalId } from '../../lib/claude'
import { downloadMedia }    from '../../lib/media'
const TOTAL_STEPS = 68

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
const NETWORKS    = {'1':'زين','2':'سوداني','3':'MTN'}
const BANKS       = {'1':'بنك الخرطوم','2':'بنك أمدرمان الوطني','3':'البنك الزراعي السوداني','4':'بنك فيصل الإسلامي','5':'بنك النيل','6':'بنك النيلين','7':'مصرف المزارع','8':'أخرى'}
const BANK_APPS   = {'1':'بنكك','2':'اوكاش','3':'مصرفك','4':'الزراعي موبايل','5':'فوري','6':'ساهل','7':'من مكانك','8':'لا أستخدم تطبيقاً'}
const CROPS       = {'1':'سمسم','2':'ذرة رفيعة','3':'فول سوداني','4':'قطن','5':'حب بطيخ','6':'دخن','7':'عباد الشمس'}
const GUARANTEES  = {'1':'شيك','2':'معدات','3':'أرض','4':'أخرى'}
const FINANCE_HOW = {'1':'بنك','2':'تمويل ذاتي','3':'ائتمان تاجر','4':'منظمة','5':'أخرى'}
const NO_REPAY    = {'1':'انخفاض الإنتاج','2':'ارتفاع تكاليف المدخلات','3':'لا يوجد إنتاج','4':'أسباب أخرى'}
const FINANCE_USE = {'1':'بذور','2':'سماد','3':'مبيدات','4':'إيجار آلات','5':'وقود','6':'حصاد'}
const CROP_REASON = {'1':'سعر أفضل','2':'طلب محلي','3':'محصول مألوف','4':'مناسب للتربة','5':'مخاطر أقل','6':'إمكانية التخزين','7':'توافر المدخلات','8':'نصيحة متخصص','9':'أخرى'}
const NO_INPUT_REASON = {'1':'التكلفة عالية','2':'غير متاح','3':'المحصول لا يحتاجه','4':'تجربة سلبية','5':'أخرى'}
const MARITAL     = {'1':'أعزب','2':'متزوج','3':'أرمل','4':'مطلق'}
const RENT_TENURE = {'1':'موسم واحد','2':'موسمان','3':'من ٣ إلى ٥ مواسم','4':'أكثر من ٥ مواسم'}
const INCOME_SRC  = {
  '1':'وظيفة رسمية','2':'تجارة','3':'العمل بالأجر اليومي',
  '4':'خدمات نقل وترحيل','5':'المعاش','6':'حرف يدوية',
  '7':'إيجار الأراضي أو المعدات','8':'رعي','9':'حوالات','10':'دعم نقدي من منظمات'
}
// Crop step mapping for yield questions
const CROP_YIELD_STEP = {'1':29,'2':30,'3':31,'4':32,'5':33,'6':34,'7':35}
const YIELD_STEP_CROP = {29:'1',30:'2',31:'3',32:'4',33:'5',34:'6',35:'7'}
const YIELD_CROP_NAME = {29:'السمسم',30:'الذرة الرفيعة',31:'الفول السوداني',32:'القطن',33:'حب البطيخ',34:'الدخن',35:'عباد الشمس'}
const YIELD_UNIT      = {29:'شوال',30:'شوال',31:'شوال',32:'قنطار',33:'شوال',34:'شوال',35:'شوال'}

function lookup(map, val) {
  return val.split(/[,،\s]+/).map(v => map[v.trim()] || v).join('، ')
}
function isYes(val) { return val === '1' }
function isNo(val)  { return val === '2' }

// ─── Progress header ──────────────────────────────────────────────────────────
function header(step) {
  const sections = [
    { label: 'البيانات الشخصية',      steps: [1,2,3,4,5,6,7,8] },
    { label: 'بيانات السكن والتواصل', steps: [9,10,11,12,13,14,15,16,17,18] },
    { label: 'الزراعة والتمويل',      steps: [19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44] },
    { label: 'المحاصيل وطلب التمويل', steps: [45,46,47,48,49,50,51,52,53,54,55,56,57] },
    { label: 'بيانات الأسرة',          steps: [58,59,60,61,62,63,64,65,66,67,68] },
  ]

  const ar = n => n.toString().replace(/\d/g, d => '٠١٢٣٤٥٦٧٨٩'[d])
  const current = sections.findIndex(s => s.steps.includes(step))
  const sectionNum = current + 1
  const label = sections[current]?.label || ''

  return `القسم ${ar(sectionNum)} من ${ar(sections.length)}  •  ${label}\n\n`
}
// ─── Welcome message ──────────────────────────────────────────────────────────
const WELCOME = `*برنامج التمويل الزراعي*
البنك الزراعي السوداني بالشراكة مع محصولي
────────────────────────

أهلاً بك.

هذه الاستمارة جزء من مبادرة لدعم المزارعين وتيسير حصولهم على التمويل الزراعي. مشاركتك تُسهم مباشرةً في تطوير هذا البرنامج.

────────────────────────

*تعليمات الإجابة*

· أجب برقم الخيار فقط
  مثال: للاختيار "ذكر" اكتب  ١

· لاختيار أكثر من إجابة، افصل بفاصلة
  مثال: ١,٣,٤

· للمبالغ المالية الكبيرة، استخدم الفاصلة
  مثال: ١,٥٠٠,٠٠٠ وليس ١٥٠٠٠٠٠  
  
· للأسئلة الاختيارية اكتب  لا يوجد

· جميع بياناتك محفوظة بسرية تامة ولن تُشارك مع أي جهة خارج البرنامج.

────────────────────────

اكتب  *١*  للبدء`

// ─── Questions ────────────────────────────────────────────────────────────────
function getQuestion(step, data = {}) {
  const h = header(step)
  const isMarried = data.q58 === '2'

  switch(step) {

    case 1: return `${h}*القسم الأول — البيانات الشخصية*
────────────────────────

ما اسمك الرباعي؟

مثال: أحمد محمد إبراهيم إسماعيل`

    case 2: return `${h}تاريخ الميلاد

اليوم / الشهر / السنة
مثال: ١٥/٠٦/١٩٨٥`

    case 3: return `${h}الجنس 

١ — ذكر
٢ — أنثى`

    case 4: return `${h}رقم الهاتف الأساسي

١٠ أرقام تبدأ بـ ٠
مثال: ٠٩١٢٣٤٥٦٧٨`

    case 5: return `${h}رقم الهاتف الثانوي  (اختياري)

اكتب  لا يوجد  إذا لم يكن لديك`

  case 6: return `${h}هل لديك بطاقة إثبات شخصية؟
(رقم وطني / جواز سفر / بطاقة قومية)

١ — نعم
٢ — لا`

  

    case 8: return `${h}أرسل صورة واضحة لبطاقة إثبات الشخصية

التقط صورة للبطاقة وأرسلها`

    case 9: return `${h}*القسم الثاني — بيانات السكن والتواصل*
────────────────────────

الولاية

١ — الخرطوم       ١٠ — جنوب دارفور
٢ — الجزيرة       ١١ — شرق دارفور
٣ — سنار          ١٢ — غرب دارفور
٤ — النيل الأبيض  ١٣ — وسط دارفور
٥ — النيل الأزرق  ١٤ — كسلا
٦ — شمال كردفان   ١٥ — البحر الأحمر
٧ — جنوب كردفان   ١٦ — القضارف
٨ — غرب كردفان    ١٧ — نهر النيل
٩ — شمال دارفور   ١٨ — الشمالية`

    case 10: {
      const localities = getLocalities(data.q9 || '')
      const list = localities.map((l,i) => `${i+1} — ${l}`).join('\n')
      return `${h}المحلية\n\n${list}`
    }

    case 11: return `${h}أعلى مستوى تعليمي

١ — لا يوجد
٢ — خلوة (يقرأ ويكتب)
٣ — مرحلة أساسية
٤ — مرحلة ثانوية
٥ — دبلوم
٦ — بكالوريوس
٧ — ماجستير
٨ — دكتوراه`

    case 12: return `${h}هل تمتلك هاتفاً ذكياً؟

١ — نعم
٢ — لا`

    case 13: return `${h}هل تغطية شبكة الاتصال جيدة في منطقتك؟

١ — نعم
٢ — لا`

    case 14: return `${h}أفضل شبكة في منطقتك

١ — زين
٢ — سوداني
٣ — MTN`

    case 15: return `${h}هل لديك حساب في أي بنك؟

١ — نعم
٢ — لا`

    case 16: return `${h}في أي بنك لديك حساب؟

١ — بنك الخرطوم
٢ — بنك أمدرمان الوطني
٣ — البنك الزراعي السوداني
٤ — بنك فيصل الإسلامي
٥ — بنك النيل
٦ — بنك النيلين
٧ — مصرف المزارع
٨ — أخرى

أكثر من اختيار: مثال  ١,٣`

    case 17: return `${h}أي تطبيق بنكي تستخدم؟

١ — بنكك  (الخرطوم)
٢ — اوكاش  (أمدرمان)
٣ — مصرفك  (المزارع)
٤ — الزراعي موبايل
٥ — فوري  (فيصل)
٦ — ساهل  (النيل)
٧ — من مكانك  (النيلين)
٨ — لا أستخدم تطبيقاً

أكثر من اختيار: مثال  ١,٣`

   case 18: {
  const fromBank = (data.q16 || '').includes('8') && !data.q17
  return `${h}${fromBank ? 'اذكر اسم البنك' : 'اذكر اسم التطبيق البنكي'}`
}

    case 19: return `${h}*القسم الثالث — الزراعة والتمويل*
────────────────────────

هل أنت عضو في اتحاد زراعي أو جمعية؟

١ — نعم
٢ — لا`

    case 20: return `${h}اذكر اسم الاتحاد أو الجمعية`

    case 21: return `${h}*تفاصيل المزرعة*
────────────────────────

مساحة الأرض الزراعية  (فدان)

مثال: ٥٠`

    case 22: return `${h}حالة الأرض

١ — مملوكة
٢ — مستأجرة`

    case 23: return `${h}مدة عقد الإيجار

١ — موسم واحد
٢ — موسمان
٣ — من ٣ إلى ٥ مواسم
٤ — أكثر من ٥ مواسم`

    case 24: return `${h}هل لديك وثائق رسمية تثبت ملكية الأرض؟

١ — نعم
٢ — لا`

    case 25: return `${h}*الضمانات والمحاصيل*
────────────────────────

هل بإمكانك تقديم ضمانات؟

١ — نعم
٢ — لا`

    case 26: return `${h}نوع الضمان

١ — شيك
٢ — معدات
٣ — أرض
٤ — أخرى

أكثر من اختيار: مثال  ١,٣`

    case 27: return `${h}اذكر نوع الضمان`

    case 28: return `${h}المحاصيل التي زرعتها في آخر ٣ مواسم

١ — سمسم
٢ — ذرة رفيعة
٣ — فول سوداني
٤ — قطن
٥ — حب بطيخ
٦ — دخن
٧ — عباد الشمس

أكثر من اختيار: مثال  ١,٢,٣`

    case 29:
    case 30:
    case 31:
    case 32:
    case 33:
    case 34:
    case 35: {
      const cropName = YIELD_CROP_NAME[step]
      const unit     = YIELD_UNIT[step]
      return `${h}*متوسط الإنتاجية — ${cropName}*
آخر ٣ مواسم  •  ${unit} / فدان
────────────────────────
أرسل رقماً فقط
مثال: ٥٠`
    }

    case 36: return `${h}كيف موّلت زراعتك في الموسم الماضي؟

١ — بنك
٢ — تمويل ذاتي
٣ — ائتمان تاجر
٤ — منظمة
٥ — أخرى`

    case 37: return `${h}وضّح كيف موّلت زراعتك`

    case 38: return `${h}مبلغ التمويل الذي حصلت عليه
بالجنيه السوداني

مثال: ١,٥٠٠,٠٠٠`

    case 39: return `${h}هل تمكنت من سداد التمويل كاملاً؟

١ — نعم
٢ — لا`

    case 40: return `${h}لماذا لم تتمكن من السداد؟

١ — انخفاض الإنتاج
٢ — ارتفاع تكاليف المدخلات
٣ — لا يوجد إنتاج
٤ — أسباب أخرى`

    case 41: return `${h}وضّح سبب عدم السداد`

    case 42: return `${h}كيف استخدمت مبلغ التمويل؟

١ — بذور
٢ — سماد
٣ — مبيدات
٤ — إيجار آلات
٥ — وقود
٦ — حصاد

أكثر من اختيار: مثال  ١,٢`

    case 43: return `${h}من أين حصلت على التمويل؟

١ — بنك الخرطوم
٢ — بنك أمدرمان الوطني
٣ — البنك الزراعي السوداني
٤ — بنك فيصل الإسلامي
٥ — بنك النيل
٦ — بنك النيلين
٧ — مصرف المزارع
٨ — أخرى`

    case 44: return `${h}اذكر اسم البنك`

case 45: {
  const selectedCrops = (data.q28 || '').split(/[,،\s]+/).filter(Boolean)
  const isSingle = selectedCrops.length === 1
  return `${h}*المحاصيل وطلب التمويل*
────────────────────────

${isSingle ? 'المحصول الذي تريد زراعته هذا الموسم' : 'المحاصيل التي تريد زراعتها هذا الموسم'}

١ — سمسم
٢ — ذرة رفيعة
٣ — فول سوداني
٤ — قطن
٥ — حب بطيخ
٦ — دخن
٧ — عباد الشمس

${isSingle ? '' : 'أكثر من اختيار: مثال  ١,٣'}`
}

   case 46: {
  const count = (data.q45 || '').split(/[,،\s]+/).filter(Boolean).length
  const word = count === 1 ? 'هذا المحصول' : 'هذه المحاصيل'
  return `${h}لماذا اخترت ${word}؟  (اختياري)

١ — سعر أفضل في السوق
٢ — طلب محلي مرتفع
٣ — محصول مألوف ومتعارف عليه
٤ — مناسب لطبيعة المنطقة والتربة
٥ — مخاطر أقل
٦ — إمكانية التخزين
٧ — توافر المدخلات
٨ — بناءً على نصيحة متخصص
٩ — أخرى

أكثر من اختيار: مثال  ١,٤
أو اكتب: لا يوجد`
}

    case 47: return `${h}وضّح السبب`

    case 48: return `${h}لأي محصول تريد طلب التمويل؟
(اختر محصولاً واحداً فقط)

١ — سمسم
٢ — ذرة رفيعة
٣ — فول سوداني
٤ — قطن
٥ — حب بطيخ
٦ — دخن
٧ — عباد الشمس`

    case 49: {
      const varieties = getVarieties(data.q48 || '')
      if (!varieties.length) return `${h}ما الصنف الذي تريد زراعته؟  (اختياري)\n\nاكتب  لا يوجد  إذا لم تعرف`
      const list = varieties.map((v,i) => `${i+1} — ${v}`).join('\n')
      return `${h}ما الصنف الذي تريد زراعته؟\n\n${list}`
    }

    case 50: return `${h}اذكر اسم الصنف`

    case 51: return `${h}هل ستستخدم الأسمدة هذا الموسم؟

١ — نعم
٢ — لا`

    case 52: return `${h}لماذا لن تستخدم الأسمدة؟

١ — التكلفة عالية
٢ — غير متاح في المنطقة
٣ — المحصول لا يحتاجه
٤ — تجربة سلبية سابقة
٥ — أخرى

أكثر من اختيار: مثال  ١,٢`

    case 53: return `${h}وضّح السبب`

    case 54: return `${h}هل ستستخدم المبيدات هذا الموسم؟

١ — نعم
٢ — لا`

    case 55: return `${h}لماذا لن تستخدم المبيدات؟

١ — التكلفة عالية
٢ — غير متاح في المنطقة
٣ — المحصول لا يحتاجه
٤ — تجربة سلبية سابقة
٥ — أخرى

أكثر من اختيار: مثال  ١,٢`

    case 56: return `${h}وضّح السبب`

    case 57: return `${h}المبلغ الذي تحتاجه كتمويل
بالجنيه السوداني

مثال: ١,٥٠٠,٠٠٠`

    case 58: return `${h}*القسم الرابع — بيانات الأسرة*
────────────────────────

الحالة الاجتماعية

١ — أعزب
٢ — متزوج
٣ — أرمل
٤ — مطلق`

    case 59: return `${h}عدد الزوجات
(أدخل رقماً من ١ إلى ٤)`

    case 60: return `${h}هل لديك أطفال؟

١ — نعم
٢ — لا`

    case 61: return `${h}عدد الأطفال الإجمالي`

    case 62: return `${h}كم منهم دون سن الـ ١٨؟`

    case 63: {
      if (isMarried) return `${h}هل تعول أشخاصاً آخرين غير أطفالك؟\n\n١ — نعم\n٢ — لا`
      return `${h}هل هناك أشخاص يعتمدون عليك في معيشتهم؟\n\n١ — نعم\n٢ — لا`
    }

    case 64: return `${h}كم عددهم؟`

    case 65: return `${h}هل لديك مصدر دخل آخر غير الزراعة؟

١ — نعم
٢ — لا`

    case 66: return `${h}مصادر دخلك الأخرى

١ — وظيفة رسمية
٢ — تجارة
٣ — العمل بالأجر اليومي
٤ — خدمات نقل وترحيل
٥ — المعاش
٦ — حرف يدوية
٧ — إيجار الأراضي أو المعدات
٨ — رعي
٩ — حوالات
١٠ — دعم نقدي من منظمات

أكثر من اختيار: مثال  ١,٤`

    case 67: return `${h}المبلغ التقريبي للحوالات سنوياً
بالجنيه السوداني  (اختياري)

اكتب  لا يوجد  إذا لم تشأ الإجابة`

    case 68: return `${h}*الإقرار والموافقة*
────────────────────────

أُقِرُّ بأن جميع المعلومات التي قدمتها صحيحة ودقيقة. كما أوافق على قيام محصولي بمعالجة هذه البيانات واستخدامها في تقييم طلبي للتمويل الزراعي وفقاً لشروط وأحكام البرنامج.

تتعهد محصولي بالحفاظ على سرية هذه المعلومات وعدم الإفصاح عنها لأي طرف ثالث إلا في حدود متطلبات التمويل.

────────────────────────

١ — أقر وأوافق بما ورد أعلاه`

    default: return null
  }
}

// ─── Yield step helpers ───────────────────────────────────────────────────────
function getYieldSteps(cropsAnswer) {
  return (cropsAnswer || '')
    .split(/[,،\s]+/)
    .map(c => c.trim())
    .filter(c => CROP_YIELD_STEP[c])
    .map(c => CROP_YIELD_STEP[c])
    .sort((a,b) => a - b)
}

// ─── Skip logic ───────────────────────────────────────────────────────────────
function getNextStep(step, answer, data) {
  const t = answer.trim()

  switch(step) {
    case 6:  return isYes(t) ? 7 : 9        // has ID → number, else → state
    case 7:  return 8                        // ID number → photo
    case 8:  return 9                        // photo → state
    case 15: return isYes(t) ? 16 : 19      // has bank → which banks, else → union
    case 16: return t.includes('8') ? 18 : 17   // other bank → step 18
    case 17: return t.includes('8') ? 18 : 19   // other app → step 18
    case 18: return 19                           // either other → union
    case 19: return isYes(t) ? 20 : 21      // union → name, else → farm
    case 22: return t === '2' ? 23 : 24     // rented → tenure, owned → docs
    case 23: return 25                       // tenure → guarantees
    case 25: return isYes(t) ? 26 : 28      // has guarantees → type, else → crops
    case 26: return t.includes('4') ? 27 : 28  // other → specify, else → crops
    case 28: {                               // crops → first yield step
      const yieldSteps = getYieldSteps(t)
      return yieldSteps.length > 0 ? yieldSteps[0] : 36
    }
    case 29:
    case 30:
    case 31:
    case 32:
    case 33:
    case 34:
    case 35: {                               // yield → next yield or finance
      const yieldSteps = getYieldSteps(data.q28 || '')
      const idx = yieldSteps.indexOf(step)
      return idx < yieldSteps.length - 1 ? yieldSteps[idx + 1] : 36
    }
    case 36: return t === '1' ? 38 : 45     // bank → amount, else → preferred crops
    case 37: return 45                       // other finance → preferred crops
    case 36: return t === '1' ? 38 : t === '5' ? 37 : 45
    case 39: return isYes(t) ? 42 : 40      // repaid → use, not repaid → why
    case 40: return t === '4' ? 41 : 42     // other reason → specify, else → use
    case 41: return 42
    case 43: return t === '8' ? 44 : 45     // other bank → name, else → preferred
    case 44: return 45
    case 46: return t.includes('9') ? 47 : 48   // other reason → specify
    case 47: return 48
    case 49: {                               // variety → other if last choice
      const varieties = getVarieties(data.q48 || '')
      const lastChoice = String(varieties.length)
      return (t === lastChoice && varieties[varieties.length-1] === 'أخرى') ? 50 : 51
    }
    case 50: return 51
    case 51: return isYes(t) ? 54 : 52      // fertilizer yes → pesticides, no → why
    case 52: return t.includes('5') ? 53 : 54   // other → specify
    case 53: return 54
    case 54: return isYes(t) ? 57 : 55      // pesticides yes → amount, no → why
    case 55: return t.includes('5') ? 56 : 57   // other → specify
    case 56: return 57
    case 58: {
     if (t === '2') return 59   // married → wives
     if (t === '1') return 63   // single → skip to dependents
      return 60                   // widowed/divorced → children
                  }
    case 59: return 60              
    case 60: return isYes(t) ? 61 : 63      // has children → count, else → dependents
    case 61: return 62
    case 63: return isYes(t) ? 64 : 65      // dependents → count
    case 64: return 65
    case 65: return isYes(t) ? 66 : 68      // other income → sources, else → consent
    case 66: return t.includes('9') ? 67 : 68   // remittances → amount
    case 67: return 68
    default: return step + 1
  }
}

// ─── Sheets row builder ───────────────────────────────────────────────────────
function buildRow(phone, d) {
  const v = (key) => d[key] || 'لا ينطبق'
  const nameParts = (d.q1 || '').split(/\s+/).filter(Boolean)
  const localities = getLocalities(d.q9 || '')
  const localityName = localities[parseInt(d.q10)-1] || d.q10 || 'لا ينطبق'

  return {
    phone,
    first_name:         nameParts[0] || 'لا ينطبق',
    second_name:        nameParts[1] || 'لا ينطبق',
    third_name:         nameParts[2] || 'لا ينطبق',
    fourth_name:        nameParts[3] || 'لا ينطبق',
    dob:                v('q2'),
    gender:             d.q3==='1' ? 'ذكر' : d.q3==='2' ? 'أنثى' : 'لا ينطبق',
    phone_primary:      v('q4'),
    phone_secondary:    v('q5'),
    has_id:             d.q6 ? (isYes(d.q6) ? 'نعم' : 'لا') : 'لا ينطبق',
    id_number:          v('q7'),
    id_photo:           v('q8'),
    state:              STATES[d.q9] || 'لا ينطبق',
    locality:           localityName,
    education:          EDUCATION[d.q11] || 'لا ينطبق',
    has_smartphone:     d.q12 ? (isYes(d.q12) ? 'نعم' : 'لا') : 'لا ينطبق',
    network_coverage:   d.q13 ? (isYes(d.q13) ? 'نعم' : 'لا') : 'لا ينطبق',
    best_network:       NETWORKS[d.q14] || 'لا ينطبق',
    has_bank:           d.q15 ? (isYes(d.q15) ? 'نعم' : 'لا') : 'لا ينطبق',
    banks:              d.q16 ? lookup(BANKS, d.q16) : 'لا ينطبق',
    banking_apps:       d.q17 ? lookup(BANK_APPS, d.q17) : 'لا ينطبق',
    other_bank:         v('q18'),
    union_member:       d.q19 ? (isYes(d.q19) ? 'نعم' : 'لا') : 'لا ينطبق',
    union_name:         v('q20'),
    farm_size:          v('q21'),
    land_ownership:     d.q22==='1' ? 'مملوكة' : d.q22==='2' ? 'مستأجرة' : 'لا ينطبق',
    rent_tenure:        RENT_TENURE[d.q23] || 'لا ينطبق',
    ownership_docs:     d.q24 ? (isYes(d.q24) ? 'نعم' : 'لا') : 'لا ينطبق',
    has_guarantees:     d.q25 ? (isYes(d.q25) ? 'نعم' : 'لا') : 'لا ينطبق',
    guarantee_types:    d.q26 ? lookup(GUARANTEES, d.q26) : 'لا ينطبق',
    other_guarantee:    v('q27'),
    crops_last3:        d.q28 ? lookup(CROPS, d.q28) : 'لا ينطبق',
    yield_sesame:       v('q29'),
    yield_sorghum:      v('q30'),
    yield_groundnut:    v('q31'),
    yield_cotton:       v('q32'),
    yield_watermelon:   v('q33'),
    yield_millet:       v('q34'),
    yield_sunflower:    v('q35'),
    finance_source:     FINANCE_HOW[d.q36] || 'لا ينطبق',
    other_finance:      v('q37'),
    finance_amount:     d.q38 ? d.q38.replace(/,|،/g, '') : 'لا ينطبق',
    repaid:             d.q39 ? (isYes(d.q39) ? 'نعم' : 'لا') : 'لا ينطبق',
    no_repay_reason:    NO_REPAY[d.q40] || 'لا ينطبق',
    other_repay_reason: v('q41'),
    finance_use:        d.q42 ? lookup(FINANCE_USE, d.q42) : 'لا ينطبق',
    finance_bank:       BANKS[d.q43] || 'لا ينطبق',
    other_finance_bank: v('q44'),
    preferred_crops:    d.q45 ? lookup(CROPS, d.q45) : 'لا ينطبق',
    crop_reason:        d.q46 ? lookup(CROP_REASON, d.q46) : 'لا ينطبق',
    other_crop_reason:  v('q47'),
    finance_crop:       CROPS[d.q48] || 'لا ينطبق',
    seed_variety:       (() => {
      const varieties = getVarieties(d.q48 || '')
      return varieties[parseInt(d.q49)-1] || d.q49 || 'لا ينطبق'
    })(),
    other_variety:      v('q50'),
    use_fertiliser:     d.q51 ? (isYes(d.q51) ? 'نعم' : 'لا') : 'لا ينطبق',
    no_fertiliser_reason: d.q52 ? lookup(NO_INPUT_REASON, d.q52) : 'لا ينطبق',
    other_no_fertiliser:  v('q53'),
    use_pesticides:     d.q54 ? (isYes(d.q54) ? 'نعم' : 'لا') : 'لا ينطبق',
    no_pesticides_reason: d.q55 ? lookup(NO_INPUT_REASON, d.q55) : 'لا ينطبق',
    other_no_pesticides:  v('q56'),
    requested_amount:   d.q57 ? d.q57.replace(/,|،/g, '') : 'لا ينطبق',
    marital_status:     MARITAL[d.q58] || 'لا ينطبق',
    wives:              v('q59'),
    has_children:       d.q60 ? (isYes(d.q60) ? 'نعم' : 'لا') : 'لا ينطبق',
    total_children:     v('q61'),
    children_under18:   v('q62'),
    other_dependents:   d.q63 ? (isYes(d.q63) ? 'نعم' : 'لا') : 'لا ينطبق',
    dependents_count:   v('q64'),
    other_income:       d.q65 ? (isYes(d.q65) ? 'نعم' : 'لا') : 'لا ينطبق',
    income_sources:     d.q66 ? lookup(INCOME_SRC, d.q66) : 'لا ينطبق',
    remittances:        v('q67'),
    consent:            d.q68 === '1' ? 'أقر وأوافق' : 'لا ينطبق',
    timestamp:          new Date().toISOString()
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

    // Handle image messages for ID photo step
 if (message.type === 'image') {
  console.log('Full image object:', JSON.stringify(message.image))
  await handleMessage(phone, '__IMAGE__', message)
  continue
}

    if (message.type !== 'text') {
      await sendWhatsApp(phone, 'يرجى الرد برسالة نصية فقط.')
      continue
    }

    const text = message.text.body.trim()
    if (!text) continue
    await handleMessage(phone, text, message)
  }

  return res.status(200).json({ status: 'ok' })
}

// ─── Main message handler ─────────────────────────────────────────────────────
async function handleMessage(phone, text, message = {}) {
  const session = await getSession(phone)
  if (session.completed) return

  // ── Not greeted ──────────────────────────────────────────────────────────────
  if (!session.greeted) {
    session.greeted = true
    await saveSession(phone, session)
    await sendWhatsApp(phone, WELCOME)
    return
  }

  // ── Not started — wait for ١ ─────────────────────────────────────────────────
  if (!session.started) {
    const normalized = text.replace(/[١٢٣٤٥٦٧٨٩٠]/g, d => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)))
    if (normalized === '1') {
      session.started = true
      session.step = 1
      session.last_activity = Date.now()
      await Promise.all([
        saveSession(phone, session),
        sendWhatsApp(phone, getQuestion(1, session.data))
      ])
    } else {
      await sendWhatsApp(phone, 'اكتب  *١*  للبدء في التسجيل')
    }
    return
  }

  // ── Awaiting resume after reminder ──────────────────────────────────────────
  if (session.awaiting_resume) {
    const normalized = text.replace(/[١٢٣٤٥٦٧٨٩٠]/g, d => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)))
    if (normalized === '2') {
      session.awaiting_resume = false
      session.last_activity = Date.now()
      await Promise.all([
        saveSession(phone, session),
        sendWhatsApp(phone, getQuestion(session.step, session.data))
      ])
    } else {
      await sendWhatsApp(phone, 'اكتب  *٢*  للمتابعة من حيث توقفت.')
    }
    return
  }

if (session.step === 8) {
  if (text !== '__IMAGE__') {
    await sendWhatsApp(phone, 'يرجى إرسال صورة واضحة لبطاقة إثبات الشخصية.')
    return
  }

  const mediaId  = message.image?.id
  const mediaUrl = message.image?.url

  if (!mediaId || !mediaUrl) {
    await sendWhatsApp(phone, 'لم نتمكن من استلام الصورة. يرجى المحاولة مرة أخرى.')
    return
  }

  // Let user know we're processing
  await sendWhatsApp(phone, 'جارٍ التحقق من الصورة...')

  // Download image
  const media = await downloadMedia(mediaId, mediaUrl)
  if (!media) {
    await sendWhatsApp(phone, 'تعذر تحميل الصورة. يرجى إرسالها مرة أخرى.')
    return
  }

  // Verify with Claude
  const result = await verifyNationalId(media.base64, media.mimeType)

  if (!result.is_valid_id) {
    await sendWhatsApp(phone,
      `❌ لم نتمكن من التحقق من الصورة.\n${result.reason || 'يرجى إرسال صورة واضحة لبطاقة إثبات الشخصية.'}\n\nأرسل الصورة مرة أخرى.`
    )
    return
  }

 // Valid ID — upload to Firebase Storage
const photoUrl = await uploadIdPhoto(media.base64, media.mimeType, phone)

session.data.q8  = photoUrl || mediaId   // URL if uploaded, fallback to mediaId
session.data.q7  = result.id_number || session.data.q7 || ''
session.last_activity = Date.now()
session.step = 9

const confirmMsg = result.id_number
  ? `✅ تم التحقق من الهوية بنجاح.\nرقم الهوية: ${result.id_number}`
  : `✅ تم التحقق من الهوية بنجاح.`

await sendWhatsApp(phone, confirmMsg)
await Promise.all([
  saveSession(phone, session),
  sendWhatsApp(phone, getQuestion(9, session.data))
])
return
}
  // ── Normalize Arabic numerals for all inputs ─────────────────────────────────
  const normalizedText = text
    .replace(/[٠-٩]/g, d => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)))
    .replace(/،/g, ',')

  // ── Validate ─────────────────────────────────────────────────────────────────
  const error = validateAnswer(session.step, normalizedText, session.data)
  if (error) {
    await sendWhatsApp(phone, error)
    return
  }

  session.data[`q${session.step}`] = normalizedText
  session.last_activity = Date.now()
  const nextStep = getNextStep(session.step, normalizedText, session.data)

  // ── Completed ────────────────────────────────────────────────────────────────
  if (nextStep > TOTAL_STEPS) {
    const row = buildRow(phone, session.data)

    await Promise.all([
      saveToSheets(row),
      saveToFirestore(phone, row),
      saveSession(phone, { completed: true, step: TOTAL_STEPS, started: true, greeted: true, data: {} })
    ])

    await sendWhatsApp(phone,
      `تم التسجيل بنجاح ✓\n────────────────────────\nشكراً لك. سيتواصل معك فريقنا قريباً.\n\nنتمنى لك موسماً زراعياً موفقاً.`
    )
    return
  }

  // ── Next question ─────────────────────────────────────────────────────────────
  session.step = nextStep
  await Promise.all([
    saveSession(phone, session),
    sendWhatsApp(phone, getQuestion(nextStep, session.data))
  ])
}
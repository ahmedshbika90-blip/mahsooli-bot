export function validateAnswer(step, text, data = {}) {
  const t = text.trim()

  switch (step) {

    // Q1: Full 4-part name
    case 1: {
      const parts = t.split(/\s+/).filter(Boolean)
      if (parts.length < 3) return '❌ يرجى إدخال الاسم الرباعي كاملاً (٣ أجزاء على الأقل).\nمثال: أحمد محمد إبراهيم إسماعيل'
      if (/\d/.test(t)) return '❌ يجب ألا يحتوي الاسم على أرقام.'
      return null
    }

    // Q2: DOB
    case 2: {
      const normalized = t
        .replace(/[٠-٩]/g, d => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)))
        .replace(/[.\-،]/g, '/')
        .replace(/\s+/g, '')
      const parts = normalized.split('/')
      if (parts.length !== 3) return '❌ صيغة غير صحيحة.\nمثال: ١٥/٠٦/١٩٨٥'
      const [d, m, y] = parts.map(Number)
      if (isNaN(d) || isNaN(m) || isNaN(y)) return '❌ يرجى إدخال أرقام صحيحة.\nمثال: ١٥/٠٦/١٩٨٥'
      if (y < 1920 || y > 2010) return '❌ السنة يجب أن تكون بين ١٩٢٠ و٢٠١٠.'
      if (m < 1 || m > 12) return '❌ الشهر يجب أن يكون بين ١ و١٢.'
      if (d < 1 || d > 31) return '❌ اليوم يجب أن يكون بين ١ و٣١.'
      return null
    }

    // Q3: Gender
    case 3:
      if (!['1','2'].includes(t)) return '❌ يرجى الاختيار:\n١ — ذكر\n٢ — أنثى'
      return null

    // Q4: Primary phone
    case 4: {
      const normalized = t.replace(/[٠-٩]/g, d => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)))
      const digits = normalized.replace(/\D/g, '')
      if (digits.length !== 10) return '❌ رقم الهاتف يجب أن يكون ١٠ أرقام.\nمثال: ٠٩١٢٣٤٥٦٧٨'
      if (!digits.startsWith('0')) return '❌ يجب أن يبدأ الرقم بـ ٠.\nمثال: ٠٩١٢٣٤٥٦٧٨'
      return null
    }

    // Q5: Secondary phone (optional)
    case 5: {
      if (['لا يوجد','لايوجد','-'].includes(t)) return null
      const normalized = t.replace(/[٠-٩]/g, d => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)))
      const digits = normalized.replace(/\D/g, '')
      if (digits.length !== 10) return '❌ رقم الهاتف يجب أن يكون ١٠ أرقام.\nأو اكتب: لا يوجد'
      if (!digits.startsWith('0')) return '❌ يجب أن يبدأ الرقم بـ ٠.'
      return null
    }

    // Q6: Has ID?
    case 6:
      if (!['1','2'].includes(t)) return '❌ يرجى الاختيار:\n١ — نعم\n٢ — لا'
      return null

    // Q7: ID number
    case 7: {
      const clean = t
        .replace(/[٠-٩]/g, d => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)))
        .replace(/[-\s]/g, '')
      if (clean.length !== 11) return '❌ رقم البطاقة يجب أن يكون ١١ رقماً بالضبط.'
      if (!/^\d+$/.test(clean)) return '❌ يجب أن يحتوي على أرقام فقط.'
      return null
    }

    // Q8: ID photo — handled in webhook (image type check)
    case 8: return null

    // Q9: State
    case 9: {
      const valid = Array.from({length:18}, (_,i) => String(i+1))
      if (!valid.includes(t))
        return '❌ يرجى اختيار رقم الولاية:\n١ — الخرطوم\n٢ — الجزيرة\n٣ — سنار\n٤ — النيل الأبيض\n٥ — النيل الأزرق\n٦ — شمال كردفان\n٧ — جنوب كردفان\n٨ — غرب كردفان\n٩ — شمال دارفور\n١٠ — جنوب دارفور\n١١ — شرق دارفور\n١٢ — غرب دارفور\n١٣ — وسط دارفور\n١٤ — كسلا\n١٥ — البحر الأحمر\n١٦ — القضارف\n١٧ — نهر النيل\n١٨ — الشمالية'
      return null
    }

    // Q10: Locality (dynamic per state)
    case 10: {
      const localities = getLocalities(data.q9 || '')
      const valid = Array.from({length: localities.length}, (_,i) => String(i+1))
      if (!valid.includes(t)) {
        const list = localities.map((l,i) => `${i+1} — ${l}`).join('\n')
        return `❌ يرجى اختيار رقم المحلية:\n${list}`
      }
      return null
    }

    // Q11: Education
    case 11:
      if (!['1','2','3','4','5','6','7','8'].includes(t))
        return '❌ يرجى اختيار رقم المستوى:\n١ — لا يوجد\n٢ — خلوة (يقرأ ويكتب)\n٣ — مرحلة أساسية\n٤ — مرحلة ثانوية\n٥ — دبلوم\n٦ — بكالوريوس\n٧ — ماجستير\n٨ — دكتوراه'
      return null

    // Q12: Smartphone
    case 12:
      if (!['1','2'].includes(t)) return '❌ يرجى الاختيار:\n١ — نعم\n٢ — لا'
      return null

    // Q13: Network coverage
    case 13:
      if (!['1','2'].includes(t)) return '❌ يرجى الاختيار:\n١ — نعم\n٢ — لا'
      return null

    // Q14: Best network
    case 14:
      if (!['1','2','3'].includes(t))
        return '❌ يرجى الاختيار:\n١ — زين\n٢ — سوداني\n٣ — MTN'
      return null

    // Q15: Has bank?
    case 15:
      if (!['1','2'].includes(t)) return '❌ يرجى الاختيار:\n١ — نعم\n٢ — لا'
      return null

    // Q16: Which banks
    case 16: {
      const parts = t.split(/[,،\s]+/).map(s => s.trim()).filter(Boolean)
      if (!parts.length || !parts.every(p => ['1','2','3','4','5','6','7','8'].includes(p)))
        return '❌ يرجى اختيار الأرقام:\n١ — بنك الخرطوم\n٢ — بنك أمدرمان الوطني\n٣ — البنك الزراعي السوداني\n٤ — بنك فيصل الإسلامي\n٥ — بنك النيل\n٦ — بنك النيلين\n٧ — مصرف المزارع\n٨ — أخرى\n\nأكثر من اختيار: مثال ١,٣'
      return null
    }

    // Q17: Banking apps
    case 17: {
      const parts = t.split(/[,،\s]+/).map(s => s.trim()).filter(Boolean)
      if (!parts.length || !parts.every(p => ['1','2','3','4','5','6','7','8'].includes(p)))
        return '❌ يرجى اختيار الأرقام:\n١ — بنكك (الخرطوم)\n٢ — اوكاش (أمدرمان)\n٣ — مصرفك (المزارع)\n٤ — الزراعي موبايل\n٥ — فوري (فيصل)\n٦ — ساهل (النيل)\n٧ — من مكانك (النيلين)\n٨ — لا أستخدم تطبيقاً\n\nأكثر من اختيار: مثال ١,٣'
      return null
    }

    // Q18: Other bank name (free text)
    case 18:
      if (t.length < 2) return '❌ يرجى ذكر اسم البنك.'
      return null

    // Q19: Union member?
    case 19:
      if (!['1','2'].includes(t)) return '❌ يرجى الاختيار:\n١ — نعم\n٢ — لا'
      return null

    // Q20: Union name
    case 20:
      if (t.length < 2) return '❌ يرجى إدخال اسم الاتحاد أو الجمعية.'
      return null

    // Q21: Farm size
    case 21: {
      const norm = t.replace(/[٠-٩]/g, d => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)))
      const num = parseFloat(norm.replace(/[^\d.]/g, ''))
      if (isNaN(num) || num <= 0) return '❌ يرجى إدخال المساحة بالأرقام.\nمثال: ٥٠'
      if (num > 10000) return '❌ المساحة كبيرة جداً. يرجى التحقق.'
      return null
    }

    // Q22: Owned/rented
    case 22:
      if (!['1','2'].includes(t)) return '❌ يرجى الاختيار:\n١ — مملوكة\n٢ — مستأجرة'
      return null

    // Q23: Rent tenure
    case 23:
      if (!['1','2','3','4'].includes(t))
        return '❌ يرجى اختيار مدة الإيجار:\n١ — موسم واحد\n٢ — موسمان\n٣ — من ٣ إلى ٥ مواسم\n٤ — أكثر من ٥ مواسم'
      return null

    // Q24: Ownership docs
    case 24:
      if (!['1','2'].includes(t)) return '❌ يرجى الاختيار:\n١ — نعم\n٢ — لا'
      return null

    // Q25: Has guarantees?
    case 25:
      if (!['1','2'].includes(t)) return '❌ يرجى الاختيار:\n١ — نعم\n٢ — لا'
      return null

    // Q26: Guarantee types
    case 26: {
      const parts = t.split(/[,،\s]+/).map(s => s.trim()).filter(Boolean)
      if (!parts.length || !parts.every(p => ['1','2','3','4'].includes(p)))
        return '❌ يرجى اختيار الأرقام:\n١ — شيك\n٢ — معدات\n٣ — أرض\n٤ — أخرى\n\nأكثر من اختيار: مثال ١,٣'
      return null
    }

    // Q27: Other guarantee
    case 27:
      if (t.length < 2) return '❌ يرجى تحديد نوع الضمان.'
      return null

    // Q28: Crops last 3 seasons
    case 28: {
      const parts = t.split(/[,،\s]+/).map(s => s.trim()).filter(Boolean)
      if (!parts.length || !parts.every(p => ['1','2','3','4','5','6','7'].includes(p)))
        return '❌ يرجى اختيار الأرقام:\n١ — سمسم\n٢ — ذرة رفيعة\n٣ — فول سوداني\n٤ — قطن\n٥ — حب بطيخ\n٦ — دخن\n٧ — عباد الشمس\n\nأكثر من اختيار: مثال ١,٢,٣'
      return null
    }

    // Q29-35: Yield per crop (free number)
    case 29:
    case 30:
    case 31:
    case 32:
    case 33:
    case 34:
    case 35: {
      const norm = t.replace(/[٠-٩]/g, d => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)))
      const num = parseFloat(norm.replace(/[^\d.]/g, ''))
      if (isNaN(num) || num < 0) return '❌ يرجى إدخال رقم صحيح.\nمثال: ٥٠'
      return null
    }

    // Q36: Finance source
    case 36:
      if (!['1','2','3','4','5'].includes(t))
        return '❌ يرجى اختيار طريقة التمويل:\n١ — بنك\n٢ — تمويل ذاتي\n٣ — ائتمان تاجر\n٤ — منظمة\n٥ — أخرى'
      return null

    // Q37: Other finance source
    case 37:
      if (t.length < 2) return '❌ يرجى توضيح طريقة التمويل.'
      return null

    // Q38: Finance amount
    case 38: {
  const norm = t.replace(/[٠-٩]/g, d => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)))
  const num = parseFloat(norm.replace(/,/g, '').replace(/[^\d]/g, ''))
  if (isNaN(num) || num <= 0) return '❌ يرجى إدخال المبلغ بالأرقام.\nمثال: ١,٥٠٠,٠٠٠'
  if (num >= 1000 && !t.includes(',') && !t.includes('،'))
    return '❌ يرجى إضافة الفاصلة للأرقام الكبيرة.\nمثال: ١,٥٠٠,٠٠٠ وليس ١٥٠٠٠٠٠'
  return null
}
    // Q39: Repaid?
    case 39:
      if (!['1','2'].includes(t)) return '❌ يرجى الاختيار:\n١ — نعم\n٢ — لا'
      return null

    // Q40: Why not repaid
    case 40:
      if (!['1','2','3','4'].includes(t))
        return '❌ يرجى اختيار السبب:\n١ — انخفاض الإنتاج\n٢ — ارتفاع تكاليف المدخلات\n٣ — لا يوجد إنتاج\n٤ — أسباب أخرى'
      return null

    // Q41: Other repay reason
    case 41:
      if (t.length < 2) return '❌ يرجى توضيح السبب.'
      return null

    // Q42: Finance use
    case 42: {
      const parts = t.split(/[,،\s]+/).map(s => s.trim()).filter(Boolean)
      if (!parts.length || !parts.every(p => ['1','2','3','4','5','6'].includes(p)))
        return '❌ يرجى اختيار الأرقام:\n١ — بذور\n٢ — سماد\n٣ — مبيدات\n٤ — إيجار آلات\n٥ — وقود\n٦ — حصاد\n\nأكثر من اختيار: مثال ١,٢'
      return null
    }

    // Q43: Which bank financed
    case 43:
      if (!['1','2','3','4','5','6','7','8'].includes(t))
        return '❌ يرجى اختيار البنك:\n١ — بنك الخرطوم\n٢ — بنك أمدرمان الوطني\n٣ — البنك الزراعي السوداني\n٤ — بنك فيصل الإسلامي\n٥ — بنك النيل\n٦ — بنك النيلين\n٧ — مصرف المزارع\n٨ — أخرى'
      return null

    // Q44: Other bank name
    case 44:
      if (t.length < 2) return '❌ يرجى ذكر اسم البنك.'
      return null

    // Q45: Preferred crops this season
    case 45: {
      const parts = t.split(/[,،\s]+/).map(s => s.trim()).filter(Boolean)
      if (!parts.length || !parts.every(p => ['1','2','3','4','5','6','7'].includes(p)))
        return '❌ يرجى اختيار الأرقام:\n١ — سمسم\n٢ — ذرة رفيعة\n٣ — فول سوداني\n٤ — قطن\n٥ — حب بطيخ\n٦ — دخن\n٧ — عباد الشمس\n\nأكثر من اختيار: مثال ١,٣'
      return null
    }

    // Q46: Why preferred (choices)
    case 46: {
      const parts = t.split(/[,،\s]+/).map(s => s.trim()).filter(Boolean)
      if (!parts.length || !parts.every(p => ['1','2','3','4','5','6','7','8','9'].includes(p)))
        return '❌ يرجى اختيار الأرقام:\n١ — سعر أفضل في السوق\n٢ — طلب محلي مرتفع\n٣ — محصول مألوف\n٤ — مناسب للتربة\n٥ — مخاطر أقل\n٦ — إمكانية التخزين\n٧ — توافر المدخلات\n٨ — بناءً على نصيحة متخصص\n٩ — أخرى\n\nأكثر من اختيار: مثال ١,٤'
      return null
    }

    // Q47: Other crop reason
    case 47:
      if (t.length < 2) return '❌ يرجى توضيح السبب.'
      return null

    // Q48: Finance crop (one only)
    case 48:
      if (!['1','2','3','4','5','6','7'].includes(t))
        return '❌ يرجى اختيار محصول واحد:\n١ — سمسم\n٢ — ذرة رفيعة\n٣ — فول سوداني\n٤ — قطن\n٥ — حب بطيخ\n٦ — دخن\n٧ — عباد الشمس'
      return null

    // Q49: Seed variety (dynamic per crop)
    case 49: {
      const varieties = getVarieties(data.q48 || '')
      if (!varieties.length) return null
      const valid = Array.from({length: varieties.length}, (_,i) => String(i+1))
      if (!valid.includes(t)) {
        const list = varieties.map((v,i) => `${i+1} — ${v}`).join('\n')
        return `❌ يرجى اختيار رقم الصنف:\n${list}`
      }
      return null
    }

    // Q50: Other variety
    case 50:
      if (t.length < 2) return '❌ يرجى ذكر اسم الصنف.'
      return null

    // Q51: Use fertilizer?
    case 51:
      if (!['1','2'].includes(t)) return '❌ يرجى الاختيار:\n١ — نعم\n٢ — لا'
      return null

    // Q52: Why no fertilizer
    case 52: {
      const parts = t.split(/[,،\s]+/).map(s => s.trim()).filter(Boolean)
      if (!parts.length || !parts.every(p => ['1','2','3','4','5'].includes(p)))
        return '❌ يرجى اختيار الأرقام:\n١ — التكلفة عالية\n٢ — غير متاح في المنطقة\n٣ — المحصول لا يحتاجه\n٤ — تجربة سلبية سابقة\n٥ — أخرى\n\nأكثر من اختيار: مثال ١,٢'
      return null
    }

    // Q53: Other no-fertilizer reason
    case 53:
      if (t.length < 2) return '❌ يرجى توضيح السبب.'
      return null

    // Q54: Use pesticides?
    case 54:
      if (!['1','2'].includes(t)) return '❌ يرجى الاختيار:\n١ — نعم\n٢ — لا'
      return null

    // Q55: Why no pesticides
    case 55: {
      const parts = t.split(/[,،\s]+/).map(s => s.trim()).filter(Boolean)
      if (!parts.length || !parts.every(p => ['1','2','3','4','5'].includes(p)))
        return '❌ يرجى اختيار الأرقام:\n١ — التكلفة عالية\n٢ — غير متاح في المنطقة\n٣ — المحصول لا يحتاجه\n٤ — تجربة سلبية سابقة\n٥ — أخرى\n\nأكثر من اختيار: مثال ١,٢'
      return null
    }

    // Q56: Other no-pesticides reason
    case 56:
      if (t.length < 2) return '❌ يرجى توضيح السبب.'
      return null

    // Q57: Requested amount
  case 57: {
  const norm = t.replace(/[٠-٩]/g, d => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)))
  const num = parseFloat(norm.replace(/,/g, '').replace(/[^\d]/g, ''))
  if (isNaN(num) || num <= 0) return '❌ يرجى إدخال المبلغ بالأرقام.\nمثال: ١,٥٠٠,٠٠٠'
  if (num >= 1000 && !t.includes(',') && !t.includes('،'))
    return '❌ يرجى إضافة الفاصلة للأرقام الكبيرة.\nمثال: ١,٥٠٠,٠٠٠ وليس ١٥٠٠٠٠٠'
  return null
}
    // Q58: Marital status
    case 58:
      if (!['1','2','3','4'].includes(t))
        return '❌ يرجى اختيار الحالة الاجتماعية:\n١ — أعزب\n٢ — متزوج\n٣ — أرمل\n٤ — مطلق'
      return null

    // Q59: Wives
    case 59: {
      const num = parseInt(t.replace(/[٠-٩]/g, d => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d))))
      if (isNaN(num) || num < 1 || num > 4) return '❌ يرجى إدخال عدد الزوجات (من ١ إلى ٤).'
      return null
    }

    // Q60: Has children?
    case 60:
      if (!['1','2'].includes(t)) return '❌ يرجى الاختيار:\n١ — نعم\n٢ — لا'
      return null

    // Q61: Total children
    case 61: {
      const num = parseInt(t.replace(/[٠-٩]/g, d => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d))))
      if (isNaN(num) || num < 0) return '❌ يرجى إدخال عدد الأطفال.'
      return null
    }

    // Q62: Children under 18
    case 62: {
      const num = parseInt(t.replace(/[٠-٩]/g, d => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d))))
      if (isNaN(num) || num < 0) return '❌ يرجى إدخال عدد الأطفال دون سن ١٨.'
      return null
    }

    // Q63: Other dependents?
    case 63:
      if (!['1','2'].includes(t)) return '❌ يرجى الاختيار:\n١ — نعم\n٢ — لا'
      return null

    // Q64: Dependents count
    case 64: {
      const num = parseInt(t.replace(/[٠-٩]/g, d => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d))))
      if (isNaN(num) || num < 1) return '❌ يرجى إدخال عدد المعالين.'
      return null
    }

    // Q65: Other income?
    case 65:
      if (!['1','2'].includes(t)) return '❌ يرجى الاختيار:\n١ — نعم\n٢ — لا'
      return null

    // Q66: Income sources
    case 66: {
      const parts = t.split(/[,،\s]+/).map(s => s.trim()).filter(Boolean)
      if (!parts.length || !parts.every(p => ['1','2','3','4','5','6','7','8','9','10'].includes(p)))
        return '❌ يرجى اختيار الأرقام:\n١ — وظيفة رسمية\n٢ — تجارة\n٣ — العمل بالأجر اليومي\n٤ — خدمات نقل وترحيل\n٥ — المعاش\n٦ — حرف يدوية\n٧ — إيجار الأراضي أو المعدات\n٨ — رعي\n٩ — حوالات\n١٠ — دعم نقدي من منظمات\n\nأكثر من اختيار: مثال ١,٤'
      return null
    }

    // Q67: Remittances amount (optional)
    case 67: return null

    // Q68: Consent
    case 68:
      if (t !== '1') return '❌ يرجى كتابة ١ للإقرار والموافقة.'
      return null

    default: return null
  }
}

// ─── Localities per state ─────────────────────────────────────────────────────
export function getLocalities(stateNum) {
  const map = {
    '1':  ['الخرطوم','بحري','أم درمان','أمبدة','كرري','شرق النيل','جبل أولياء'],
    '2':  ['مدني','جنوب الجزيرة','شرق الجزيرة','أم القرى','الحصاحيصا','الكاملين','المناقل','القرشي'],
    '3':  ['سنجة','سنار','السوكي','الدندر','أبو حجار','شرق سنار','الدالي والمزموم'],
    '4':  ['ربك','كوستي','الدويم','القطينة','الجبلين','السلام','أم رمته','تندلتي'],
    '5':  ['الدمازين','الروصيرص','الكرمك','باو','قيسان','ود الماحي','التضامن'],
    '6':  ['الأبيض','بارا','الرهد','أم روابة','شيكان','غبيش','وادي الباشا','الخوي'],
    '7':  ['كادقلي','الدلنج','أبو جبيهة','العباسية','لقاوة','هيبان','رشاد','تلودي'],
    '8':  ['الفولة','النهود','أبو زبد','بابنوسة','الوحدة'],
    '9':  ['الفاشر','كبكابية','كتم','الطويشة','مليط','أم كدادة','الواحة'],
    '10': ['نيالا','كاس','الضعين','رهيد البردي','دمسو','بليل','إد الغنم'],
    '11': ['الضعين','أبو كارنكا','يابس','الفردوس','أسلاية'],
    '12': ['الجنينة','كرينك','هبيلة','بيضة','فور برنقا','سربا'],
    '13': ['زالنجي','وادي صالح','أزم','نيرتتي','روكورو'],
    '14': ['كسلا','حلفا الجديدة','ريفي كسلا','غرب كسلا','أروما','خشم القربة','ود الحليو','همشكوريب','تلكوك','نهر عطبرة','ريفي ود الحليو'],
    '15': ['بورتسودان','سواكن','سنكات','طوكر','هيا','درديب','عقيق','القنب والأوليب','حلايب','جبيت المعادن'],
    '16': ['القضارف','وسط القضارف','الفاو','الرهد','القريشة','القلابات الشرقية','القلابات الغربية','الفشقة','المفازة','البطانة','باسندة','قلع النحل'],
    '17': ['الدامر','عطبرة','شندي','المتمة','بربر','أبو حمد','البحيرة'],
    '18': ['دنقلا','مروي','الدبة','القولد','البرقيق','دلقو','حلفا'],
  }
  return map[stateNum] || []
}

// ─── Varieties per crop ───────────────────────────────────────────────────────
export function getVarieties(cropNum) {
  const map = {
    '1': ['برومو','أم شجرة','جزولي','قضارف ١','أخرى'],                                      // sesame
    '2': ['ود أحمد','أرفع قدمك','دهب','طابت','فتريتة','بطانة','ود باكو','مُقد','حريري','عكر','أخرى'], // sorghum
    '3': ['غبيش','أحمدي','توزي','سودري','أخرى'],                                             // groundnut
    '4': ['الصيني ١','البرازيلي RR','أخرى'],                                                  // cotton
    '5': [],                                                                                   // watermelon - no varieties
    '6': ['عشانا','عزيز','فارس','بيوضة','أخرى'],                                              // millet
    '7': ['هاي صن ٣٣','SY','سيرينا','أخرى'],                                                  // sunflower
  }
  return map[cropNum] || []
}
export function validateAnswer(step, text) {
  const t = text.trim()

  switch (step) {

    // Q1: Full name (first + second + third combined)
    case 1: {
      const parts = t.split(/\s+/).filter(Boolean)
      if (parts.length < 2) return '❌ يرجى إدخال الاسم الكامل (الاسم الأول والثاني على الأقل).\nمثال: أحمد عبدالله إبراهيم'
      if (/\d/.test(t)) return '❌ يجب ألا يحتوي الاسم على أرقام.'
      return null
    }

    // Q2: Last name
    case 2:
      if (t.length < 2) return '❌ يرجى إدخال اسم العائلة.'
      if (/\d/.test(t)) return '❌ يجب ألا يحتوي الاسم على أرقام.'
      return null

    // Q3: Date of birth DD/MM/YYYY
    case 3: {
      const normalized = t
        .replace(/[٠-٩]/g, d => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)))
        .replace(/[.-]/g, '/')
      const parts = normalized.split('/')
      if (parts.length !== 3) return '❌ صيغة غير صحيحة.\nيرجى الإدخال هكذا: DD/MM/YYYY\nمثال: 15/05/1990'
      const [d, m, y] = parts.map(Number)
      if (isNaN(d) || isNaN(m) || isNaN(y)) return '❌ يرجى إدخال أرقام صحيحة.\nمثال: 15/05/1990'
      if (y < 1920 || y > 2010) return '❌ السنة يجب أن تكون بين 1920 و2010.'
      if (m < 1 || m > 12) return '❌ الشهر يجب أن يكون بين 1 و12.'
      if (d < 1 || d > 31) return '❌ اليوم يجب أن يكون بين 1 و31.'
      return null
    }

    // Q4: Gender
    case 4: {
      if (!['ذكر','أنثى','1','2'].includes(t))
        return '❌ يرجى الاختيار:\n1 - ذكر\n2 - أنثى'
      return null
    }

    // Q5: Primary phone
    case 5: {
      const digits = t.replace(/\D/g, '')
      if (digits.length !== 10) return '❌ رقم الهاتف يجب أن يكون 10 أرقام.'
      if (!digits.startsWith('0')) return '❌ يجب أن يبدأ الرقم بـ 0.\nمثال: 0912345678'
      return null
    }

    // Q6: Secondary phone (optional)
    case 6: {
      if (['لا يوجد','-','skip','لا'].includes(t.toLowerCase())) return null
      const digits = t.replace(/\D/g, '')
      if (digits.length !== 10) return '❌ رقم الهاتف يجب أن يكون 10 أرقام.\nإذا لم يكن لديك رقم ثانٍ اكتب: لا يوجد'
      if (!digits.startsWith('0')) return '❌ يجب أن يبدأ الرقم بـ 0.'
      return null
    }

    // Q7: Has national ID
    case 7:
      if (!['نعم','لا','1','2'].includes(t))
        return '❌ يرجى الاختيار:\n1 - نعم\n2 - لا'
      return null

    // Q8: National ID number
    case 8: {
      const clean = t.replace(/[-\s]/g, '')
        .replace(/[٠-٩]/g, d => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)))
      if (clean.length !== 11) return '❌ رقم الهوية يجب أن يكون 11 رقماً بالضبط.'
      if (!/^\d+$/.test(clean)) return '❌ رقم الهوية يجب أن يحتوي على أرقام فقط.'
      return null
    }

    // Q9: State
    case 9: {
      const nums = Array.from({length:18}, (_,i) => String(i+1))
      if (!nums.includes(t))
        return '❌ يرجى اختيار رقم الولاية:\n1. الخرطوم\n2. الجزيرة\n3. سنار\n4. النيل الأبيض\n5. النيل الأزرق\n6. شمال كردفان\n7. جنوب كردفان\n8. غرب كردفان\n9. شمال دارفور\n10. جنوب دارفور\n11. شرق دارفور\n12. غرب دارفور\n13. وسط دارفور\n14. كسلا\n15. البحر الأحمر\n16. القضارف\n17. نهر النيل\n18. الشمالية'
      return null
    }

    // Q10: Locality
    case 10:
      if (t.length < 2) return '❌ يرجى إدخال اسم المحلية.'
      return null

    // Q11: Education
    case 11:
      if (!['1','2','3','4','5','6','7','8'].includes(t))
        return '❌ يرجى اختيار رقم المستوى التعليمي:\n1. لا يوجد\n2. خلوة (يقرأ ويكتب)\n3. مرحلة أساسية\n4. مرحلة ثانوية\n5. دبلوم\n6. بكالوريوس\n7. ماجستير\n8. دكتوراه'
      return null

    // Q12: Smartphone
    case 12:
      if (!['نعم','لا','1','2'].includes(t))
        return '❌ يرجى الاختيار:\n1 - نعم\n2 - لا'
      return null

    // Q13: Network coverage
    case 13:
      if (!['نعم','لا','1','2'].includes(t))
        return '❌ يرجى الاختيار:\n1 - نعم\n2 - لا'
      return null

    // Q14: Best network
    case 14:
      if (!['زين','سوداني','mtn','MTN','1','2','3'].includes(t))
        return '❌ يرجى الاختيار:\n1 - زين\n2 - سوداني\n3 - MTN'
      return null

    // Q15: Bank account
    case 15:
      if (!['نعم','لا','1','2'].includes(t))
        return '❌ يرجى الاختيار:\n1 - نعم\n2 - لا'
      return null

    // Q16: Which banks
    case 16: {
      const parts = t.split(/[,،\s]+/).map(s => s.trim()).filter(Boolean)
      if (!parts.length || !parts.every(p => ['1','2','3','4','5','6','7'].includes(p)))
        return '❌ يرجى اختيار الأرقام:\n1. بنك الخرطوم\n2. بنك فيصل الإسلامي\n3. بنك النيل\n4. SAB\n5. بنك أمدرمان الوطني\n6. بنك النيلين\n7. أخرى\n\nمثال: 1 أو 1,3'
      return null
    }

    // Q17: Banking apps
    case 17: {
      const parts = t.split(/[,،\s]+/).map(s => s.trim()).filter(Boolean)
      if (!parts.length || !parts.every(p => ['1','2','3','4','5','6','7'].includes(p)))
        return '❌ يرجى اختيار الأرقام:\n1. تطبيق بنك الخرطوم\n2. تطبيق بنك فيصل\n3. تطبيق بنك النيل\n4. تطبيق SAB\n5. تطبيق ONB\n6. تطبيق بنك النيلين\n7. لا أستخدم تطبيقاً\n\nمثال: 1 أو 1,3'
      return null
    }

    // Q18: Union member
    case 18:
      if (!['نعم','لا','1','2'].includes(t))
        return '❌ يرجى الاختيار:\n1 - نعم\n2 - لا'
      return null

    // Q19: Union name
    case 19:
      if (t.length < 2) return '❌ يرجى إدخال اسم الاتحاد أو الجمعية.'
      return null

    // Q20: Farm size
    case 20: {
      const normalized = t.replace(/[٠-٩]/g, d => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)))
      const num = parseFloat(normalized.replace(/[^\d.]/g, ''))
      if (isNaN(num) || num <= 0) return '❌ يرجى إدخال مساحة الأرض بالأرقام.\nمثال: 25 أو 7.5'
      if (num > 10000) return '❌ المساحة كبيرة جداً. يرجى التحقق من الرقم.'
      return null
    }

    // Q21: Owned or rented
    case 21:
      if (!['مملوكة','مستأجرة','1','2'].includes(t))
        return '❌ يرجى الاختيار:\n1 - مملوكة\n2 - مستأجرة'
      return null

    // Q22: Rent amount
    case 22: {
      const normalized = t.replace(/[٠-٩]/g, d => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)))
      const num = parseFloat(normalized.replace(/[^\d.]/g, ''))
      if (isNaN(num) || num <= 0) return '❌ يرجى إدخال مبلغ الإيجار بالأرقام.\nمثال: 500000'
      return null
    }

    // Q23: Ownership docs
    case 23:
      if (!['نعم','لا','1','2'].includes(t))
        return '❌ يرجى الاختيار:\n1 - نعم\n2 - لا'
      return null

    // Q24: Has guarantees
    case 24:
      if (!['نعم','لا','1','2'].includes(t))
        return '❌ يرجى الاختيار:\n1 - نعم\n2 - لا'
      return null

    // Q25: Guarantee types
    case 25: {
      const parts = t.split(/[,،\s]+/).map(s => s.trim()).filter(Boolean)
      if (!parts.length || !parts.every(p => ['1','2','3','4'].includes(p)))
        return '❌ يرجى اختيار الأرقام:\n1. شيك\n2. معدات\n3. أرض\n4. أخرى\n\nمثال: 3 أو 1,3'
      return null
    }

    // Q26: Other guarantee
    case 26:
      if (t.length < 2) return '❌ يرجى تحديد نوع الضمان.'
      return null

    // Q27: Crops last 3 seasons
    case 27: {
      const parts = t.split(/[,،\s]+/).map(s => s.trim()).filter(Boolean)
      if (!parts.length || !parts.every(p => ['1','2','3','4','5','6','7'].includes(p)))
        return '❌ يرجى اختيار الأرقام:\n1. سمسم\n2. ذرة رفيعة\n3. فول سوداني\n4. قطن\n5. بذرة بطيخ\n6. دخن\n7. عباد الشمس\n\nمثال: 1,2,3'
      return null
    }

    // Q28-34: Yield per crop (1 to 4 in 0.5 steps or لا يوجد)
    case 28:
    case 29:
    case 30:
    case 31:
    case 32:
    case 33:
    case 34: {
      const noYield = ['لا يوجد','لايوجد','na','NA','لا']
      if (noYield.includes(t.toLowerCase()) || noYield.includes(t)) return null
      const normalized = t.replace(/[٠-٩]/g, d => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)))
      const num = parseFloat(normalized)
      const valid = [1, 1.5, 2, 2.5, 3, 3.5, 4]
      if (!valid.includes(num))
        return '❌ يرجى اختيار قيمة من القائمة:\n1 — 1.5 — 2 — 2.5 — 3 — 3.5 — 4\n\nأو اكتب: لا يوجد (إذا لم تزرع هذا المحصول)'
      return null
    }

    // Q35: Finance source
    case 35:
      if (!['1','2','3','4','5'].includes(t))
        return '❌ يرجى اختيار طريقة التمويل:\n1. بنك\n2. تمويل ذاتي\n3. ائتمان تاجر\n4. منظمة\n5. أخرى'
      return null

    // Q36: Finance amount
    case 36: {
      const normalized = t.replace(/[٠-٩]/g, d => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)))
      const num = parseFloat(normalized.replace(/[^\d.]/g, ''))
      if (isNaN(num) || num <= 0) return '❌ يرجى إدخال مبلغ التمويل بالأرقام.\nمثال: 5000000'
      return null
    }

    // Q37: Repaid
    case 37:
      if (!['نعم','لا','1','2'].includes(t))
        return '❌ يرجى الاختيار:\n1 - نعم\n2 - لا'
      return null

    // Q38: Why not repaid
    case 38:
      if (!['1','2','3','4'].includes(t))
        return '❌ يرجى اختيار السبب:\n1. إنتاج منخفض\n2. تكلفة مدخلات عالية\n3. لا يوجد إنتاج\n4. أخرى'
      return null

    // Q39: Finance use
    case 39: {
      const parts = t.split(/[,،\s]+/).map(s => s.trim()).filter(Boolean)
      if (!parts.length || !parts.every(p => ['1','2','3','4','5','6'].includes(p)))
        return '❌ يرجى اختيار الأرقام:\n1. بذور\n2. سماد\n3. مبيدات\n4. إيجار آلات\n5. وقود\n6. حصاد\n\nمثال: 1,2'
      return null
    }

    // Q40: Finance bank
    case 40:
      if (!['1','2','3','4','5','6','7'].includes(t))
        return '❌ يرجى اختيار البنك:\n1. بنك الخرطوم\n2. بنك فيصل الإسلامي\n3. بنك النيل\n4. SAB\n5. بنك أمدرمان الوطني\n6. بنك النيلين\n7. أخرى'
      return null

    // Q41: Preferred crops
    case 41: {
      const parts = t.split(/[,،\s]+/).map(s => s.trim()).filter(Boolean)
      if (!parts.length || !parts.every(p => ['1','2','3','4','5','6','7'].includes(p)))
        return '❌ يرجى اختيار الأرقام:\n1. سمسم\n2. ذرة رفيعة\n3. فول سوداني\n4. قطن\n5. بذرة بطيخ\n6. دخن\n7. عباد الشمس\n\nمثال: 1,3'
      return null
    }

    // Q42: Why preferred (optional)
    case 42: return null

    // Q43: Finance crop
    case 43:
      if (!['1','2','3','4','5','6','7'].includes(t))
        return '❌ يرجى اختيار المحصول:\n1. سمسم\n2. ذرة رفيعة\n3. فول سوداني\n4. قطن\n5. بذرة بطيخ\n6. دخن\n7. عباد الشمس'
      return null

    // Q44: Seed variety (optional)
    case 44: return null

    // Q45: Fertiliser
    case 45:
      if (!['نعم','لا','1','2'].includes(t))
        return '❌ يرجى الاختيار:\n1 - نعم\n2 - لا'
      return null

    // Q46: Pesticides
    case 46:
      if (!['نعم','لا','1','2'].includes(t))
        return '❌ يرجى الاختيار:\n1 - نعم\n2 - لا'
      return null

    // Q47: Requested amount
    case 47: {
      const normalized = t.replace(/[٠-٩]/g, d => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)))
      const num = parseFloat(normalized.replace(/[^\d.]/g, ''))
      if (isNaN(num) || num <= 0) return '❌ يرجى إدخال المبلغ المطلوب بالأرقام.\nمثال: 5000000'
      return null
    }

    // Q48: Marital status
    case 48:
      if (!['1','2','3','4'].includes(t))
        return '❌ يرجى اختيار الحالة الاجتماعية:\n1. أعزب\n2. متزوج\n3. أرمل\n4. مطلق'
      return null

    // Q49: Wives (only if married)
    case 49: {
      const num = parseInt(t)
      if (isNaN(num) || num < 1 || num > 4)
        return '❌ يرجى إدخال عدد الزوجات (من 1 إلى 4).'
      return null
    }

    // Q50: Has children (only if married)
    case 50:
      if (!['نعم','لا','1','2'].includes(t))
        return '❌ يرجى الاختيار:\n1 - نعم\n2 - لا'
      return null

    // Q51: Total children
    case 51: {
      const num = parseInt(t)
      if (isNaN(num) || num < 0) return '❌ يرجى إدخال عدد الأطفال.'
      return null
    }

    // Q52: Children under 18
    case 52: {
      const num = parseInt(t)
      if (isNaN(num) || num < 0) return '❌ يرجى إدخال عدد الأطفال دون سن 18.'
      return null
    }

    // Q53: Other dependents
    case 53:
      if (!['نعم','لا','1','2'].includes(t))
        return '❌ يرجى الاختيار:\n1 - نعم\n2 - لا'
      return null

    // Q54: Dependents count
    case 54: {
      const num = parseInt(t)
      if (isNaN(num) || num < 1) return '❌ يرجى إدخال عدد المعالين.'
      return null
    }

    // Q55: Other income
    case 55:
      if (!['نعم','لا','1','2'].includes(t))
        return '❌ يرجى الاختيار:\n1 - نعم\n2 - لا'
      return null

    // Q56: Income sources
    case 56: {
      const parts = t.split(/[,،\s]+/).map(s => s.trim()).filter(Boolean)
      if (!parts.length || !parts.every(p => ['1','2','3','4','5'].includes(p)))
        return '❌ يرجى اختيار الأرقام:\n1. وظيفة رسمية\n2. تجارة\n3. رعي\n4. حوالات\n5. دعم نقدي من منظمة\n\nمثال: 1,4'
      return null
    }

    // Q57: Remittances (optional)
    case 57: return null

    // Q58: Challenges (optional)
    case 58: return null

    default: return null
  }
}
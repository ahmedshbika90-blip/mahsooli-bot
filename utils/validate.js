export function validateAnswer(step, text) {
  const t = text.trim()

  switch (step) {
    // Q1: First Name
    case 1:
      if (t.length < 2) return '❌ الاسم قصير جداً. يرجى إدخال الاسم الأول.'
      if (/\d/.test(t)) return '❌ يجب ألا يحتوي الاسم على أرقام.'
      return null

    // Q2: Second Name
    case 2:
      if (t.length < 2) return '❌ الاسم قصير جداً. يرجى إدخال الاسم الثاني.'
      if (/\d/.test(t)) return '❌ يجب ألا يحتوي الاسم على أرقام.'
      return null

    // Q3: Third Name (optional)
    case 3:
      if (t === '-' || t === 'لا يوجد' || t === 'skip') return null
      if (t.length < 2) return '❌ الاسم قصير جداً. إذا لم يكن لديك اسم ثالث اكتب: لا يوجد'
      if (/\d/.test(t)) return '❌ يجب ألا يحتوي الاسم على أرقام.'
      return null

    // Q4: Last Name
    case 4:
      if (t.length < 2) return '❌ الاسم قصير جداً. يرجى إدخال اسم العائلة.'
      if (/\d/.test(t)) return '❌ يجب ألا يحتوي الاسم على أرقام.'
      return null

    // Q5: Date of Birth
    case 5: {
      const parts = t.split('/')
      if (parts.length !== 3) return '❌ صيغة غير صحيحة. يرجى الإدخال بهذا الشكل: YYYY/MM/DD\nمثال: 1990/05/15'
      const [y, m, d] = parts.map(Number)
      if (isNaN(y) || isNaN(m) || isNaN(d)) return '❌ يرجى إدخال أرقام صحيحة. مثال: 1990/05/15'
      if (y < 1920 || y > 2010) return '❌ السنة يجب أن تكون بين 1920 و 2010.'
      if (m < 1 || m > 12) return '❌ الشهر يجب أن يكون بين 1 و 12.'
      if (d < 1 || d > 31) return '❌ اليوم يجب أن يكون بين 1 و 31.'
      return null
    }

    // Q6: Gender
    case 6: {
      const valid = ['ذكر', 'أنثى', '1', '2']
      if (!valid.includes(t)) return '❌ يرجى الاختيار:\n1 - ذكر\n2 - أنثى'
      return null
    }

    // Q7: Primary Phone
    case 7: {
      const digits = t.replace(/\D/g, '')
      if (digits.length !== 10) return '❌ رقم الهاتف يجب أن يكون 10 أرقام.'
      if (!digits.startsWith('0')) return '❌ رقم الهاتف يجب أن يبدأ بـ 0.\nمثال: 0912345678'
      return null
    }

    // Q8: Secondary Phone (optional)
    case 8: {
      if (t === '-' || t === 'لا يوجد' || t.toLowerCase() === 'skip') return null
      const digits = t.replace(/\D/g, '')
      if (digits.length !== 10) return '❌ رقم الهاتف يجب أن يكون 10 أرقام. إذا لم يكن لديك رقم ثانٍ اكتب: لا يوجد'
      if (!digits.startsWith('0')) return '❌ رقم الهاتف يجب أن يبدأ بـ 0.'
      return null
    }

    // Q9: Has national ID?
    case 9: {
      const valid = ['نعم', 'لا', '1', '2']
      if (!valid.includes(t)) return '❌ يرجى الاختيار:\n1 - نعم\n2 - لا'
      return null
    }

    // Q10: National ID Number (only asked if answered نعم to Q9)
    case 10: {
      const clean = t.replace(/[-\s]/g, '')
      if (clean.length !== 11) return '❌ رقم الهوية الوطنية يجب أن يكون 11 رقماً.'
      if (!/^\d+$/.test(clean)) return '❌ رقم الهوية يجب أن يحتوي على أرقام فقط.'
      return null
    }

    // Q11: State
    case 11: {
      const states = [
        'الخرطوم', 'الجزيرة', 'سنار', 'النيل الأبيض', 'النيل الأزرق',
        'شمال كردفان', 'جنوب كردفان', 'غرب كردفان',
        'شمال دارفور', 'جنوب دارفور', 'شرق دارفور', 'غرب دارفور', 'وسط دارفور',
        'كسلا', 'البحر الأحمر', 'القضارف', 'نهر النيل', 'الشمالية'
      ]
      const nums = Array.from({length: 18}, (_, i) => String(i + 1))
      if (nums.includes(t)) return null
      if (states.some(s => t.includes(s) || s.includes(t))) return null
      return `❌ يرجى اختيار رقم الولاية:\n1. الخرطوم\n2. الجزيرة\n3. سنار\n4. النيل الأبيض\n5. النيل الأزرق\n6. شمال كردفان\n7. جنوب كردفان\n8. غرب كردفان\n9. شمال دارفور\n10. جنوب دارفور\n11. شرق دارفور\n12. غرب دارفور\n13. وسط دارفور\n14. كسلا\n15. البحر الأحمر\n16. القضارف\n17. نهر النيل\n18. الشمالية`
    }

    // Q12: Locality
    case 12:
      if (t.length < 2) return '❌ يرجى إدخال اسم المحلية.'
      return null

    // Q13: Education
    case 13: {
      const valid = ['1', '2', '3', '4', '5', '6', '7', '8']
      if (!valid.includes(t)) return '❌ يرجى اختيار المستوى التعليمي:\n1. لا يوجد\n2. خلوة (يقرأ ويكتب)\n3. مرحلة أساسية\n4. مرحلة ثانوية\n5. دبلوم\n6. بكالوريوس\n7. ماجستير\n8. دكتوراه'
      return null
    }

    // Q14: Smartphone
    case 14: {
      const valid = ['نعم', 'لا', '1', '2']
      if (!valid.includes(t)) return '❌ يرجى الاختيار:\n1 - نعم\n2 - لا'
      return null
    }

    // Q15: Network coverage
    case 15: {
      const valid = ['نعم', 'لا', '1', '2']
      if (!valid.includes(t)) return '❌ يرجى الاختيار:\n1 - نعم\n2 - لا'
      return null
    }

    // Q16: Best network
    case 16: {
      const valid = ['زين', 'سوداني', 'mtn', 'MTN', '1', '2', '3']
      if (!valid.includes(t) && !valid.includes(t.toLowerCase())) return '❌ يرجى الاختيار:\n1 - زين\n2 - سوداني\n3 - MTN'
      return null
    }

    // Q17: Bank account
    case 17: {
      const valid = ['نعم', 'لا', '1', '2']
      if (!valid.includes(t)) return '❌ يرجى الاختيار:\n1 - نعم\n2 - لا'
      return null
    }

    // Q18: Which banks (only if yes to Q17)
    case 18: {
      const valid = ['1','2','3','4','5','6','7']
      const parts = t.split(/[,،\s]+/).map(s => s.trim()).filter(Boolean)
      if (parts.length === 0) return '❌ يرجى اختيار بنك واحد على الأقل:\n1. بنك الخرطوم\n2. بنك فيصل الإسلامي\n3. بنك النيل\n4. SAB\n5. بنك أمدرمان الوطني\n6. بنك النيلين\n7. أخرى'
      if (!parts.every(p => valid.includes(p))) return '❌ يرجى اختيار الأرقام فقط:\n1. بنك الخرطوم\n2. بنك فيصل الإسلامي\n3. بنك النيل\n4. SAB\n5. بنك أمدرمان الوطني\n6. بنك النيلين\n7. أخرى\n\nمثال: 1 أو 1,3'
      return null
    }

    // Q19: Banking apps (only if yes to Q17)
    case 19: {
      const valid = ['1','2','3','4','5','6','7']
      const parts = t.split(/[,،\s]+/).map(s => s.trim()).filter(Boolean)
      if (!parts.every(p => valid.includes(p))) return '❌ يرجى اختيار الأرقام فقط:\n1. تطبيق بنك الخرطوم\n2. تطبيق بنك فيصل\n3. تطبيق بنك النيل\n4. تطبيق SAB\n5. تطبيق ONB\n6. تطبيق بنك النيلين\n7. لا أستخدم تطبيقاً\n\nمثال: 1 أو 1,3'
      return null
    }

    // Q20: Union member
    case 20: {
      const valid = ['نعم', 'لا', '1', '2']
      if (!valid.includes(t)) return '❌ يرجى الاختيار:\n1 - نعم\n2 - لا'
      return null
    }

    // Q21: Union name (only if yes to Q20)
    case 21:
      if (t.length < 2) return '❌ يرجى إدخال اسم الاتحاد أو الجمعية.'
      return null

    // Q22: Farm size
    case 22: {
      const num = parseFloat(t.replace(/[^\d.]/g, ''))
      if (isNaN(num) || num <= 0) return '❌ يرجى إدخال مساحة الأرض بالأرقام فقط.\nمثال: 25 أو 7.5'
      if (num > 10000) return '❌ المساحة كبيرة جداً. يرجى التحقق من الرقم.'
      return null
    }

    // Q23: Owned or rented
    case 23: {
      const valid = ['مملوكة', 'مستأجرة', '1', '2']
      if (!valid.includes(t)) return '❌ يرجى الاختيار:\n1 - مملوكة\n2 - مستأجرة'
      return null
    }

    // Q24: Rent amount (only if rented)
    case 24: {
      const num = parseFloat(t.replace(/[^\d.]/g, ''))
      if (isNaN(num) || num <= 0) return '❌ يرجى إدخال مبلغ الإيجار بالأرقام فقط.\nمثال: 500000'
      return null
    }

    // Q25: Ownership documents (only if owned)
    case 25: {
      const valid = ['نعم', 'لا', '1', '2']
      if (!valid.includes(t)) return '❌ يرجى الاختيار:\n1 - نعم\n2 - لا'
      return null
    }

    // Q26: Has guarantees
    case 26: {
      const valid = ['نعم', 'لا', '1', '2']
      if (!valid.includes(t)) return '❌ يرجى الاختيار:\n1 - نعم\n2 - لا'
      return null
    }

    // Q27: Guarantee types (only if yes to Q26)
    case 27: {
      const valid = ['1','2','3','4']
      const parts = t.split(/[,،\s]+/).map(s => s.trim()).filter(Boolean)
      if (parts.length === 0) return '❌ يرجى اختيار نوع الضمان:\n1. شيك\n2. معدات\n3. أرض\n4. أخرى'
      if (!parts.every(p => valid.includes(p))) return '❌ يرجى اختيار الأرقام فقط:\n1. شيك\n2. معدات\n3. أرض\n4. أخرى\n\nمثال: 3 أو 1,3'
      return null
    }

    // Q28: Other guarantee (only if chose أخرى in Q27)
    case 28:
      if (t.length < 2) return '❌ يرجى تحديد نوع الضمان.'
      return null

    // Q29: Crops last 3 seasons
    case 29: {
      const valid = ['1','2','3','4','5','6','7']
      const parts = t.split(/[,،\s]+/).map(s => s.trim()).filter(Boolean)
      if (parts.length === 0) return '❌ يرجى اختيار المحاصيل:\n1. سمسم\n2. ذرة رفيعة\n3. فول سوداني\n4. قطن\n5. بذرة بطيخ\n6. دخن\n7. عباد الشمس\n\nمثال: 1,2,3'
      if (!parts.every(p => valid.includes(p))) return '❌ يرجى اختيار الأرقام فقط:\n1. سمسم\n2. ذرة رفيعة\n3. فول سوداني\n4. قطن\n5. بذرة بطيخ\n6. دخن\n7. عباد الشمس\n\nمثال: 1,2,3'
      return null
    }

    // Q30-36: Yield per crop (free text, write NA if not applicable)
    case 30:
    case 31:
    case 32:
    case 33:
    case 34:
    case 35:
    case 36:
      if (t.length === 0) return '❌ يرجى إدخال متوسط الإنتاجية أو اكتب: لا يوجد'
      return null

    // Q37: How financed
    case 37: {
      const valid = ['1','2','3','4','5']
      if (!valid.includes(t)) return '❌ يرجى اختيار طريقة التمويل:\n1. بنك\n2. تمويل ذاتي\n3. ائتمان تاجر\n4. منظمة\n5. أخرى'
      return null
    }

    // Q38: Finance amount (only if bank)
    case 38: {
      const num = parseFloat(t.replace(/[^\d.]/g, ''))
      if (isNaN(num) || num <= 0) return '❌ يرجى إدخال مبلغ التمويل بالأرقام فقط.\nمثال: 5000000'
      return null
    }

    // Q39: Repaid?
    case 39: {
      const valid = ['نعم', 'لا', '1', '2']
      if (!valid.includes(t)) return '❌ يرجى الاختيار:\n1 - نعم\n2 - لا'
      return null
    }

    // Q40: Why not repaid (only if لا to Q39)
    case 40: {
      const valid = ['1','2','3','4']
      if (!valid.includes(t)) return '❌ يرجى اختيار السبب:\n1. إنتاج منخفض\n2. تكلفة مدخلات عالية\n3. لا يوجد إنتاج\n4. أخرى'
      return null
    }

    // Q41: How finance was used (only if bank)
    case 41: {
      const valid = ['1','2','3','4','5','6']
      const parts = t.split(/[,،\s]+/).map(s => s.trim()).filter(Boolean)
      if (parts.length === 0) return '❌ يرجى اختيار كيفية استخدام التمويل:\n1. بذور\n2. سماد\n3. مبيدات\n4. إيجار آلات\n5. وقود\n6. حصاد\n\nمثال: 1,2'
      if (!parts.every(p => valid.includes(p))) return '❌ يرجى اختيار الأرقام فقط:\n1. بذور\n2. سماد\n3. مبيدات\n4. إيجار آلات\n5. وقود\n6. حصاد'
      return null
    }

    // Q42: Which bank provided finance
    case 42: {
      const valid = ['1','2','3','4','5','6','7']
      if (!valid.includes(t)) return '❌ يرجى اختيار البنك:\n1. بنك الخرطوم\n2. بنك فيصل الإسلامي\n3. بنك النيل\n4. SAB\n5. بنك أمدرمان الوطني\n6. بنك النيلين\n7. أخرى'
      return null
    }

    // Q43: Preferred crops this season
    case 43: {
      const valid = ['1','2','3','4','5','6','7']
      const parts = t.split(/[,،\s]+/).map(s => s.trim()).filter(Boolean)
      if (parts.length === 0) return '❌ يرجى اختيار المحاصيل المفضلة:\n1. سمسم\n2. ذرة رفيعة\n3. فول سوداني\n4. قطن\n5. بذرة بطيخ\n6. دخن\n7. عباد الشمس\n\nمثال: 1,3,4'
      if (!parts.every(p => valid.includes(p))) return '❌ يرجى اختيار الأرقام فقط.'
      return null
    }

    // Q44: Why preferred (optional free text)
    case 44:
      return null

    // Q45: Crop requesting finance for
    case 45: {
      const valid = ['1','2','3','4','5','6','7']
      if (!valid.includes(t)) return '❌ يرجى اختيار المحصول:\n1. سمسم\n2. ذرة رفيعة\n3. فول سوداني\n4. قطن\n5. بذرة بطيخ\n6. دخن\n7. عباد الشمس'
      return null
    }

    // Q46: Seed variety (optional)
    case 46:
      return null

    // Q47: Use fertiliser
    case 47: {
      const valid = ['نعم', 'لا', '1', '2']
      if (!valid.includes(t)) return '❌ يرجى الاختيار:\n1 - نعم\n2 - لا'
      return null
    }

    // Q48: Use pesticides
    case 48: {
      const valid = ['نعم', 'لا', '1', '2']
      if (!valid.includes(t)) return '❌ يرجى الاختيار:\n1 - نعم\n2 - لا'
      return null
    }

    // Q49: Requested finance amount
    case 49: {
      const num = parseFloat(t.replace(/[^\d.]/g, ''))
      if (isNaN(num) || num <= 0) return '❌ يرجى إدخال المبلغ المطلوب بالأرقام فقط.\nمثال: 5000000'
      return null
    }

    // Q50: Marital status
    case 50: {
      const valid = ['1','2','3','4']
      if (!valid.includes(t)) return '❌ يرجى اختيار الحالة الاجتماعية:\n1. أعزب\n2. متزوج\n3. أرمل\n4. مطلق'
      return null
    }

    // Q51: Number of wives (only if married)
    case 51: {
      const num = parseInt(t)
      if (isNaN(num) || num < 1 || num > 4) return '❌ يرجى إدخال عدد الزوجات (من 1 إلى 4).'
      return null
    }

    // Q52: Has children
    case 52: {
      const valid = ['نعم', 'لا', '1', '2']
      if (!valid.includes(t)) return '❌ يرجى الاختيار:\n1 - نعم\n2 - لا'
      return null
    }

    // Q53: Total children (only if yes to Q52)
    case 53: {
      const num = parseInt(t)
      if (isNaN(num) || num < 0) return '❌ يرجى إدخال عدد الأطفال.'
      return null
    }

    // Q54: Children under 18 (only if yes to Q52)
    case 54: {
      const num = parseInt(t)
      if (isNaN(num) || num < 0) return '❌ يرجى إدخال عدد الأطفال دون سن 18.'
      return null
    }

    // Q55: Other dependents
    case 55: {
      const valid = ['نعم', 'لا', '1', '2']
      if (!valid.includes(t)) return '❌ يرجى الاختيار:\n1 - نعم\n2 - لا'
      return null
    }

    // Q56: How many dependents (only if yes to Q55)
    case 56: {
      const num = parseInt(t)
      if (isNaN(num) || num < 1) return '❌ يرجى إدخال عدد المعالين.'
      return null
    }

    // Q57: Other income sources
    case 57: {
      const valid = ['نعم', 'لا', '1', '2']
      if (!valid.includes(t)) return '❌ يرجى الاختيار:\n1 - نعم\n2 - لا'
      return null
    }

    // Q58: What income sources (only if yes to Q57)
    case 58: {
      const valid = ['1','2','3','4','5']
      const parts = t.split(/[,،\s]+/).map(s => s.trim()).filter(Boolean)
      if (parts.length === 0) return '❌ يرجى اختيار مصادر الدخل:\n1. وظيفة رسمية\n2. تجارة\n3. رعي\n4. حوالات\n5. دعم نقدي من منظمة\n\nمثال: 1,4'
      if (!parts.every(p => valid.includes(p))) return '❌ يرجى اختيار الأرقام فقط.'
      return null
    }

    // Q59: Remittances amount (optional)
    case 59:
      return null

    // Q60: Challenges and solutions (optional)
    case 60:
      return null

    default:
      return null
  }
}
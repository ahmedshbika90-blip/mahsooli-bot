import { google } from 'googleapis'

function getAuthClient() {
  return new google.auth.GoogleAuth({
    credentials: {
      client_email: process.env.GOOGLE_SERVICE_ACCOUNT_EMAIL,
      private_key:  process.env.GOOGLE_PRIVATE_KEY,
    },
    scopes: ['https://www.googleapis.com/auth/spreadsheets']
  })
}

async function getSheetsClient() {
  const auth = getAuthClient()
  return google.sheets({ version: 'v4', auth })
}

export async function saveToSheets(data) {
  try {
    const sheets = await getSheetsClient()

    await sheets.spreadsheets.values.append({
      spreadsheetId: process.env.SHEET_ID,
      range: 'mahsooli!A:BT',
      valueInputOption: 'RAW',
      requestBody: {
        values: [[
          // ── البيانات الشخصية ──────────────────────────────────────────────
          data.phone            || '',   // A  رقم الواتساب
          data.first_name       || '',   // B  الاسم الأول
          data.second_name      || '',   // C  الاسم الثاني
          data.third_name       || '',   // D  الاسم الثالث
          data.fourth_name      || '',   // E  الاسم الرابع
          data.dob              || '',   // F  تاريخ الميلاد
          data.gender           || '',   // G  الجنس
          data.phone_primary    || '',   // H  الهاتف الأساسي
          data.phone_secondary  || '',   // I  الهاتف الثانوي
          data.has_id           || '',   // J  هل لديه هوية؟
          data.id_number        || '',   // K  رقم الهوية
          data.id_photo         || '',   // L  صورة الهوية

          // ── بيانات السكن والتواصل ─────────────────────────────────────────
          data.state            || '',   // M  الولاية
          data.locality         || '',   // N  المحلية
          data.education        || '',   // O  المستوى التعليمي
          data.has_smartphone   || '',   // P  هاتف ذكي؟
          data.network_coverage || '',   // Q  تغطية شبكة؟
          data.best_network     || '',   // R  أفضل شبكة

          // ── البنوك ───────────────────────────────────────────────────────
          data.has_bank         || '',   // S  حساب بنكي؟
          data.banks            || '',   // T  البنوك
          data.banking_apps     || '',   // U  التطبيقات البنكية
          data.other_bank       || '',   // V  بنك / تطبيق آخر

          // ── الزراعة والتمويل ─────────────────────────────────────────────
          data.union_member     || '',   // W  عضو اتحاد؟
          data.union_name       || '',   // X  اسم الاتحاد
          data.farm_size        || '',   // Y  مساحة الأرض (فدان)
          data.land_ownership   || '',   // Z  ملكية الأرض
          data.rent_tenure      || '',   // AA مدة الإيجار
          data.ownership_docs   || '',   // AB وثائق الملكية؟
          data.has_guarantees   || '',   // AC ضمانات؟
          data.guarantee_types  || '',   // AD أنواع الضمانات
          data.other_guarantee  || '',   // AE ضمان آخر
          data.crops_last3      || '',   // AF محاصيل آخر 3 مواسم
          data.yield_sesame     || '',   // AG إنتاجية السمسم
          data.yield_sorghum    || '',   // AH إنتاجية الذرة
          data.yield_groundnut  || '',   // AI إنتاجية الفول
          data.yield_cotton     || '',   // AJ إنتاجية القطن
          data.yield_watermelon || '',   // AK إنتاجية البطيخ
          data.yield_millet     || '',   // AL إنتاجية الدخن
          data.yield_sunflower  || '',   // AM إنتاجية عباد الشمس
          data.finance_source   || '',   // AN مصدر التمويل الماضي
          data.other_finance    || '',   // AO مصدر تمويل آخر
          data.finance_amount   || '',   // AP مبلغ التمويل
          data.repaid           || '',   // AQ سداد التمويل؟
          data.no_repay_reason  || '',   // AR سبب عدم السداد
          data.other_repay_reason || '', // AS سبب آخر لعدم السداد
          data.finance_use      || '',   // AT استخدام التمويل
          data.finance_bank     || '',   // AU البنك الممول
          data.other_finance_bank || '', // AV بنك ممول آخر

          // ── المحاصيل وطلب التمويل ────────────────────────────────────────
          data.preferred_crops      || '', // AW محاصيل هذا الموسم
          data.crop_reason          || '', // AX سبب اختيار المحاصيل
          data.other_crop_reason    || '', // AY سبب آخر
          data.finance_crop         || '', // AZ المحصول المطلوب تمويله
          data.seed_variety         || '', // BA صنف البذرة
          data.other_variety        || '', // BB صنف آخر
          data.use_fertiliser       || '', // BC استخدام أسمدة؟
          data.no_fertiliser_reason || '', // BD سبب عدم الأسمدة
          data.other_no_fertiliser  || '', // BE سبب آخر (أسمدة)
          data.use_pesticides       || '', // BF استخدام مبيدات؟
          data.no_pesticides_reason || '', // BG سبب عدم المبيدات
          data.other_no_pesticides  || '', // BH سبب آخر (مبيدات)
          data.requested_amount     || '', // BI المبلغ المطلوب

          // ── بيانات الأسرة ─────────────────────────────────────────────────
          data.marital_status   || '',   // BJ الحالة الاجتماعية
          data.wives            || '',   // BK عدد الزوجات
          data.has_children     || '',   // BL أطفال؟
          data.total_children   || '',   // BM عدد الأطفال
          data.children_under18 || '',   // BN أطفال دون 18
          data.other_dependents || '',   // BO معالون آخرون؟
          data.dependents_count || '',   // BP عدد المعالين
          data.other_income     || '',   // BQ دخل آخر غير الزراعة؟
          data.income_sources   || '',   // BR مصادر الدخل الأخرى
          data.remittances      || '',   // BS مبلغ الحوالات

          // ── الإدارة ───────────────────────────────────────────────────────
          data.consent          || '',   // BT الإقرار والموافقة
          data.timestamp        || '',   // BU تاريخ التسجيل
        ]]
      }
    })

    return true

  } catch (err) {
    console.error('Sheets save failed:', err.message)
    return false
  }
}
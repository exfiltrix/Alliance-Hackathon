export type Lang = "uz" | "ru";

export const LANGS: { code: Lang; label: string }[] = [
  { code: "uz", label: "UZ" },
  { code: "ru", label: "RU" },
];

export const DEFAULT_LANG: Lang = "uz";

const dictionary = {
  nav: {
    home: { uz: "Bosh sahifa", ru: "Главная" },
    seal: { uz: "Muhrlash", ru: "Печать" },
    verify: { uz: "Tekshirish", ru: "Проверка" },
    crashTest: { uz: "Sinov hujumi", ru: "Краш-тест" },
    dashboard: { uz: "Statistika", ru: "Статистика" },
    cta: { uz: "Boshlash", ru: "Начать" },
  },
  home: {
    badge: {
      uz: "Milliy AI xakaton · Tibbiyot yo'nalishi",
      ru: "Национальный AI-хакатон · Трек «Медицина»",
    },
    heroTitle: {
      uz: "Rentgen va KT suratlarini soxtalashtirishdan himoya qiling",
      ru: "Защитите рентген и КТ-снимки от подделки",
    },
    heroSubtitle: {
      uz: "MedSeal — tibbiy suratlar va ularni o'qiydigan sun'iy intellekt uchun raqamli muhr va antivirus. Surat asl ekanini va AI aldanmaganini isbotlaymiz.",
      ru: "MedSeal — цифровая печать и антивирус для медицинских снимков и AI, который их читает. Доказываем подлинность снимка и то, что AI нельзя обмануть.",
    },
    ctaPrimary: { uz: "Suratni muhrlash", ru: "Запечатать снимок" },
    ctaSecondary: { uz: "Suratni tekshirish", ru: "Проверить снимок" },
    mockBadgeSealed: { uz: "Muhrlandi", ru: "Запечатано" },
    mockUid: { uz: "ID: 1.3.6.1…", ru: "ID: 1.3.6.1…" },
    mockTiles: { uz: "256 ta bo'lak · Ed25519 imzo", ru: "256 фрагментов · подпись Ed25519" },
    servicesTitle: { uz: "Bizning xizmatlar", ru: "Наши сервисы" },
    servicesSubtitle: {
      uz: "Suratni olishdan tortib, AI modelini sertifikatlashgacha — bitta platformada.",
      ru: "От момента съёмки до сертификации AI-модели — всё в одной платформе.",
    },
    open: { uz: "Ochish", ru: "Открыть" },
    howTitle: { uz: "Qanday ishlaydi", ru: "Как это работает" },
    howSubtitle: {
      uz: "To'rt qadam: suratni olishdan AI modelini tasdiqlashgacha. Istalgan qadamdan boshlang.",
      ru: "Четыре шага: от съёмки до допуска AI-модели. Начните с любого шага.",
    },
    stepLabel: { uz: "Qadam", ru: "Шаг" },
    disclaimer: {
      uz: "Muhr — matematik jihatdan aniq natija. Detektiv va Qalqon esa faqat ehtimollikni ko'rsatadi. Yakuniy qarorni har doim shifokor qabul qiladi.",
      ru: "Печать — математически точный результат. Детектив и Щит показывают только вероятность. Итоговое решение всегда принимает врач.",
    },
    footerTagline: {
      uz: "Tibbiy suratlar va tibbiy AI uchun muhr va antivirus.",
      ru: "Печать и антивирус для медицинских снимков и медицинского AI.",
    },
  },
  flow: {
    label: { uz: "Yo'l", ru: "Путь" },
    next: { uz: "Keyingi qadam", ru: "Следующий шаг" },
    steps: {
      seal: {
        title: { uz: "Muhrlash", ru: "Печать" },
        desc: { uz: "Suratni skanerdan chiqishi bilan imzolang", ru: "Подпишите снимок сразу после съёмки" },
      },
      verify: {
        title: { uz: "Tekshirish", ru: "Проверка" },
        desc: { uz: "Shifokor ko'rishidan oldin haqiqiyligini tekshiring", ru: "Проверьте подлинность до показа врачу" },
      },
      crash: {
        title: { uz: "Sinov hujumi", ru: "Краш-тест" },
        desc: { uz: "AI modelini ko'rinmas hujum bilan sinang", ru: "Испытайте AI-модель невидимой атакой" },
      },
      passport: {
        title: { uz: "Pasport", ru: "Паспорт" },
        desc: { uz: "Model uchun xavfsizlik pasportini oling", ru: "Получите паспорт безопасности модели" },
      },
    },
  },
  services: {
    seal: {
      title: { uz: "Muhr", ru: "Печать" },
      desc: {
        uz: "Suratni olish paytida SHA-256, Merkle daraxti va Ed25519 imzo bilan muhrlaymiz.",
        ru: "Печатаем снимок в момент съёмки: SHA-256, дерево Меркла, подпись Ed25519.",
      },
    },
    verify: {
      title: { uz: "Tekshirish", ru: "Проверка" },
      desc: {
        uz: "Shifokor yoki AI ko'rishdan oldin: asl / o'zgartirilgan / muhrlanmagan.",
        ru: "До показа врачу или AI: подлинный / изменён / без печати.",
      },
    },
    detective: {
      title: { uz: "AI detektiv", ru: "AI-детектив" },
      desc: {
        uz: "Muhrlanmagan suratlar uchun: soxtalik ehtimoli va issiqlik xaritasi.",
        ru: "Для снимков без печати: вероятность подделки и тепловая карта.",
      },
    },
    crashTest: {
      title: { uz: "Sinov hujumi", ru: "Краш-тест" },
      desc: {
        uz: "Tibbiy AI modeliga FGSM/PGD hujumi va 0–10 balllik mustahkamlik bahosi.",
        ru: "Атака FGSM/PGD на медицинскую AI-модель и оценка устойчивости 0–10.",
      },
    },
    shield: {
      title: { uz: "AI qalqon", ru: "AI-щит" },
      desc: {
        uz: "Diagnostika AI'siga yetib borishdan oldin yashirin hujumni aniqlaydi.",
        ru: "Обнаруживает скрытую атаку до того, как снимок дойдёт до диагностического AI.",
      },
    },
    passport: {
      title: { uz: "Model pasporti", ru: "Паспорт модели" },
      desc: {
        uz: "Har bir AI modeli uchun bir sahifalik hisobot, PDF ko'rinishida.",
        ru: "Одностраничный отчёт по каждой AI-модели, экспорт в PDF.",
      },
    },
  },
  common: {
    back: { uz: "Orqaga", ru: "Назад" },
    doctorDecides: {
      uz: "Yakuniy qarorni shifokor qabul qiladi.",
      ru: "Итоговое решение принимает врач.",
    },
    upload: { uz: "Faylni tanlang yoki shu yerga tashlang", ru: "Выберите файл или перетащите сюда" },
    change: { uz: "Boshqa fayl", ru: "Другой файл" },
    loading: { uz: "Yuklanmoqda…", ru: "Загрузка…" },
    error: { uz: "Xatolik yuz berdi", ru: "Произошла ошибка" },
    retry: { uz: "Qayta urinish", ru: "Повторить" },
    yes: { uz: "Ha", ru: "Да" },
    no: { uz: "Yo'q", ru: "Нет" },
    certain: { uz: "Aniq natija", ru: "Точный результат" },
    probability: { uz: "Ehtimollik", ru: "Вероятность" },
    mockMode: {
      uz: "Demo rejim: backend ulanmagan, natijalar namunaviy.",
      ru: "Демо-режим: бэкенд не подключён, результаты примерные.",
    },
  },
  seal: {
    title: { uz: "Suratni muhrlash", ru: "Печать снимка" },
    subtitle: {
      uz: "DICOM yoki PNG yuklang, qurilmani tanlang — surat SHA-256 va Ed25519 bilan muhrlanadi.",
      ru: "Загрузите DICOM или PNG, выберите устройство — снимок будет запечатан SHA-256 и Ed25519.",
    },
    gatewayNote: {
      uz: "Kasalxonada bu jarayon skaner yonidagi qurilmada avtomatik bajariladi.",
      ru: "В больнице это происходит автоматически на устройстве рядом со сканером.",
    },
    device: { uz: "Qurilma", ru: "Устройство" },
    addDevice: { uz: "+ Yangi qurilma", ru: "+ Новое устройство" },
    deviceName: { uz: "Qurilma nomi (masalan, KT-01)", ru: "Название (например, КТ-01)" },
    hospital: { uz: "Shifoxona", ru: "Больница" },
    save: { uz: "Saqlash", ru: "Сохранить" },
    cancel: { uz: "Bekor qilish", ru: "Отмена" },
    submit: { uz: "Muhrlash", ru: "Запечатать" },
    sealing: { uz: "Muhrlanmoqda…", ru: "Печатаем…" },
    sealed: { uz: "Muhrlandi", ru: "Запечатано" },
    sealId: { uz: "Muhr ID", ru: "ID печати" },
    time: { uz: "Vaqt", ru: "Время" },
    tiles: { uz: "Bo'laklar soni", ru: "Число фрагментов" },
    root: { uz: "Merkle ildizi", ru: "Корень Меркла" },
    uid: { uz: "Surat UID", ru: "UID снимка" },
    download: { uz: "Muhrlangan faylni yuklab olish", ru: "Скачать запечатанный файл" },
    another: { uz: "Yana muhrlash", ru: "Запечатать ещё" },
    verifyNow: { uz: "Tekshirishga o'tish", ru: "Перейти к проверке" },
  },
  verify: {
    title: { uz: "Suratni tekshirish", ru: "Проверка снимка" },
    subtitle: {
      uz: "Har qanday suratni yuklang: asl, o'zgartirilgan yoki muhrlanmaganligini bilib oling.",
      ru: "Загрузите любой снимок: узнайте, подлинный он, изменён или без печати.",
    },
    checking: { uz: "Tekshirilmoqda…", ru: "Проверяем…" },
    submit: { uz: "Tekshirish", ru: "Проверить" },
    another: { uz: "Boshqa suratni tekshirish", ru: "Проверить другой снимок" },
    status: {
      authentic: {
        title: { uz: "Tasdiqlangan", ru: "Подтверждён" },
        desc: {
          uz: "Imzo haqiqiy, barcha bo'laklar mos keladi. Surat olingandan beri o'zgartirilmagan.",
          ru: "Подпись верна, все фрагменты совпадают. Снимок не менялся с момента съёмки.",
        },
      },
      tampered: {
        title: { uz: "O'zgartirilgan", ru: "Изменён" },
        desc: {
          uz: "Surat olingandan keyin o'zgartirilgan. O'zgargan joylar qizil ramkada.",
          ru: "Снимок изменён после съёмки. Изменённые участки обведены красным.",
        },
      },
      unsigned: {
        title: { uz: "Muhrlanmagan", ru: "Без печати" },
        desc: {
          uz: "Bu surat uchun muhr topilmadi. AI detektiv soxtalik ehtimolini baholadi.",
          ru: "Печать для этого снимка не найдена. AI-детектив оценил вероятность подделки.",
        },
      },
      forged: {
        title: { uz: "Soxta muhr yozuvi", ru: "Поддельная запись" },
        desc: {
          uz: "Reyestrdagi yozuv imzoga mos emas — yozuv kalitsiz tahrirlangan.",
          ru: "Запись в реестре не совпадает с подписью — её изменили без ключа.",
        },
      },
    },
    changedTiles: { uz: "O'zgargan bo'laklar", ru: "Изменённых фрагментов" },
    device: { uz: "Qurilma", ru: "Устройство" },
    preview: { uz: "Surat", ru: "Снимок" },
    detectiveTitle: { uz: "AI detektiv", ru: "AI-детектив" },
    detectiveLabel: { uz: "Soxtalik ehtimoli", ru: "Вероятность подделки" },
    detectiveNote: {
      uz: "Bu ehtimollik, aniq xulosa emas. Issiqlik xaritasi shubhali joylarni ko'rsatadi.",
      ru: "Это вероятность, а не точный вывод. Тепловая карта показывает подозрительные участки.",
    },
    heatmap: { uz: "Issiqlik xaritasi", ru: "Тепловая карта" },
    shieldTitle: { uz: "AI qalqon", ru: "AI-щит" },
    shieldClean: { uz: "Yashirin hujum aniqlanmadi", ru: "Скрытая атака не обнаружена" },
    shieldFlag: { uz: "Yashirin hujum aniqlandi", ru: "Обнаружена скрытая атака" },
    shieldFlagNote: {
      uz: "Suratda ko'zga ko'rinmas shovqin bo'lishi mumkin. Diagnostika AI natijasiga ishonmang.",
      ru: "В снимке может быть невидимый шум. Не доверяйте результату диагностического AI.",
    },
    shieldScore: { uz: "Ko'rsatkich", ru: "Показатель" },
    threshold: { uz: "chegara", ru: "порог" },
    demoHint: {
      uz: "Demo: fayl nomida \"fake\" → o'zgartirilgan, \"attack\" → hujum, muhrlangan fayl → tasdiqlangan.",
      ru: "Демо: в имени файла \"fake\" → изменён, \"attack\" → атака, запечатанный файл → подтверждён.",
    },
  },
  crash: {
    title: { uz: "Sinov hujumi", ru: "Краш-тест" },
    subtitle: {
      uz: "Tibbiy AI modeliga ko'zga ko'rinmas shovqin bilan hujum qilamiz va u qanchalik chidamli ekanini o'lchaymiz.",
      ru: "Атакуем медицинскую AI-модель невидимым шумом и измеряем её устойчивость.",
    },
    model: { uz: "Model", ru: "Модель" },
    images: { uz: "Sinov suratlari soni", ru: "Число тестовых снимков" },
    method: { uz: "Hujum usuli", ru: "Метод атаки" },
    fgsm: { uz: "FGSM (tez)", ru: "FGSM (быстро)" },
    pgd: { uz: "PGD (kuchli)", ru: "PGD (сильнее)" },
    start: { uz: "Sinovni boshlash", ru: "Запустить тест" },
    running: { uz: "Hujum davom etmoqda…", ru: "Атака идёт…" },
    beforeAfter: { uz: "Oldin / keyin", ru: "До / после" },
    before: { uz: "Asl surat", ru: "Исходный снимок" },
    after: { uz: "Shovqindan keyin", ru: "После шума" },
    pneumonia: { uz: "Pnevmoniya ehtimoli", ru: "Вероятность пневмонии" },
    invisible: {
      uz: "Shovqin ko'zga ko'rinmaydi, lekin AI tashxisi o'zgaradi.",
      ru: "Шум не виден глазу, но диагноз AI меняется.",
    },
    chartTitle: { uz: "Buzilgan tashxislar ulushi", ru: "Доля изменённых диагнозов" },
    chartAxis: { uz: "Hujum kuchi (eps, piksel 0–255)", ru: "Сила атаки (eps, пиксели 0–255)" },
    psnr: { uz: "PSNR (yuqori = ko'rinmas)", ru: "PSNR (выше = незаметнее)" },
    scoreTitle: { uz: "Mustahkamlik bahosi", ru: "Оценка устойчивости" },
    scoreFormula: {
      uz: "Baho = 10 × (1 − eps=1 dagi buzilish ulushi)",
      ru: "Оценка = 10 × (1 − доля изменённых при eps=1)",
    },
    createPassport: { uz: "Model pasportini yaratish", ru: "Создать паспорт модели" },
    restart: { uz: "Qayta sinash", ru: "Запустить заново" },
  },
  passport: {
    title: { uz: "Model pasporti", ru: "Паспорт модели" },
    subtitle: {
      uz: "AI modeli bemorlarga qo'llanilishidan oldin uning xavfsizligi haqida bir sahifalik hisobot.",
      ru: "Одностраничный отчёт о безопасности AI-модели до её применения к пациентам.",
    },
    model: { uz: "Model", ru: "Модель" },
    version: { uz: "Versiya", ru: "Версия" },
    intendedUse: { uz: "Maqsad", ru: "Назначение" },
    robustness: { uz: "Mustahkamlik bahosi", ru: "Оценка устойчивости" },
    shieldCompatible: { uz: "AI qalqon bilan mos", ru: "Совместима с AI-щитом" },
    pipelineProtected: { uz: "Suratlar oqimi muhrlangan", ru: "Поток снимков защищён печатью" },
    verdict: { uz: "Xulosa", ru: "Вердикт" },
    verdicts: {
      allowed: { uz: "Ruxsat etiladi", ru: "Допускается" },
      conditional: { uz: "Shartli ruxsat", ru: "Допускается с условиями" },
      not_allowed: { uz: "Ruxsat etilmaydi", ru: "Не допускается" },
    },
    conditions: { uz: "Shartlar", ru: "Условия" },
    organisation: { uz: "Mas'ul tashkilot", ru: "Ответственная организация" },
    date: { uz: "Sana", ru: "Дата" },
    crashTest: { uz: "Sinov hujumi №", ru: "Краш-тест №" },
    downloadPdf: { uz: "PDF yuklab olish", ru: "Скачать PDF" },
    print: { uz: "Chop etish", ru: "Печать" },
    notFound: { uz: "Pasport topilmadi", ru: "Паспорт не найден" },
  },
  dashboard: {
    title: { uz: "Statistika", ru: "Статистика" },
    subtitle: {
      uz: "Muhrlangan, tekshirilgan va o'zgartirilgan suratlar, sinovdan o'tgan modellar.",
      ru: "Запечатанные, проверенные и изменённые снимки, протестированные модели.",
    },
    sealed: { uz: "Muhrlangan", ru: "Запечатано" },
    verified: { uz: "Tekshirilgan", ru: "Проверено" },
    tampered: { uz: "O'zgartirilgan", ru: "Изменено" },
    unsigned: { uz: "Muhrsiz", ru: "Без печати" },
    modelsTested: { uz: "Sinalgan modellar", ru: "Моделей протестировано" },
    avgRobustness: { uz: "O'rtacha mustahkamlik", ru: "Средняя устойчивость" },
  },
} as const;

export default dictionary;

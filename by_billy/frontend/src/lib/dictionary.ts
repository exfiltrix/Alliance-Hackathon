export type Lang = "uz" | "ru" | "en";

export const LANGS: { code: Lang; label: string; name: string; locale: string; speech: string }[] = [
  { code: "uz", label: "UZ", name: "O'zbekcha", locale: "uz-UZ", speech: "uz-UZ" },
  { code: "ru", label: "RU", name: "Русский", locale: "ru-RU", speech: "ru-RU" },
  { code: "en", label: "EN", name: "English", locale: "en-GB", speech: "en-US" },
];

export const DEFAULT_LANG: Lang = "uz";

export const localeOf = (lang: Lang) => LANGS.find((l) => l.code === lang)!.locale;

const dictionary = {
  nav: {
    home: { uz: "Bosh sahifa", ru: "Главная", en: "Home" },
    seal: { uz: "Muhrlash", ru: "Печать", en: "Seal" },
    verify: { uz: "Tekshirish", ru: "Проверка", en: "Verify" },
    crashTest: { uz: "Sinov hujumi", ru: "Краш-тест", en: "Crash test" },
    dashboard: { uz: "Statistika", ru: "Статистика", en: "Statistics" },
    cta: { uz: "Boshlash", ru: "Начать", en: "Get started" },
    menu: { uz: "Asosiy menyu", ru: "Главное меню", en: "Main menu" },
    language: { uz: "Til", ru: "Язык", en: "Language" },
    skip: { uz: "Asosiy mazmunga o'tish", ru: "Перейти к содержимому", en: "Skip to main content" },
  },
  home: {
    badge: {
      uz: "Milliy AI xakaton · Tibbiyot yo'nalishi",
      ru: "Национальный AI-хакатон · Трек «Медицина»",
      en: "National AI Hackathon · Medicine track",
    },
    heroTitle: {
      uz: "Rentgen va KT suratlarini soxtalashtirishdan himoya qiling",
      ru: "Защитите рентген и КТ-снимки от подделки",
      en: "Protect X-ray and CT images from tampering",
    },
    heroSubtitle: {
      uz: "MedSeal — tibbiy suratlar va ularni o'qiydigan sun'iy intellekt uchun raqamli muhr va antivirus. Surat asl ekanini va AI aldanmaganini isbotlaymiz.",
      ru: "MedSeal — цифровая печать и антивирус для медицинских снимков и AI, который их читает. Доказываем подлинность снимка и то, что AI нельзя обмануть.",
      en: "MedSeal is a digital seal and antivirus for medical images and the AI that reads them. We prove an image is authentic and that the AI can't be fooled.",
    },
    ctaPrimary: { uz: "Suratni muhrlash", ru: "Запечатать снимок", en: "Seal an image" },
    ctaSecondary: { uz: "Suratni tekshirish", ru: "Проверить снимок", en: "Verify an image" },
    mockBadgeSealed: { uz: "Muhrlandi", ru: "Запечатано", en: "Sealed" },
    mockUid: { uz: "ID: 1.3.6.1…", ru: "ID: 1.3.6.1…", en: "ID: 1.3.6.1…" },
    mockTiles: {
      uz: "256 ta bo'lak · Ed25519 imzo",
      ru: "256 фрагментов · подпись Ed25519",
      en: "256 tiles · Ed25519 signature",
    },
    servicesTitle: { uz: "Bizning xizmatlar", ru: "Наши сервисы", en: "Our services" },
    servicesSubtitle: {
      uz: "Suratni olishdan tortib, AI modelini sertifikatlashgacha — bitta platformada.",
      ru: "От момента съёмки до сертификации AI-модели — всё в одной платформе.",
      en: "From image capture to AI model certification — in one platform.",
    },
    open: { uz: "Ochish", ru: "Открыть", en: "Open" },
    howTitle: { uz: "Qanday ishlaydi", ru: "Как это работает", en: "How it works" },
    howSubtitle: {
      uz: "To'rt qadam: suratni olishdan AI modelini tasdiqlashgacha. Istalgan qadamdan boshlang.",
      ru: "Четыре шага: от съёмки до допуска AI-модели. Начните с любого шага.",
      en: "Four steps: from capture to approving an AI model. Start from any step.",
    },
    stepLabel: { uz: "Qadam", ru: "Шаг", en: "Step" },
    disclaimer: {
      uz: "Muhr — matematik jihatdan aniq natija. Detektiv va Qalqon esa faqat ehtimollikni ko'rsatadi. Yakuniy qarorni har doim shifokor qabul qiladi.",
      ru: "Печать — математически точный результат. Детектив и Щит показывают только вероятность. Итоговое решение всегда принимает врач.",
      en: "The seal gives a mathematically certain answer. The detective and the shield only show a probability. The final decision is always the doctor's.",
    },
    footerTagline: {
      uz: "Tibbiy suratlar va tibbiy AI uchun muhr va antivirus.",
      ru: "Печать и антивирус для медицинских снимков и медицинского AI.",
      en: "A seal and an antivirus for medical images and medical AI.",
    },
  },
  flow: {
    label: { uz: "Yo'l", ru: "Путь", en: "Steps" },
    next: { uz: "Keyingi qadam", ru: "Следующий шаг", en: "Next step" },
    steps: {
      seal: {
        title: { uz: "Muhrlash", ru: "Печать", en: "Seal" },
        desc: {
          uz: "Suratni skanerdan chiqishi bilan imzolang",
          ru: "Подпишите снимок сразу после съёмки",
          en: "Sign the image right after capture",
        },
      },
      verify: {
        title: { uz: "Tekshirish", ru: "Проверка", en: "Verify" },
        desc: {
          uz: "Shifokor ko'rishidan oldin haqiqiyligini tekshiring",
          ru: "Проверьте подлинность до показа врачу",
          en: "Check authenticity before a doctor sees it",
        },
      },
      crash: {
        title: { uz: "Sinov hujumi", ru: "Краш-тест", en: "Crash test" },
        desc: {
          uz: "AI modelini ko'rinmas hujum bilan sinang",
          ru: "Испытайте AI-модель невидимой атакой",
          en: "Test the AI model with an invisible attack",
        },
      },
      passport: {
        title: { uz: "Pasport", ru: "Паспорт", en: "Passport" },
        desc: {
          uz: "Model uchun xavfsizlik pasportini oling",
          ru: "Получите паспорт безопасности модели",
          en: "Get a safety passport for the model",
        },
      },
    },
  },
  services: {
    seal: {
      title: { uz: "Muhr", ru: "Печать", en: "Seal" },
      desc: {
        uz: "Suratni olish paytida SHA-256, Merkle daraxti va Ed25519 imzo bilan muhrlaymiz.",
        ru: "Печатаем снимок в момент съёмки: SHA-256, дерево Меркла, подпись Ed25519.",
        en: "We seal the image at capture: SHA-256, a Merkle tree and an Ed25519 signature.",
      },
    },
    verify: {
      title: { uz: "Tekshirish", ru: "Проверка", en: "Verify" },
      desc: {
        uz: "Shifokor yoki AI ko'rishdan oldin: asl / o'zgartirilgan / muhrlanmagan.",
        ru: "До показа врачу или AI: подлинный / изменён / без печати.",
        en: "Before a doctor or AI sees it: authentic / tampered / unsigned.",
      },
    },
    detective: {
      title: { uz: "AI detektiv", ru: "AI-детектив", en: "AI detective" },
      desc: {
        uz: "Muhrlanmagan suratlar uchun: soxtalik ehtimoli va issiqlik xaritasi.",
        ru: "Для снимков без печати: вероятность подделки и тепловая карта.",
        en: "For unsigned images: tampering probability and a heatmap.",
      },
    },
    crashTest: {
      title: { uz: "Sinov hujumi", ru: "Краш-тест", en: "Crash test" },
      desc: {
        uz: "Tibbiy AI modeliga FGSM/PGD hujumi va 0–10 balllik mustahkamlik bahosi.",
        ru: "Атака FGSM/PGD на медицинскую AI-модель и оценка устойчивости 0–10.",
        en: "FGSM/PGD attack on a medical AI model and a 0–10 robustness score.",
      },
    },
    shield: {
      title: { uz: "AI qalqon", ru: "AI-щит", en: "AI shield" },
      desc: {
        uz: "Diagnostika AI'siga yetib borishdan oldin yashirin hujumni aniqlaydi.",
        ru: "Обнаруживает скрытую атаку до того, как снимок дойдёт до диагностического AI.",
        en: "Detects a hidden attack before the image reaches the diagnostic AI.",
      },
    },
    passport: {
      title: { uz: "Model pasporti", ru: "Паспорт модели", en: "Model passport" },
      desc: {
        uz: "Har bir AI modeli uchun bir sahifalik hisobot, PDF ko'rinishida.",
        ru: "Одностраничный отчёт по каждой AI-модели, экспорт в PDF.",
        en: "A one-page report for every AI model, exportable to PDF.",
      },
    },
  },
  common: {
    back: { uz: "Orqaga", ru: "Назад", en: "Back" },
    breadcrumb: { uz: "Siz shu yerdasiz", ru: "Вы здесь", en: "You are here" },
    doctorDecides: {
      uz: "Yakuniy qarorni shifokor qabul qiladi.",
      ru: "Итоговое решение принимает врач.",
      en: "The final decision is made by the doctor.",
    },
    upload: {
      uz: "Faylni tanlang yoki shu yerga tashlang",
      ru: "Выберите файл или перетащите сюда",
      en: "Choose a file or drop it here",
    },
    change: { uz: "Boshqa fayl", ru: "Другой файл", en: "Choose another file" },
    loading: { uz: "Yuklanmoqda…", ru: "Загрузка…", en: "Loading…" },
    error: { uz: "Xatolik yuz berdi", ru: "Произошла ошибка", en: "Something went wrong" },
    retry: { uz: "Qayta urinish", ru: "Повторить", en: "Try again" },
    yes: { uz: "Ha", ru: "Да", en: "Yes" },
    no: { uz: "Yo'q", ru: "Нет", en: "No" },
    certain: { uz: "Aniq natija", ru: "Точный результат", en: "Certain result" },
    probability: { uz: "Ehtimollik", ru: "Вероятность", en: "Probability" },
    mockMode: {
      uz: "Demo rejim: backend ulanmagan, natijalar namunaviy.",
      ru: "Демо-режим: бэкенд не подключён, результаты примерные.",
      en: "Demo mode: backend not connected, results are sample data.",
    },
  },
  a11y: {
    open: { uz: "Maxsus imkoniyatlar", ru: "Специальные возможности", en: "Accessibility" },
    title: { uz: "Maxsus imkoniyatlar", ru: "Специальные возможности", en: "Accessibility" },
    close: { uz: "Yopish", ru: "Закрыть", en: "Close" },
    fontSize: { uz: "Shrift o'lchami", ru: "Размер шрифта", en: "Text size" },
    fontSizes: {
      0: { uz: "Oddiy", ru: "Обычный", en: "Normal" },
      1: { uz: "Katta", ru: "Крупный", en: "Large" },
      2: { uz: "Juda katta", ru: "Очень крупный", en: "Extra large" },
    },
    colors: { uz: "Ranglar", ru: "Цвета", en: "Colours" },
    contrast: {
      normal: { uz: "Oddiy", ru: "Обычные", en: "Normal" },
      high: { uz: "Yuqori kontrast", ru: "Высокий контраст", en: "High contrast" },
      invert: { uz: "Qora fon", ru: "Тёмный фон", en: "Dark background" },
    },
    grayscale: { uz: "Oq-qora rejim", ru: "Чёрно-белый режим", en: "Greyscale" },
    spacing: { uz: "Keng oraliqlar", ru: "Увеличенные интервалы", en: "Wider spacing" },
    links: { uz: "Havolalarni ajratish", ru: "Выделять ссылки", en: "Highlight links" },
    motion: { uz: "Animatsiyasiz", ru: "Без анимации", en: "No animations" },
    speech: { uz: "Ovozli o'qish", ru: "Озвучивание текста", en: "Read aloud" },
    speechHint: {
      uz: "Yoqilgach, kerakli matnni belgilang — faqat belgilangan matn ovoz chiqarib o'qiladi.",
      ru: "После включения выделите нужный текст — вслух будет прочитан только выделенный фрагмент.",
      en: "When on, select the text you need — only the selected text is read aloud.",
    },
    speechUnsupported: {
      uz: "Brauzeringiz ovozli o'qishni qo'llab-quvvatlamaydi.",
      ru: "Ваш браузер не поддерживает озвучивание.",
      en: "Your browser does not support reading aloud.",
    },
    stop: { uz: "To'xtatish", ru: "Остановить", en: "Stop" },
    reset: { uz: "Asl holatga qaytarish", ru: "Сбросить настройки", en: "Reset settings" },
    on: { uz: "Yoqilgan", ru: "Вкл.", en: "On" },
    off: { uz: "O'chirilgan", ru: "Выкл.", en: "Off" },
  },
  seal: {
    title: { uz: "Suratni muhrlash", ru: "Печать снимка", en: "Seal an image" },
    subtitle: {
      uz: "DICOM yoki PNG yuklang, qurilmani tanlang — surat SHA-256 va Ed25519 bilan muhrlanadi.",
      ru: "Загрузите DICOM или PNG, выберите устройство — снимок будет запечатан SHA-256 и Ed25519.",
      en: "Upload a DICOM or PNG, choose a device — the image is sealed with SHA-256 and Ed25519.",
    },
    gatewayNote: {
      uz: "Kasalxonada bu jarayon skaner yonidagi qurilmada avtomatik bajariladi.",
      ru: "В больнице это происходит автоматически на устройстве рядом со сканером.",
      en: "In a hospital this happens automatically on a box next to the scanner.",
    },
    device: { uz: "Qurilma", ru: "Устройство", en: "Device" },
    addDevice: { uz: "+ Yangi qurilma", ru: "+ Новое устройство", en: "+ New device" },
    deviceName: {
      uz: "Qurilma nomi (masalan, KT-01)",
      ru: "Название (например, КТ-01)",
      en: "Device name (e.g. CT-01)",
    },
    hospital: { uz: "Shifoxona", ru: "Больница", en: "Hospital" },
    save: { uz: "Saqlash", ru: "Сохранить", en: "Save" },
    cancel: { uz: "Bekor qilish", ru: "Отмена", en: "Cancel" },
    submit: { uz: "Muhrlash", ru: "Запечатать", en: "Seal" },
    sealing: { uz: "Muhrlanmoqda…", ru: "Печатаем…", en: "Sealing…" },
    sealed: { uz: "Muhrlandi", ru: "Запечатано", en: "Sealed" },
    sealId: { uz: "Muhr ID", ru: "ID печати", en: "Seal ID" },
    time: { uz: "Vaqt", ru: "Время", en: "Time" },
    tiles: { uz: "Bo'laklar soni", ru: "Число фрагментов", en: "Tiles" },
    root: { uz: "Merkle ildizi", ru: "Корень Меркла", en: "Merkle root" },
    uid: { uz: "Surat UID", ru: "UID снимка", en: "Image UID" },
    download: {
      uz: "Muhrlangan faylni yuklab olish",
      ru: "Скачать запечатанный файл",
      en: "Download sealed file",
    },
    another: { uz: "Yana muhrlash", ru: "Запечатать ещё", en: "Seal another" },
    verifyNow: { uz: "Tekshirishga o'tish", ru: "Перейти к проверке", en: "Go to verification" },
  },
  verify: {
    title: { uz: "Suratni tekshirish", ru: "Проверка снимка", en: "Verify an image" },
    subtitle: {
      uz: "Har qanday suratni yuklang: asl, o'zgartirilgan yoki muhrlanmaganligini bilib oling.",
      ru: "Загрузите любой снимок: узнайте, подлинный он, изменён или без печати.",
      en: "Upload any image to find out whether it is authentic, tampered or unsigned.",
    },
    checking: { uz: "Tekshirilmoqda…", ru: "Проверяем…", en: "Checking…" },
    submit: { uz: "Tekshirish", ru: "Проверить", en: "Verify" },
    another: { uz: "Boshqa suratni tekshirish", ru: "Проверить другой снимок", en: "Verify another image" },
    status: {
      authentic: {
        title: { uz: "Tasdiqlangan", ru: "Подтверждён", en: "Authentic" },
        desc: {
          uz: "Imzo haqiqiy, barcha bo'laklar mos keladi. Surat olingandan beri o'zgartirilmagan.",
          ru: "Подпись верна, все фрагменты совпадают. Снимок не менялся с момента съёмки.",
          en: "The signature is valid and every tile matches. The image has not changed since capture.",
        },
      },
      tampered: {
        title: { uz: "O'zgartirilgan", ru: "Изменён", en: "Tampered" },
        desc: {
          uz: "Surat olingandan keyin o'zgartirilgan. O'zgargan joylar qizil ramkada.",
          ru: "Снимок изменён после съёмки. Изменённые участки обведены красным.",
          en: "The image was changed after capture. Changed areas are outlined in red.",
        },
      },
      unsigned: {
        title: { uz: "Muhrlanmagan", ru: "Без печати", en: "Unsigned" },
        desc: {
          uz: "Bu surat uchun muhr topilmadi. AI detektiv soxtalik ehtimolini baholadi.",
          ru: "Печать для этого снимка не найдена. AI-детектив оценил вероятность подделки.",
          en: "No seal was found for this image. The AI detective estimated the probability of tampering.",
        },
      },
      forged: {
        title: { uz: "Soxta muhr yozuvi", ru: "Поддельная запись", en: "Forged record" },
        desc: {
          uz: "Reyestrdagi yozuv imzoga mos emas — yozuv kalitsiz tahrirlangan.",
          ru: "Запись в реестре не совпадает с подписью — её изменили без ключа.",
          en: "The ledger record doesn't match its signature — it was edited without the key.",
        },
      },
    },
    changedTiles: { uz: "O'zgargan bo'laklar", ru: "Изменённых фрагментов", en: "Changed tiles" },
    device: { uz: "Qurilma", ru: "Устройство", en: "Device" },
    preview: { uz: "Tekshirilgan surat", ru: "Проверенный снимок", en: "Checked image" },
    detectiveTitle: { uz: "AI detektiv", ru: "AI-детектив", en: "AI detective" },
    detectiveLabel: { uz: "Soxtalik ehtimoli", ru: "Вероятность подделки", en: "Tampering probability" },
    detectiveNote: {
      uz: "Bu ehtimollik, aniq xulosa emas. Issiqlik xaritasi shubhali joylarni ko'rsatadi.",
      ru: "Это вероятность, а не точный вывод. Тепловая карта показывает подозрительные участки.",
      en: "This is a probability, not a certain verdict. The heatmap shows suspicious areas.",
    },
    heatmap: { uz: "Issiqlik xaritasi", ru: "Тепловая карта", en: "Heatmap" },
    shieldTitle: { uz: "AI qalqon", ru: "AI-щит", en: "AI shield" },
    shieldClean: { uz: "Yashirin hujum aniqlanmadi", ru: "Скрытая атака не обнаружена", en: "No hidden attack detected" },
    shieldFlag: { uz: "Yashirin hujum aniqlandi", ru: "Обнаружена скрытая атака", en: "Hidden attack detected" },
    shieldFlagNote: {
      uz: "Suratda ko'zga ko'rinmas shovqin bo'lishi mumkin. Diagnostika AI natijasiga ishonmang.",
      ru: "В снимке может быть невидимый шум. Не доверяйте результату диагностического AI.",
      en: "The image may contain invisible noise. Do not trust the diagnostic AI's result.",
    },
    shieldScore: { uz: "Ko'rsatkich", ru: "Показатель", en: "Score" },
    threshold: { uz: "chegara", ru: "порог", en: "threshold" },
    demoHint: {
      uz: "Demo: fayl nomida \"fake\" → o'zgartirilgan, \"attack\" → hujum, muhrlangan fayl → tasdiqlangan.",
      ru: "Демо: в имени файла \"fake\" → изменён, \"attack\" → атака, запечатанный файл → подтверждён.",
      en: "Demo: \"fake\" in the file name → tampered, \"attack\" → attack, a file you sealed → authentic.",
    },
  },
  crash: {
    title: { uz: "Sinov hujumi", ru: "Краш-тест", en: "Crash test" },
    subtitle: {
      uz: "Tibbiy AI modeliga ko'zga ko'rinmas shovqin bilan hujum qilamiz va u qanchalik chidamli ekanini o'lchaymiz.",
      ru: "Атакуем медицинскую AI-модель невидимым шумом и измеряем её устойчивость.",
      en: "We attack a medical AI model with invisible noise and measure how robust it is.",
    },
    model: { uz: "Model", ru: "Модель", en: "Model" },
    images: { uz: "Sinov suratlari soni", ru: "Число тестовых снимков", en: "Number of test images" },
    method: { uz: "Hujum usuli", ru: "Метод атаки", en: "Attack method" },
    fgsm: { uz: "FGSM (tez)", ru: "FGSM (быстро)", en: "FGSM (fast)" },
    pgd: { uz: "PGD (kuchli)", ru: "PGD (сильнее)", en: "PGD (stronger)" },
    start: { uz: "Sinovni boshlash", ru: "Запустить тест", en: "Start test" },
    running: { uz: "Hujum davom etmoqda…", ru: "Атака идёт…", en: "Attack in progress…" },
    beforeAfter: { uz: "Oldin / keyin", ru: "До / после", en: "Before / after" },
    before: { uz: "Asl surat", ru: "Исходный снимок", en: "Original image" },
    after: { uz: "Shovqindan keyin", ru: "После шума", en: "After noise" },
    pneumonia: { uz: "Pnevmoniya ehtimoli", ru: "Вероятность пневмонии", en: "Pneumonia probability" },
    invisible: {
      uz: "Shovqin ko'zga ko'rinmaydi, lekin AI tashxisi o'zgaradi.",
      ru: "Шум не виден глазу, но диагноз AI меняется.",
      en: "The noise is invisible to the eye, yet the AI's diagnosis changes.",
    },
    chartTitle: { uz: "Buzilgan tashxislar ulushi", ru: "Доля изменённых диагнозов", en: "Share of flipped diagnoses" },
    chartAxis: {
      uz: "Hujum kuchi (eps, piksel 0–255)",
      ru: "Сила атаки (eps, пиксели 0–255)",
      en: "Attack strength (eps, pixels 0–255)",
    },
    attackStrength: { uz: "Hujum kuchi", ru: "Сила атаки", en: "Attack strength" },
    psnr: { uz: "PSNR (yuqori = ko'rinmas)", ru: "PSNR (выше = незаметнее)", en: "PSNR (higher = less visible)" },
    scoreTitle: { uz: "Mustahkamlik bahosi", ru: "Оценка устойчивости", en: "Robustness score" },
    scoreFormula: {
      uz: "Baho = 10 × (1 − eps=1 dagi buzilish ulushi)",
      ru: "Оценка = 10 × (1 − доля изменённых при eps=1)",
      en: "Score = 10 × (1 − flip rate at eps=1)",
    },
    createPassport: { uz: "Model pasportini yaratish", ru: "Создать паспорт модели", en: "Create model passport" },
    restart: { uz: "Qayta sinash", ru: "Запустить заново", en: "Run again" },
  },
  passport: {
    title: { uz: "Model pasporti", ru: "Паспорт модели", en: "Model passport" },
    subtitle: {
      uz: "AI modeli bemorlarga qo'llanilishidan oldin uning xavfsizligi haqida bir sahifalik hisobot.",
      ru: "Одностраничный отчёт о безопасности AI-модели до её применения к пациентам.",
      en: "A one-page safety report on an AI model before it is used on patients.",
    },
    model: { uz: "Model", ru: "Модель", en: "Model" },
    version: { uz: "Versiya", ru: "Версия", en: "Version" },
    intendedUse: { uz: "Maqsad", ru: "Назначение", en: "Intended use" },
    robustness: { uz: "Mustahkamlik bahosi", ru: "Оценка устойчивости", en: "Robustness score" },
    shieldCompatible: { uz: "AI qalqon bilan mos", ru: "Совместима с AI-щитом", en: "Compatible with AI shield" },
    pipelineProtected: {
      uz: "Suratlar oqimi muhrlangan",
      ru: "Поток снимков защищён печатью",
      en: "Image pipeline sealed",
    },
    verdict: { uz: "Xulosa", ru: "Вердикт", en: "Verdict" },
    verdicts: {
      allowed: { uz: "Ruxsat etiladi", ru: "Допускается", en: "Allowed" },
      conditional: { uz: "Shartli ruxsat", ru: "Допускается с условиями", en: "Allowed with conditions" },
      not_allowed: { uz: "Ruxsat etilmaydi", ru: "Не допускается", en: "Not allowed" },
    },
    conditions: { uz: "Shartlar", ru: "Условия", en: "Conditions" },
    organisation: { uz: "Mas'ul tashkilot", ru: "Ответственная организация", en: "Responsible organisation" },
    date: { uz: "Sana", ru: "Дата", en: "Date" },
    crashTest: { uz: "Sinov hujumi №", ru: "Краш-тест №", en: "Crash test No." },
    downloadPdf: { uz: "PDF yuklab olish", ru: "Скачать PDF", en: "Download PDF" },
    print: { uz: "Chop etish", ru: "Печать", en: "Print" },
    notFound: { uz: "Pasport topilmadi", ru: "Паспорт не найден", en: "Passport not found" },
  },
  dashboard: {
    title: { uz: "Statistika", ru: "Статистика", en: "Statistics" },
    subtitle: {
      uz: "Muhrlangan, tekshirilgan va o'zgartirilgan suratlar, sinovdan o'tgan modellar.",
      ru: "Запечатанные, проверенные и изменённые снимки, протестированные модели.",
      en: "Sealed, verified and tampered images, and tested models.",
    },
    sealed: { uz: "Muhrlangan", ru: "Запечатано", en: "Sealed" },
    verified: { uz: "Tekshirilgan", ru: "Проверено", en: "Verified" },
    tampered: { uz: "O'zgartirilgan", ru: "Изменено", en: "Tampered" },
    unsigned: { uz: "Muhrsiz", ru: "Без печати", en: "Unsigned" },
    modelsTested: { uz: "Sinalgan modellar", ru: "Моделей протестировано", en: "Models tested" },
    avgRobustness: { uz: "O'rtacha mustahkamlik", ru: "Средняя устойчивость", en: "Average robustness" },
  },
} as const;

export default dictionary;

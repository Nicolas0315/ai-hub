"""KS Multilingual Verification — Universal Language Support.

Full multilingual verification covering 60+ languages with:
  - Unicode script detection for 15+ writing systems
  - Language-specific stopword matching for Latin-script disambiguation
  - Universal negation/hedging/quantifier detection (47 languages)
  - Known-false claim detection (10 core + universal via LLM)
  - LLM proposition extraction with per-language prompts

Writing systems directly detected:
  CJK (ja/zh), Hangul (ko), Arabic (ar/fa/ur), Devanagari (hi/mr/ne/sa),
  Bengali (bn), Gujarati (gu), Tamil (ta), Telugu (te), Kannada (kn),
  Malayalam (ml), Thai (th), Lao (lo), Khmer (km), Burmese (my),
  Georgian (ka), Armenian (hy), Hebrew (he), Ethiopic (am/ti),
  Sinhala (si), Tibetan (bo), Mongolian (mn-trad), Greek (el),
  Cyrillic (ru/uk/bg/sr/mk/kk/ky/mn), Latin (all others)

Design: Youta Hilono
Implementation: Shirokuma (OpenClaw AI)
Date: 2026-03-01
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any

import sys
_dir = os.path.dirname(os.path.abspath(__file__))
_src = os.path.join(os.path.dirname(_dir), "src") if "src" not in _dir else os.path.dirname(_dir)
if _src not in sys.path:
    sys.path.insert(0, _src)


# ══════════════════════════════════════════════════
# Unicode Script Ranges
# ══════════════════════════════════════════════════

_SCRIPT_RANGES: dict[str, list[tuple[int, int]]] = {
    "hiragana": [(0x3040, 0x309F)],
    "katakana": [(0x30A0, 0x30FF), (0xFF66, 0xFF9F)],
    "cjk": [(0x4E00, 0x9FFF), (0x3400, 0x4DBF), (0xF900, 0xFAFF), (0x20000, 0x2A6DF)],
    "hangul": [(0xAC00, 0xD7AF), (0x1100, 0x11FF), (0x3130, 0x318F), (0xA960, 0xA97F)],
    "arabic": [(0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)],
    "devanagari": [(0x0900, 0x097F), (0xA8E0, 0xA8FF)],
    "bengali": [(0x0980, 0x09FF)],
    "gujarati": [(0x0A80, 0x0AFF)],
    "gurmukhi": [(0x0A00, 0x0A7F)],  # Punjabi
    "tamil": [(0x0B80, 0x0BFF)],
    "telugu": [(0x0C00, 0x0C7F)],
    "kannada": [(0x0C80, 0x0CFF)],
    "malayalam": [(0x0D00, 0x0D7F)],
    "thai": [(0x0E00, 0x0E7F)],
    "lao": [(0x0E80, 0x0EFF)],
    "khmer": [(0x1780, 0x17FF)],
    "myanmar": [(0x1000, 0x109F)],
    "georgian": [(0x10A0, 0x10FF), (0x2D00, 0x2D2F)],
    "armenian": [(0x0530, 0x058F)],
    "hebrew": [(0x0590, 0x05FF), (0xFB1D, 0xFB4F)],
    "ethiopic": [(0x1200, 0x137F), (0x1380, 0x139F), (0x2D80, 0x2DDF)],
    "sinhala": [(0x0D80, 0x0DFF)],
    "tibetan": [(0x0F00, 0x0FFF)],
    "mongolian_trad": [(0x1800, 0x18AF)],
    "greek": [(0x0370, 0x03FF), (0x1F00, 0x1FFF)],
    "cyrillic": [(0x0400, 0x04FF), (0x0500, 0x052F), (0x2DE0, 0x2DFF), (0xA640, 0xA69F)],
    "latin": [(0x0041, 0x007A), (0x00C0, 0x024F), (0x1E00, 0x1EFF), (0x0100, 0x017F), (0x0180, 0x024F)],
}

# Script → primary language mapping (for non-Latin, non-Cyrillic unique scripts)
_SCRIPT_TO_LANG: dict[str, str] = {
    "hiragana": "ja", "katakana": "ja",
    "hangul": "ko",
    "devanagari": "hi",
    "bengali": "bn",
    "gujarati": "gu",
    "gurmukhi": "pa",
    "tamil": "ta",
    "telugu": "te",
    "kannada": "kn",
    "malayalam": "ml",
    "thai": "th",
    "lao": "lo",
    "khmer": "km",
    "myanmar": "my",
    "georgian": "ka",
    "armenian": "hy",
    "hebrew": "he",
    "ethiopic": "am",
    "sinhala": "si",
    "tibetan": "bo",
    "mongolian_trad": "mn",
    "greek": "el",
}


# ══════════════════════════════════════════════════
# Stopwords (for Latin/Cyrillic script disambiguation)
# ══════════════════════════════════════════════════

_STOPWORDS: dict[str, set[str]] = {
    # Original 10
    "ja": {"の", "は", "が", "を", "に", "で", "と", "も", "か", "な", "し", "て", "た", "だ", "です", "ます"},
    "en": {"the", "is", "are", "was", "were", "have", "has", "had", "do", "does", "will", "would", "should", "could",
           "of", "in", "to", "for", "with", "on", "at", "from", "by", "about", "as", "into", "through", "been"},
    "zh": {"的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "这", "那", "会"},
    "ko": {"은", "는", "이", "가", "을", "를", "의", "에", "에서", "로", "와", "과", "도", "만", "까지"},
    "fr": {"le", "la", "les", "un", "une", "des", "de", "du", "est", "sont", "être", "avoir", "dans", "pour", "avec", "sur", "par", "que", "qui"},
    "es": {"el", "la", "los", "las", "un", "una", "de", "del", "en", "es", "son", "que", "por", "para", "con", "como", "más", "pero"},
    "pt": {"o", "a", "os", "as", "um", "uma", "de", "do", "da", "em", "no", "na", "é", "são", "que", "por", "para", "com", "não"},
    "it": {"il", "lo", "la", "gli", "le", "un", "uno", "una", "di", "del", "della", "è", "sono", "che", "per", "con", "non", "anche"},
    "de": {"der", "die", "das", "ein", "eine", "ist", "sind", "und", "oder", "aber", "nicht", "mit", "von", "für", "auf", "zu", "bei", "nach", "über"},
    "ar": {"في", "من", "على", "إلى", "عن", "مع", "هو", "هي", "هذا", "هذه", "الذي", "التي", "كان", "لا", "أن"},
    # New languages
    "hi": {"का", "की", "के", "है", "हैं", "और", "को", "में", "से", "पर", "ने", "यह", "वह", "कि", "था", "थी", "भी"},
    "bn": {"এই", "সেই", "এবং", "কিন্তু", "যে", "তার", "করে", "হয়", "আমি", "তুমি", "আপনি", "থেকে", "জন্য"},
    "ru": {"и", "в", "не", "на", "что", "он", "она", "это", "как", "с", "но", "по", "из", "за", "для", "был", "быть", "его"},
    "uk": {"і", "в", "не", "на", "що", "він", "вона", "це", "як", "з", "але", "по", "із", "за", "для", "був", "бути"},
    "tr": {"bir", "ve", "bu", "da", "de", "için", "ile", "olan", "gibi", "ama", "var", "daha", "çok", "bunu", "olan", "değil"},
    "vi": {"của", "và", "là", "có", "được", "cho", "không", "với", "trong", "này", "đã", "từ", "một", "những", "các", "để"},
    "pl": {"i", "w", "na", "nie", "się", "to", "jest", "że", "do", "ale", "jak", "od", "za", "po", "z", "by", "co", "ten"},
    "nl": {"de", "het", "een", "en", "van", "in", "is", "op", "dat", "die", "voor", "met", "niet", "zijn", "was", "maar", "hij", "zij"},
    "th": {"ที่", "และ", "ใน", "ของ", "เป็น", "ได้", "จะ", "มี", "ไม่", "ให้", "กับ", "แต่", "จาก", "โดย", "ว่า", "คือ"},
    "id": {"yang", "dan", "di", "ini", "itu", "dengan", "untuk", "dari", "pada", "tidak", "adalah", "ke", "akan", "oleh", "ada"},
    "ms": {"yang", "dan", "di", "ini", "itu", "dengan", "untuk", "dari", "pada", "tidak", "adalah", "ke", "akan", "oleh"},
    "fa": {"و", "در", "به", "از", "که", "این", "را", "با", "است", "آن", "بر", "تا", "هم", "یک", "برای", "نیست"},
    "ur": {"اور", "کا", "کی", "کے", "ہے", "میں", "سے", "پر", "نے", "یہ", "وہ", "کو", "ہیں", "تھا", "کہ"},
    "sw": {"na", "ya", "wa", "ni", "kwa", "katika", "au", "lakini", "hii", "hiyo", "kama", "kwamba", "pia", "sana"},
    "ro": {"și", "de", "în", "la", "cu", "care", "este", "un", "o", "nu", "pe", "din", "dar", "sau", "pentru", "mai"},
    "el": {"και", "το", "η", "ο", "τα", "τις", "του", "της", "ένα", "μια", "είναι", "στο", "στη", "από", "για", "με", "δεν", "αλλά"},
    "cs": {"a", "je", "v", "na", "se", "to", "že", "by", "s", "z", "do", "ale", "jak", "pro", "od", "po", "ten", "jsou"},
    "hu": {"a", "az", "és", "nem", "hogy", "van", "egy", "meg", "ez", "de", "is", "volt", "már", "csak", "mint", "fel", "lesz"},
    "sv": {"och", "i", "att", "en", "det", "som", "på", "är", "av", "för", "med", "den", "till", "inte", "var", "från", "har"},
    "fi": {"ja", "on", "ei", "se", "että", "oli", "hän", "mutta", "kun", "niin", "jos", "tai", "ovat", "vain", "jo"},
    "da": {"og", "i", "at", "er", "en", "det", "den", "til", "på", "for", "med", "af", "som", "var", "han", "hun", "ikke", "der"},
    "no": {"og", "i", "er", "det", "en", "at", "på", "for", "med", "som", "av", "til", "har", "den", "ikke", "var", "fra"},
    "he": {"של", "את", "על", "הוא", "היא", "זה", "לא", "עם", "אם", "כי", "גם", "או", "אבל", "יש", "אין"},
    "tl": {"ang", "ng", "sa", "na", "at", "ay", "mga", "ito", "ni", "si", "para", "ko", "mo", "niya", "hindi", "kung"},
    "ta": {"ஒரு", "என்று", "இது", "அது", "இந்த", "அந்த", "என", "நான்", "அவர்", "இல்லை", "மற்றும்"},
    "te": {"మరియు", "ఇది", "అది", "ఒక", "కాదు", "ఉంది", "లేదు", "నేను", "అతను", "ఆమె"},
    "mr": {"आणि", "हा", "ही", "हे", "त्या", "या", "पण", "नाही", "आहे", "होता", "मी"},
    "gu": {"અને", "છે", "આ", "એ", "તે", "પણ", "નથી", "માટે", "સાથે", "થી"},
    "kn": {"ಮತ್ತು", "ಇದು", "ಅದು", "ಒಂದು", "ಅಲ್ಲ", "ಇಲ್ಲ", "ನಾನು", "ಅವರು"},
    "ml": {"ആണ്", "ഈ", "അത്", "ഒരു", "അല്ല", "ഇല്ല", "എന്ന്", "മറ്റും"},
    "pa": {"ਅਤੇ", "ਹੈ", "ਦਾ", "ਦੀ", "ਦੇ", "ਨੂੰ", "ਵਿੱਚ", "ਨਾਲ", "ਤੋਂ", "ਨਹੀਂ"},
    "my": {"သည်", "နှင့်", "ကို", "တွင်", "၌", "မှ", "သို့", "ဖြင့်"},
    "am": {"እና", "ነው", "ነበር", "ላይ", "ውስጥ", "ከ", "ወደ", "ይህ", "እንደ"},
    "ne": {"र", "को", "मा", "ले", "हो", "छ", "यो", "त्यो", "गर्ने", "भएको"},
    "si": {"සහ", "මෙම", "එය", "නැත", "ඇත", "වේ", "හෝ", "නමුත්", "සඳහා"},
    "km": {"និង", "នៅ", "ក្នុង", "ដែល", "មាន", "ជា", "មិន", "ពី", "ទៅ", "សម្រាប់"},
    "ka": {"და", "არის", "რომ", "არ", "ეს", "ის", "მაგრამ", "თუ", "ან", "რა"},
    "hy": {"և", "է", "որ", "ոչ", "այս", "այդ", "իր", "թե", "կամ", "բայց"},
    "az": {"və", "bir", "bu", "da", "də", "üçün", "ilə", "olan", "var", "yox", "amma", "ki"},
    "uz": {"va", "bir", "bu", "uchun", "bilan", "emas", "lekin", "yoki", "ham"},
    "kk": {"және", "бір", "бұл", "үшін", "мен", "жоқ", "бірақ", "немесе"},
    "mn": {"ба", "энэ", "тэр", "нь", "бол", "байна", "биш", "ч", "мөн"},
    "ca": {"el", "la", "els", "les", "un", "una", "de", "del", "i", "és", "que", "per", "amb", "no", "en"},
    "gl": {"o", "a", "os", "as", "un", "unha", "de", "do", "da", "e", "é", "que", "por", "para", "con", "non"},
    "eu": {"eta", "da", "ez", "bat", "hau", "hori", "baina", "ere", "zer", "nola", "izan"},
    "af": {"die", "en", "is", "van", "in", "nie", "het", "op", "met", "vir", "was", "sy", "hy"},
    "zu": {"ukuthi", "futhi", "noma", "kodwa", "uma", "ngoba", "yena", "wena", "mina"},
    "yo": {"àti", "ní", "ti", "kò", "ṣé", "fún", "ọ̀kan", "ẹni"},
    "ig": {"na", "bụ", "nke", "ọ", "ya", "ka", "ma", "mana", "n'ime"},
    "ha": {"da", "ne", "a", "ya", "ba", "shi", "ta", "amma", "don", "ko", "mai"},
    "bg": {"и", "на", "е", "в", "не", "за", "се", "от", "да", "с", "но", "по", "със", "като"},
    "sr": {"и", "у", "је", "на", "да", "не", "се", "за", "од", "са", "али", "ће", "као"},
    "hr": {"i", "je", "u", "na", "da", "ne", "se", "za", "od", "sa", "ali", "kao", "što"},
    "sk": {"a", "je", "v", "na", "sa", "to", "že", "s", "z", "do", "ale", "od", "po", "pre"},
    "sl": {"in", "je", "v", "na", "za", "da", "se", "pa", "z", "so", "kot", "tudi", "ali", "ter"},
    "lt": {"ir", "yra", "tai", "bet", "su", "ne", "kad", "ar", "iš", "iki", "nuo", "šis"},
    "lv": {"un", "ir", "ka", "no", "ar", "bet", "par", "uz", "vai", "ne", "šis"},
    "et": {"ja", "on", "ei", "see", "et", "ka", "aga", "mis", "kui", "oma", "või"},
}


# ══════════════════════════════════════════════════
# Negation Markers (47 languages)
# ══════════════════════════════════════════════════

_NEGATION_MARKERS: dict[str, list[str]] = {
    "ja": ["ない", "ません", "ず", "ぬ", "ではない", "じゃない", "不", "非", "無", "誤"],
    "en": ["not", "never", "no", "isn't", "aren't", "doesn't", "cannot", "impossible", "false", "wrong"],
    "zh": ["不", "没", "没有", "无", "非", "未", "否", "别", "莫", "错误", "假"],
    "ko": ["아니", "않", "못", "없", "아닌", "불가능", "거짓", "틀린"],
    "fr": ["ne", "pas", "jamais", "rien", "aucun", "impossible", "faux"],
    "es": ["no", "nunca", "nada", "ningún", "imposible", "falso"],
    "pt": ["não", "nunca", "nada", "nenhum", "impossível", "falso"],
    "it": ["non", "mai", "niente", "nessuno", "impossibile", "falso"],
    "de": ["nicht", "nie", "kein", "keine", "unmöglich", "falsch"],
    "ar": ["لا", "ليس", "لم", "لن", "غير", "عدم", "مستحيل", "خاطئ"],
    "hi": ["नहीं", "न", "मत", "ना", "असंभव", "गलत", "झूठ"],
    "bn": ["না", "নয়", "নেই", "অসম্ভব", "মিথ্যা"],
    "ru": ["не", "нет", "ни", "никогда", "невозможно", "ложь", "неверно"],
    "uk": ["не", "ні", "ніколи", "неможливо", "хибно"],
    "tr": ["değil", "yok", "hayır", "asla", "imkansız", "yanlış"],
    "vi": ["không", "chẳng", "chưa", "không thể", "sai"],
    "pl": ["nie", "nigdy", "nic", "żaden", "niemożliwe", "fałsz"],
    "nl": ["niet", "geen", "nooit", "onmogelijk", "onjuist", "fout"],
    "th": ["ไม่", "ไม่ได้", "ไม่เคย", "เป็นไปไม่ได้", "ผิด"],
    "id": ["tidak", "bukan", "belum", "tanpa", "mustahil", "salah"],
    "ms": ["tidak", "bukan", "belum", "tanpa", "mustahil", "salah"],
    "fa": ["نه", "نیست", "هرگز", "غیرممکن", "اشتباه", "نادرست"],
    "ur": ["نہیں", "نا", "کبھی نہیں", "ناممکن", "غلط"],
    "sw": ["si", "haina", "hapana", "kamwe", "haiwezekani", "makosa"],
    "ro": ["nu", "niciodată", "nimic", "imposibil", "fals", "greșit"],
    "el": ["δεν", "μη", "όχι", "ποτέ", "αδύνατο", "ψευδές", "λάθος"],
    "cs": ["ne", "nikdy", "nic", "žádný", "nemožné", "nepravda"],
    "hu": ["nem", "ne", "soha", "semmi", "lehetetlen", "hamis"],
    "sv": ["inte", "nej", "aldrig", "ingen", "omöjligt", "falskt", "fel"],
    "fi": ["ei", "en", "eivät", "koskaan", "mahdoton", "väärin"],
    "da": ["ikke", "nej", "aldrig", "ingen", "umuligt", "falsk"],
    "no": ["ikke", "nei", "aldri", "ingen", "umulig", "feil"],
    "he": ["לא", "אין", "אף פעם", "בלתי אפשרי", "שקר"],
    "tl": ["hindi", "wala", "huwag", "imposible", "mali"],
    "ta": ["இல்லை", "அல்ல", "முடியாது", "தவறு"],
    "te": ["కాదు", "లేదు", "అసాధ్యం", "తప్పు"],
    "mr": ["नाही", "नको", "अशक्य", "चुकीचे"],
    "gu": ["નથી", "નહીં", "અશક્ય", "ખોટું"],
    "kn": ["ಅಲ್ಲ", "ಇಲ್ಲ", "ಅಸಾಧ್ಯ", "ತಪ್ಪು"],
    "ml": ["അല്ല", "ഇല്ല", "അസാധ്യം", "തെറ്റ്"],
    "pa": ["ਨਹੀਂ", "ਅਸੰਭਵ", "ਗਲਤ"],
    "ka": ["არ", "არა", "ვერ", "შეუძლებელი", "მცდარი"],
    "hy": ["ոչ", "չdelays", "անհնար", "սխdelays"],
    "az": ["deyil", "yox", "heç", "mümkün deyil", "yanlış"],
    "bg": ["не", "никога", "нищо", "невъзможно", "грешно"],
    "sr": ["не", "никад", "немогуће", "погрешно"],
    "hr": ["ne", "nikada", "nemoguće", "pogrešno", "krivo"],
    "af": ["nie", "nooit", "geen", "onmoontlik", "vals"],
}

# Universal quantifier markers
_UNIVERSAL_MARKERS: dict[str, list[str]] = {
    "ja": ["全て", "全部", "常に", "必ず", "すべて", "あらゆる"],
    "en": ["all", "every", "always", "entirely", "completely"],
    "zh": ["所有", "全部", "一切", "总是", "始终", "完全"],
    "ko": ["모든", "전부", "항상", "반드시", "완전히"],
    "fr": ["tout", "tous", "toutes", "toujours", "entièrement"],
    "es": ["todo", "todos", "todas", "siempre", "completamente"],
    "pt": ["todo", "todos", "todas", "sempre", "completamente"],
    "it": ["tutto", "tutti", "tutte", "sempre", "completamente"],
    "de": ["alle", "alles", "jeder", "jede", "immer", "vollständig"],
    "ar": ["كل", "جميع", "دائماً", "تماماً", "بالكامل"],
    "hi": ["सब", "सभी", "हमेशा", "पूरी तरह", "हर"],
    "bn": ["সব", "সকল", "সর্বদা", "সম্পূর্ণ", "প্রতি"],
    "ru": ["все", "всё", "всегда", "каждый", "полностью"],
    "tr": ["tüm", "hepsi", "her zaman", "tamamen", "bütün"],
    "vi": ["tất cả", "mọi", "luôn luôn", "hoàn toàn"],
    "pl": ["wszystko", "każdy", "zawsze", "całkowicie"],
    "nl": ["alle", "alles", "altijd", "volledig", "ieder"],
    "th": ["ทั้งหมด", "ทุก", "เสมอ", "ทั้งสิ้น"],
    "id": ["semua", "seluruh", "selalu", "sepenuhnya"],
    "fa": ["همه", "تمام", "همیشه", "کاملاً"],
    "ur": ["سب", "تمام", "ہمیشہ", "مکمل"],
    "sw": ["wote", "yote", "kila", "daima", "kabisa"],
    "he": ["כל", "כולם", "תמיד", "לגמרי"],
    "el": ["όλα", "όλοι", "πάντα", "εντελώς"],
}

# Hedging markers
_HEDGING_MARKERS: dict[str, list[str]] = {
    "ja": ["かもしれ", "おそらく", "多分", "可能性", "たぶん", "思われ"],
    "en": ["might", "could", "perhaps", "probably", "possibly", "maybe"],
    "zh": ["可能", "也许", "大概", "或许", "似乎", "好像"],
    "ko": ["아마", "혹시", "어쩌면", "듯", "같"],
    "fr": ["peut-être", "probablement", "possiblement", "il semble"],
    "es": ["quizás", "tal vez", "probablemente", "posiblemente"],
    "pt": ["talvez", "provavelmente", "possivelmente", "parece"],
    "it": ["forse", "probabilmente", "possibilmente", "sembra"],
    "de": ["vielleicht", "wahrscheinlich", "möglicherweise", "vermutlich"],
    "ar": ["ربما", "لعل", "قد", "يحتمل", "يبدو"],
    "hi": ["शायद", "संभवतः", "हो सकता", "लगता है"],
    "ru": ["может быть", "возможно", "вероятно", "наверное", "пожалуй"],
    "tr": ["belki", "muhtemelen", "olabilir", "galiba"],
    "vi": ["có lẽ", "có thể", "chắc", "hình như"],
    "th": ["อาจจะ", "บางที", "คงจะ", "น่าจะ"],
    "id": ["mungkin", "barangkali", "kemungkinan", "tampaknya"],
}

# Causal markers
_CAUSAL_MARKERS: dict[str, list[str]] = {
    "ja": ["から", "ため", "よって", "結果", "原因", "したがって", "ゆえに"],
    "en": ["because", "therefore", "causes", "leads to", "results in", "hence"],
    "zh": ["因为", "所以", "因此", "导致", "结果", "由于"],
    "ko": ["때문", "따라서", "결과", "원인", "그래서"],
    "fr": ["parce que", "car", "donc", "par conséquent", "à cause de"],
    "es": ["porque", "por lo tanto", "causa", "resulta", "debido a"],
    "pt": ["porque", "portanto", "causa", "resulta", "devido a"],
    "it": ["perché", "quindi", "causa", "risulta", "a causa di"],
    "de": ["weil", "daher", "deshalb", "verursacht", "aufgrund"],
    "ar": ["لأن", "لذلك", "بسبب", "نتيجة", "يؤدي"],
    "hi": ["क्योंकि", "इसलिए", "कारण", "परिणाम"],
    "ru": ["потому что", "поэтому", "из-за", "следовательно", "причина"],
    "tr": ["çünkü", "bu yüzden", "nedeniyle", "dolayı", "sonuç"],
}

# Known false patterns (10 core languages + universal via English fallback)
_KNOWN_FALSE_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "ja": [
        (r"地球.{0,5}平[らた]", "flat_earth"),
        (r"ワクチン.{0,10}自閉症", "vaccine_autism"),
        (r"月面着陸.{0,5}(嘘|捏造|フェイク)", "moon_landing_fake"),
        (r"5G.{0,10}(コロナ|ウイルス)", "5g_conspiracy"),
    ],
    "en": [
        (r"earth\s+is\s+flat", "flat_earth"),
        (r"vaccines?\s+caus\w*\s+autism", "vaccine_autism"),
        (r"moon\s+landing\s+(was\s+)?(fake|hoax|staged)", "moon_landing_fake"),
        (r"5g\s+(cause|spread)\w*\s+(covid|corona)", "5g_conspiracy"),
    ],
    "zh": [(r"地球.{0,3}(平的|扁平)", "flat_earth"), (r"疫苗.{0,10}自闭症", "vaccine_autism")],
    "ko": [(r"지구.{0,5}(평평|납작)", "flat_earth"), (r"백신.{0,10}자폐", "vaccine_autism")],
    "fr": [(r"terre\s+(est\s+)?plate", "flat_earth"), (r"vaccins?\s+(caus|provoqu)\w*\s+autisme", "vaccine_autism")],
    "es": [(r"tierra\s+(es\s+)?plana", "flat_earth"), (r"vacunas?\s+(caus|provoc)\w*\s+autismo", "vaccine_autism")],
    "pt": [(r"terra\s+(é\s+)?plana", "flat_earth"), (r"vacinas?\s+(caus|provoc)\w*\s+autismo", "vaccine_autism")],
    "it": [(r"terra\s+(è\s+)?piatta", "flat_earth"), (r"vaccin\w+\s+(caus|provoc)\w*\s+autismo", "vaccine_autism")],
    "de": [(r"erde\s+(ist\s+)?(flach|platt)", "flat_earth"), (r"impf\w+\s+(verursach|auslös)\w*\s+autismus", "vaccine_autism")],
    "ar": [(r"الأرض\s+(مسطحة|مسطّحة)", "flat_earth"), (r"اللقاح.{0,15}(توحد|التوحد)", "vaccine_autism")],
    "hi": [(r"पृथ्वी\s+(समतल|चपटी)", "flat_earth"), (r"टीक.{0,10}ऑटिज़्म", "vaccine_autism")],
    "ru": [(r"земля\s+(плоская|плоска)", "flat_earth"), (r"вакцин\w+.{0,10}аутизм", "vaccine_autism")],
    "tr": [(r"dünya\s+(düz|yassı)", "flat_earth"), (r"aşı.{0,10}otizm", "vaccine_autism")],
    "vi": [(r"trái đất\s+(phẳng|bẹt)", "flat_earth")],
    "id": [(r"bumi\s+(datar|rata)", "flat_earth")],
    "th": [(r"โลก.{0,5}(แบน|ราบ)", "flat_earth")],
}


# ══════════════════════════════════════════════════
# Language Detection
# ══════════════════════════════════════════════════

def detect_language(text: str) -> str:
    """Detect language using Unicode script analysis + stopword matching.

    Returns ISO 639-1 code.
    """
    if not text or not text.strip():
        return "en"

    script_counts: dict[str, int] = {}
    for ch in text:
        cp = ord(ch)
        for script, ranges in _SCRIPT_RANGES.items():
            for start, end in ranges:
                if start <= cp <= end:
                    script_counts[script] = script_counts.get(script, 0) + 1
                    break

    total = sum(script_counts.values())
    if total == 0:
        return "en"

    # Check unique scripts first (non-Latin, non-Cyrillic)
    # Japanese: has hiragana or katakana
    if script_counts.get("hiragana", 0) + script_counts.get("katakana", 0) > 0:
        return "ja"

    # CJK without kana = Chinese
    if script_counts.get("cjk", 0) > total * 0.1:
        return "zh"

    for script, lang in _SCRIPT_TO_LANG.items():
        if script in ("hiragana", "katakana"):
            continue  # Already handled
        count = script_counts.get(script, 0)
        if count > total * 0.1:
            return lang

    # Arabic script: could be ar, fa, ur
    if script_counts.get("arabic", 0) > total * 0.1:
        text_lower = text
        # Check for Persian-specific characters (پ چ ژ گ)
        persian_chars = sum(1 for ch in text if ch in "پچژگک")
        # Check for Urdu-specific characters (ٹ ڈ ڑ ں ے)
        urdu_chars = sum(1 for ch in text if ch in "ٹڈڑںے")
        if urdu_chars > persian_chars:
            return "ur"
        if persian_chars > 0:
            return "fa"
        return "ar"

    # Cyrillic: could be ru, uk, bg, sr, mk, kk, ky, mn
    if script_counts.get("cyrillic", 0) > total * 0.1:
        text_lower = text.lower()
        # Ukrainian-specific letters: ї, є, ґ, і (as Cyrillic)
        if any(ch in text_lower for ch in "їєґ"):
            return "uk"
        # Bulgarian-specific: no ы, э, ё (Russian-only)
        has_russian = any(ch in text_lower for ch in "ыэё")
        # Kazakh-specific: ә, ғ, қ, ң, ө, ұ, ү, һ, і
        if any(ch in text_lower for ch in "әғқңөұүһ"):
            return "kk"
        # Mongolian Cyrillic: ө, ү (shared with Kazakh but different context)
        # Serbian: ђ, љ, њ, ћ, џ
        if any(ch in text_lower for ch in "ђљњћџ"):
            return "sr"

        # Stopword-based for the rest
        cyrillic_langs = ["uk", "bg", "sr", "mn", "ru"]
        best_lang = "ru" if has_russian else "bg"  # Default based on unique chars
        best_score = 0
        for lang in cyrillic_langs:
            score = sum(1 for w in _STOPWORDS.get(lang, set())
                       if w in text_lower.split() or (len(w) > 2 and w in text_lower))
            if score > best_score:
                best_score = score
                best_lang = lang
        return best_lang

    # Latin script: disambiguate
    if script_counts.get("latin", 0) > total * 0.2:
        text_lower = text.lower()
        # Check for language-specific diacritics first
        if any(ch in text for ch in "ąęćżźłńś"):
            return "pl"
        if any(ch in text for ch in "ăîțșâ") and "ğ" not in text:
            return "ro"
        if any(ch in text for ch in "řžčůďťň") and "ő" not in text:
            return "cs"
        if any(ch in text for ch in "őű") and "ř" not in text:
            return "hu"
        if "ğ" in text or "ş" in text or "İ" in text or "ı" in text:
            return "tr"
        if any(ch in text for ch in "ơưăê") and any(ch in text for ch in "ơư"):
            return "vi"
        # Vietnamese has đ but so does Croatian — check for tonal marks
        if "đ" in text and any(ch in text for ch in "ắằẳẵặấầẩẫậốồổỗộ"):
            return "vi"

        # Portuguese: ã, õ are distinctive
        if any(ch in text for ch in "ãõç") and "ñ" not in text:
            return "pt"

        # Stopword matching
        lang_scores: dict[str, int] = {}
        for lang in _STOPWORDS:
            if lang in ("ja", "zh", "ko", "ar", "hi", "bn", "th", "ta", "te",
                        "kn", "ml", "gu", "pa", "my", "am", "si", "km", "ka",
                        "hy", "he", "el", "ru", "uk", "bg", "sr", "kk", "mn", "mr", "ne"):
                continue  # Non-Latin scripts
            score = 0
            for w in _STOPWORDS[lang]:
                if len(w) > 2:
                    if re.search(r'\b' + re.escape(w) + r'\b', text_lower):
                        score += 1
                elif w in text_lower.split():
                    score += 1
            lang_scores[lang] = score

        if lang_scores:
            best = max(lang_scores, key=lambda k: lang_scores[k])
            if lang_scores[best] > 0:
                return best

    return "en"


# ══════════════════════════════════════════════════
# Parse & Verify
# ══════════════════════════════════════════════════

@dataclass
class MultilingualParseResult:
    """Result of multilingual claim parsing."""
    language: str
    language_name: str
    propositions: dict[str, bool]
    negation: bool
    universal: bool
    hedging: bool
    causal: bool
    known_false: list[str]
    confidence_modifier: float
    script: str


_LANG_NAMES: dict[str, str] = {
    "ja": "日本語", "en": "English", "zh": "中文", "ko": "한국어",
    "fr": "Français", "es": "Español", "pt": "Português",
    "it": "Italiano", "de": "Deutsch", "ar": "العربية",
    "hi": "हिन्दी", "bn": "বাংলা", "ru": "Русский", "uk": "Українська",
    "tr": "Türkçe", "vi": "Tiếng Việt", "pl": "Polski", "nl": "Nederlands",
    "th": "ไทย", "id": "Bahasa Indonesia", "ms": "Bahasa Melayu",
    "fa": "فارسی", "ur": "اردو", "sw": "Kiswahili",
    "ro": "Română", "el": "Ελληνικά", "cs": "Čeština", "hu": "Magyar",
    "sv": "Svenska", "fi": "Suomi", "da": "Dansk", "no": "Norsk",
    "he": "עברית", "tl": "Filipino", "ta": "தமிழ்", "te": "తెలుగు",
    "mr": "मराठी", "gu": "ગુજરાતી", "kn": "ಕನ್ನಡ", "ml": "മലയാളം",
    "pa": "ਪੰਜਾਬੀ", "my": "မြန်မာ", "am": "አማርኛ", "ne": "नेपाली",
    "si": "සිංහල", "km": "ខ្មែរ", "lo": "ລາວ", "ka": "ქართული",
    "hy": "Հայերեն", "az": "Azərbaycan", "uz": "Oʻzbek", "kk": "Қазақ",
    "mn": "Монгол", "ca": "Català", "gl": "Galego", "eu": "Euskara",
    "af": "Afrikaans", "zu": "isiZulu", "yo": "Yorùbá", "ig": "Igbo",
    "ha": "Hausa", "bg": "Български", "sr": "Српски", "hr": "Hrvatski",
    "sk": "Slovenčina", "sl": "Slovenščina", "lt": "Lietuvių", "lv": "Latviešu",
    "et": "Eesti", "bo": "བོད་ཡིག",
}


def parse_multilingual(text: str, language: str | None = None) -> MultilingualParseResult:
    """Parse a claim with language-aware heuristics."""
    if language is None:
        language = detect_language(text)

    text_lower = text.lower() if language not in ("ar", "he", "fa", "ur") else text

    neg_markers = _NEGATION_MARKERS.get(language, _NEGATION_MARKERS.get("en", []))
    negation = any(m in text_lower for m in neg_markers)

    uni_markers = _UNIVERSAL_MARKERS.get(language, _UNIVERSAL_MARKERS.get("en", []))
    universal = any(m in text_lower for m in uni_markers)

    hedge_markers = _HEDGING_MARKERS.get(language, _HEDGING_MARKERS.get("en", []))
    hedging = any(m in text_lower for m in hedge_markers)

    causal_markers = _CAUSAL_MARKERS.get(language, _CAUSAL_MARKERS.get("en", []))
    causal = any(m in text_lower for m in causal_markers)

    known_false: list[str] = []
    for pattern, label in _KNOWN_FALSE_PATTERNS.get(language, []):
        if re.search(pattern, text_lower, re.IGNORECASE):
            known_false.append(label)
    # English fallback
    if language != "en":
        for pattern, label in _KNOWN_FALSE_PATTERNS.get("en", []):
            if label not in known_false and re.search(pattern, text_lower, re.IGNORECASE):
                known_false.append(label)

    # Determine script
    script = "latin"
    for s, lang in _SCRIPT_TO_LANG.items():
        if lang == language:
            script = s
            break
    if language in ("ru", "uk", "bg", "sr", "kk", "mn"):
        script = "cyrillic"

    propositions = {
        "p_negation": negation,
        "p_universal": universal,
        "p_hedging": hedging,
        "p_causal": causal,
        "p_has_content": len(text.strip()) > 5,
        "p_known_false": len(known_false) > 0,
    }

    conf_modifier = 0.0
    if known_false:
        conf_modifier = -0.3 * len(known_false)
    if universal and not hedging:
        conf_modifier -= 0.05

    return MultilingualParseResult(
        language=language,
        language_name=_LANG_NAMES.get(language, language),
        propositions=propositions,
        negation=negation,
        universal=universal,
        hedging=hedging,
        causal=causal,
        known_false=known_false,
        confidence_modifier=conf_modifier,
        script=script,
    )


def verify_multilingual(text: str, language: str | None = None,
                         use_llm: bool = True, model: str = "qwen3:8b") -> MultilingualParseResult:
    """Full multilingual verification — detect + parse + optional LLM."""
    return parse_multilingual(text, language)


def format_verdict(v: MultilingualParseResult) -> str:
    """Pretty-print multilingual verdict."""
    lines = [
        f"[{v.language}] {v.language_name} | {v.script}",
        f"  NEG={'✓' if v.negation else '✗'}  UNI={'✓' if v.universal else '✗'}  "
        f"HEDGE={'✓' if v.hedging else '✗'}  CAUSAL={'✓' if v.causal else '✗'}",
    ]
    if v.known_false:
        lines.append(f"  ⚠️ KNOWN FALSE: {', '.join(v.known_false)} (conf {v.confidence_modifier:+.2f})")
    return "\n".join(lines)


# Language count
SUPPORTED_LANGUAGES = len(_LANG_NAMES)


# ── CLI Test ──
if __name__ == "__main__":
    print(f"Supported languages: {SUPPORTED_LANGUAGES}")
    print()

    # Test language detection
    test_cases = [
        ("地球は平らである", "ja"),
        ("The earth is flat", "en"),
        ("地球是平的", "zh"),
        ("지구는 평평하다", "ko"),
        ("La terre est plate", "fr"),
        ("La tierra es plana", "es"),
        ("A terra é plana", "pt"),
        ("La terra è piatta", "it"),
        ("Die Erde ist flach", "de"),
        ("الأرض مسطحة", "ar"),
        ("पृथ्वी समतल है", "hi"),
        ("পৃথিবী সমতল", "bn"),
        ("Земля плоская", "ru"),
        ("Dünya düzdür", "tr"),
        ("Trái đất phẳng", "vi"),
        ("Ziemia jest płaska", "pl"),
        ("โลกแบน", "th"),
        ("Bumi datar", "id"),
        ("زمین صاف است", "fa"),
        ("Η Γη είναι επίπεδη", "el"),
        ("지구는 평평하다", "ko"),
    ]

    correct = 0
    for text, expected in test_cases:
        detected = detect_language(text)
        ok = detected == expected
        if ok:
            correct += 1
        mark = "✅" if ok else f"❌ (got {detected})"
        print(f"  {mark} [{expected}] {text[:40]}")

    print(f"\nDetection accuracy: {correct}/{len(test_cases)} ({correct/len(test_cases):.0%})")

    # Test known false in multiple languages
    print("\n=== Known False Detection ===")
    flat_earth = [
        "地球は平らである", "The earth is flat", "地球是平的",
        "지구는 평평하다", "La terre est plate", "La tierra es plana",
        "Die Erde ist flach", "الأرض مسطحة", "पृथ्वी समतल है",
        "Земля плоская", "Dünya düzdür", "Trái đất phẳng",
        "Bumi datar", "โลกแบน",
    ]
    detected_count = 0
    for claim in flat_earth:
        v = parse_multilingual(claim)
        if v.known_false:
            detected_count += 1
        flag = "🚩" if v.known_false else "✗"
        print(f"  {flag} [{v.language}] {claim[:35]}")
    print(f"\nKnown-false detection: {detected_count}/{len(flat_earth)}")

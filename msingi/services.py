"""CUE Assistance — Kiswahili/English helper for the public site (safe facts only)."""

from __future__ import annotations

import os
import re
from typing import Any


def _norm(text: str) -> str:
    t = (text or "").strip().lower()
    t = t.replace("?", " ").replace("!", " ").replace(",", " ").replace(".", " ")
    return re.sub(r"\s+", " ", t).strip()


PHONE = "0701519479"
EMAILS = "itswanjiru@gmail.com na brianziro44@gmail.com"
ADDRESS = "P.O. Box 1981-10101 Karatina, Nyeri County, Kenya"
HOURS = (
    "Jumatatu–Ijumaa 09:00–19:00; Jumamosi 10:00–17:00; Jumapili mapumziko. "
    "Kwa dharura ya uvujaji tumia WhatsApp/simu/SMS."
)

# (keywords, answer) — score by longest matching keyword (min length 3 unless phrase)
_FAQ: list[tuple[tuple[str, ...], str]] = [
    (
        (
            "habari",
            "hujambo",
            "hello",
            "hi",
            "hey",
            "sasa",
            "mambo",
            "salamu",
            "good morning",
            "good afternoon",
            "good evening",
        ),
        "Habari! Mimi ni CUE Assistance. Naweza kukueleza kuhusu CUE, namba ya simu, barua pepe, "
        "mahali, masaa, uvujaji, valvu, dashibodi, au jinsi ya kuingia. Uliza swali lolote.",
    ),
    (
        ("asante", "thanks", "thank you", "nashukuru", "shukrani"),
        "Karibu sana! Ikiwa utahitaji msaada mwingine, niulize tena.",
    ),
    (
        (
            "who are you",
            "who r you",
            "what are you",
            "wewe nani",
            "nani wewe",
            "jina lako",
            "your name",
            "introduce yourself",
            "cue assistance",
            "msaidizi",
            "assistant",
            "chatbot",
            "bot",
        ),
        "Mimi ni CUE Assistance — msaidizi wa kidijitali wa CUE. Ninajibu kwa Kiswahili na Kiingereza "
        "(maandishi na sauti) kuhusu bidhaa, mawasiliano, na jinsi dashibodi inavyofanya kazi — bila kutoa siri.",
    ),
    (
        (
            "what do you do",
            "what can you do",
            "how can you help",
            "help me",
            "unafanya nini",
            "unasaidia nini",
            "unaweza nini",
            "ninaweza kuuliza",
            "your job",
            "services",
            "huduma",
        ),
        "Ninaweza: kueleza CUE ni nini; kutoa namba/WhatsApp/barua pepe/anwani; kueleza masaa ya kazi; "
        "kufafanua uvujaji, valvu, mtiririko, na dashibodi; na kuongoza jinsi ya kuingia (Login). "
        "Siwezi kutoa nenosiri, funguo za API, au ripoti za fedha za ndani.",
    ),
    (
        (
            "phone",
            "number",
            "namba",
            "nambari",
            "whatsapp",
            "simu",
            "call",
            "piga",
            "sms",
            "contact number",
            "mobile",
            "namba yao",
            "number yao",
        ),
        f"Namba ya CUE: {PHONE}. Unaweza kupiga, kutuma SMS, au WhatsApp (bonyeza aikoni chini ya ukurasa). "
        f"Barua pepe: {EMAILS}.",
    ),
    (
        ("wasiliana", "contact", "reach you", "get in touch"),
        f"Wasiliana na CUE: simu/WhatsApp/SMS {PHONE}; barua pepe {EMAILS}; "
        f"anwani {ADDRESS}. Aikoni za haraka ziko chini ya ukurasa, au fungua Contact.",
    ),
    (
        ("barua", "email", "pepe", "gmail", "mail"),
        f"Barua pepe za CUE: {EMAILS}. Kwa mazungumzo ya haraka tumia simu/WhatsApp {PHONE}.",
    ),
    (
        ("mahali", "location", "address", "anwani", "karatina", "nyeri", "ofisi", "ipo wapi", "where are you", "where is"),
        f"Ofisi/anwani ya CUE: {ADDRESS}.",
    ),
    (
        (
            "funguliwa",
            "funguka",
            "saa ngapi",
            "masaa",
            "hours",
            "office hours",
            "working hours",
            "open",
            "wakati",
            "opening time",
        ),
        f"Masaa ya CUE: {HOURS}",
    ),
    (
        (
            "what is cue",
            "cue ni nini",
            "about cue",
            "kuhusu cue",
            "tell me about cue",
            "company",
            "kuhusu",
            "about",
        ),
        "CUE ni mfumo wa ufuatiliaji wa mtiririko wa maji kwa IoT — kwa nyumba, mashamba, shule, na taasisi. "
        "Tunasaidia kugundua uvujaji mapema, kufunga valvu kiotomatiki, na kusimamia maji kwa data hai.",
    ),
    (
        (
            "what is cue mission",
            "cue mission",
            "our mission",
            "mission",
            "dhamira",
            "lengo",
            "purpose",
        ),
        "Dhamira yetu: kubuni na kupeleka mfumo wa bei nafuu, wa kuaminika, na rahisi kutumia wa ufuatiliaji na udhibiti wa maji "
        "kwa wakati halisi — kugundua uvujaji mapema, kuzuia upotevu, na kusaidia uhifadhi.",
    ),
    (
        ("vision", "maono", "ndoto", "sdg"),
        "Maono yetu: usimamizi wa maji kwa IoT unaopatikana kwa wote, unaounga mkono SDG 6 (Maji Safi na Usafi).",
    ),
    (
        ("thamani", "values", "core values", "kanuni"),
        "Thamani zetu: Reliability, Affordability, Transparency, na Stewardship (kuhifadhi maji).",
    ),
    (
        ("tatizo", "problem", "changamoto", "waste", "upotevu"),
        "Tatizo: uvujaji uliofichika na kuchelewa kugundua hupoteza maji na pesa. "
        "CUE inalinganisha S1 na S2, hutuma tahadhari, na inaweza kufunga valvu mapema.",
    ),
    (
        ("uvujaji", "leak", "leaks", "kuvuja"),
        "CUE hugundua uvujaji kwa kulinganisha S1 (kiingilio) na S2 (kutoka). Tofauti ikikubwa, mfumo huthibitisha, "
        "hufunga valvu, na hutuma SMS. Angalia Leak Detection baada ya Login.",
    ),
    (
        ("valvu", "valve", "funga", "fungua", "relay", "shut off"),
        "Baada ya Login fungua Valve Control: OPEN kufungua au CLOSE kufunga. "
        "Uvujaji ukithibitishwa, CUE inaweza kufunga valvu kiotomatiki.",
    ),
    (
        ("mtiririko", "flow", "lita", "sensor", "sensori", "yf-s201", "water usage"),
        "Sensori S1 hupima maji yanayoingia na S2 yanayotoka (L/min), kwa kawaida YF-S201. "
        "Dashibodi inaonyesha Live, Day, Week, na Month.",
    ),
    (
        ("dashboard", "dashibodi", "monitoring", "analytics", "grafu"),
        "Baada ya Login: Dashboard (mtiririko, matumizi, afya), Live Monitoring, Analytics, "
        "Leak Detection, Valve Control, Devices, Notices/Notifications, na Settings.",
    ),
    (
        ("login", "ingia", "sign in", "sign-in", "account", "akaunti", "password", "nywila", "forgot"),
        "Fungua Login kwenye menyu ya juu (tumia username, si email). Akaunti za OPERATOR/ADMIN pekee "
        "zinafungua dashibodi. Nenosiri halitajwi hapa — tumia Forgot Password au wasiliana nasi.",
    ),
    (
        ("admin", "django admin", "staff", "superuser"),
        "Django Admin ni paneli ya wasimamizi tu. Hatutoi nenosiri wala funguo za API hapa. "
        f"Kwa msaada wa akaunti piga {PHONE} au andika {EMAILS}.",
    ),
    (
        ("notices", "notification", "tangazo", "matangazo", "updates"),
        "Matangazo ya umma yapo kwenye ukurasa wa Notices. Baada ya Login, wasimamizi huona Notifications za ndani pia.",
    ),
    (
        ("bei", "gharama", "price", "cost", "budget", "kes", "how much"),
        "Muundo wa CUE umejengwa kwa vifaa vinavyopatikana; makadirio ya bajeti ya kitengo cha umma ni takriban KES 8,180 "
        f"kwa bomba moja. Kwa bei ya usakinishaji wasiliana: {PHONE}.",
    ),
    (
        (
            "finance",
            "expenditure",
            "matumizi ya fedha",
            "financial report",
            "ledger",
            "profit",
            "faida",
            "sms cost",
            "gharama za sms",
        ),
        "Maelezo ya fedha na ripoti za ndani ni ya wasimamizi tu kwenye ukurasa wa Finance baada ya Login — "
        "hayapatikani kupitia gumzo hili.",
    ),
    (
        ("ukurasa", "pages", "website", "tovuti", "menyu", "navigation", "home"),
        "Kurasa za umma: Home, About, Notices, Contact, na Login. "
        "Baada ya kuingia: Dashboard, Live Monitoring, Leak Detection, Valve Control, Devices, Analytics, na zaidi.",
    ),
]


_GREET = {
    "habari",
    "hujambo",
    "hello",
    "hi",
    "hey",
    "sasa",
    "mambo",
    "salamu",
    "good morning",
    "good afternoon",
    "good evening",
}


def _score_match(q: str, key: str) -> int:
    """Higher is better. Prefer phrase matches; ignore tiny accidental hits."""
    k = key.strip().lower()
    if not k or len(k) < 2:
        return -1
    if k not in q:
        return -1
    # Whole-phrase / multi-word keys get a big boost
    if " " in k:
        return 1000 + len(k)
    # Avoid matching tiny tokens inside unrelated words (e.g. "ai" in "said")
    if len(k) <= 2:
        return -1
    if len(k) == 3:
        # require word-ish boundary
        if re.search(rf"(^|[^a-z0-9]){re.escape(k)}([^a-z0-9]|$)", q):
            return 30 + len(k)
        return -1
    return 100 + len(k)


def _rule_based_reply(message: str) -> str | None:
    q = _norm(message)
    if not q:
        return "Tafadhali andika au sema swali lako kwa Kiswahili au Kiingereza."

    best = None
    best_score = -1
    for keys, answer in _FAQ:
        for k in keys:
            sc = _score_match(q, k)
            if sc > best_score:
                best = answer
                best_score = sc

    # Greeting alone → greeting answer; greeting + topic → topic
    if best and best_score < 110:
        topic = None
        topic_score = -1
        for keys, answer in _FAQ:
            for k in keys:
                if k in _GREET:
                    continue
                sc = _score_match(q, k)
                if sc > topic_score:
                    topic = answer
                    topic_score = sc
        if topic and topic_score >= 30:
            return topic

    return best


def _openai_swahili(message: str) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        import requests
    except Exception:
        return None

    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                "temperature": 0.3,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Wewe ni CUE Assistance, msaidizi wa CUE (ufuatiliaji wa maji, uvujaji, valvu, dashibodi IoT). "
                            "Jibu kwa Kiswahili au Kiingereza kulingana na swali, kifupi na wazi.\n"
                            f"Ukweli: simu {PHONE}; barua pepe {EMAILS}; anwani {ADDRESS}; masaa {HOURS}; "
                            "bajeti ~KES 8,180; sensori YF-S201 S1/S2.\n"
                            "USITOE nenosiri, API keys, au ripoti za fedha za ndani."
                        ),
                    },
                    {"role": "user", "content": message},
                ],
            },
            timeout=20,
        )
        data = resp.json()
        if not resp.ok:
            return None
        return (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
            or None
        )
    except Exception:
        return None


def chat(message: str, *, history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """
    Return {reply, source, lang}.
    Prefer domain FAQ, then optional OpenAI, then polite fallback.
    """
    text = (message or "").strip()
    rule = _rule_based_reply(text)
    if rule:
        return {"reply": rule, "source": "cue-faq", "lang": "sw"}

    llm = _openai_swahili(text)
    if llm:
        return {"reply": llm, "source": "cue-llm", "lang": "sw"}

    return {
        "reply": (
            "Ninaweza kukusaidia kwa maswali rahisi kuhusu CUE: namba ya simu, barua pepe, mahali, masaa, "
            "uvujaji, valvu, dashibodi, au Login. Jaribu: \"who are you\", \"what do you do\", \"phone number\", "
            f"au \"what is CUE\". Simu: {PHONE}."
        ),
        "source": "cue-fallback",
        "lang": "sw",
    }

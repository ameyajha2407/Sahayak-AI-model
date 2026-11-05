# llm.py — Gemini API wrapper with JSON parsing, language detection, and grounded demo-mode fallback.
# A3 fix: script-based language detection, demo replies in all 6 languages.
# A4 fix: pack-aware demo responses, out-of-scope handling per pack.
# A5 fix: model updated with fast fallback and cooldown cache.
# Grounding fix: all Demo Mode and Live Mode replies use customer-scoped SQLite lookups via tools.py.

import json
import re
import time
from config import (
    get_gemini_api_key,
    MAX_HISTORY,
    LIVE_HANDOFF_CONNECTED,
    LIVE_BUSINESS_DATA_CONNECTED,
    DEFAULT_MODEL,
    FALLBACK_MODELS,
    MODEL_CANDIDATES,
    FIRST_WORD_TIMEOUT_SECONDS,
    TOTAL_REQUEST_TIMEOUT_SECONDS,
    MAX_OUTPUT_TOKENS,
)
from prompts import get_system_prompt, get_tool_result_prompt, LANGUAGE_SPECS
from tools import execute_tool, get_customer_orders, get_customer_refunds
from warmup import (
    get_cached_genai_client,
    get_query_cache_key,
    get_cached_response,
    set_cached_response,
    warm_up_model_in_background,
)
from perf_logger import log_performance


# ---------------------------------------------------------------------------
# A3: Script-based language detection — checks Unicode character ranges
# ---------------------------------------------------------------------------

def detect_language_from_script(text: str) -> str:
    """Detect language by examining the Unicode script of the characters.

    Priority: Kannada > Tamil > Telugu > Devanagari (Hindi) > Hinglish > English.
    """
    kannada = sum(1 for c in text if '\u0C80' <= c <= '\u0CFF')
    tamil = sum(1 for c in text if '\u0B80' <= c <= '\u0BFF')
    telugu = sum(1 for c in text if '\u0C00' <= c <= '\u0C7F')
    devanagari = sum(1 for c in text if '\u0900' <= c <= '\u097F')

    # If any Indic script characters are present, that script wins
    if kannada > 0:
        return "kn"
    if tamil > 0:
        return "ta"
    if telugu > 0:
        return "te"
    if devanagari > 0:
        return "hi"

    # Latin text — check for unambiguous Hindi/Hinglish words (excluding common English words like "do", "main")
    lower = text.lower()
    hinglish_words = {
        "mera", "meri", "mere", "kya", "hai", "hain", "kab", "nahi", "aaya", "aayi",
        "batao", "bataiye", "karo", "kariye", "hoon", "aapki", "abhi", "kitna",
        "kidhar", "kahan", "bhai", "yaar", "accha", "theek", "paisa", "paise",
        "wapas", "dikhao", "raha", "rahi", "kaise", "aapka", "chahiye", "karke",
        "hota", "dedo", "bolo", "aap", "tum", "humara", "tumhara", "uska", "iska",
        "kar", "madad", "mujhe", "hum", "yeh", "woh", "kyun", "kyunki", "atka",
        "subah", "shaam", "kal", "aaj", "jaldi", "turant", "insaan", "baat",
        "kuch", "kaam", "sahi", "galat", "radd", "khata", "lenden", "kist",
        "bacha", "niyam", "pareshani", "maafi", "kripya", "batayein",
    }
    word_set = set(re.findall(r'\b\w+\b', lower))
    matches = word_set.intersection(hinglish_words)
    if len(matches) >= 1:
        return "hinglish"

    return "en"


# ---------------------------------------------------------------------------
# Demo Mode — non-record templates in ALL 6 languages (no hardcoded records!)
# ---------------------------------------------------------------------------

def _demo(lang, sentiment, intent, confidence, reply, escalate=False,
          esc_reason="", triggers=None, tool_used=None):
    """Shortcut to build a demo response dict."""
    return {
        "language": lang,
        "sentiment": sentiment,
        "intent": intent,
        "confidence": confidence,
        "tool_call": None,
        "tool_used": tool_used,
        "reply": reply,
        "escalate": escalate,
        "escalation_reason": esc_reason,
        "escalation_triggers": triggers or [],
    }


DEMO_REPLIES = {
    "faq": {
        "en": "Our return policy allows returns within 7 days of delivery for most items. The product must be unused and in original packaging. Refunds are processed within 5-7 business days.",
        "hi": "हमारी रिटर्न पॉलिसी के अनुसार, डिलीवरी के 7 दिनों के भीतर अधिकांश वस्तुओं को वापस किया जा सकता है। उत्पाद अप्रयुक्त और मूल पैकेजिंग में होना चाहिए। रिफंड 5-7 कार्य दिवसों में प्रोसेस होता है।",
        "kn": "ನಮ್ಮ ರಿಟರ್ನ್ ಪಾಲಿಸಿ ಪ್ರಕಾರ, ಡೆಲಿವರಿಯ 7 ದಿನಗಳೊಳಗೆ ಹೆಚ್ಚಿನ ವಸ್ತುಗಳನ್ನು ಹಿಂದಿರುಗಿಸಬಹುದು. ಉತ್ಪನ್ನವು ಬಳಸಿಲ್ಲದ ಮತ್ತು ಮೂಲ ಪ್ಯಾಕೇಜಿಂಗ್‌ನಲ್ಲಿ ಇರಬೇಕು.",
        "hinglish": "Humari return policy ke according, delivery ke 7 din ke andar aap most items return kar sakte hain. Product unused aur original packaging mein hona chahiye. Refunds 5-7 business days mein process hote hain.",
        "ta": "எங்கள் திரும்ப பெறுதல் கொள்கையின்படி, டெலிவரி செய்யப்பட்ட 7 நாட்களுக்குள் பெரும்பாலான பொருட்களை திரும்ப பெறலாம். பொருள் பயன்படுத்தப்படாததாகவும் அசல் பேக்கேஜிங்கில் இருக்க வேண்டும்.",
        "te": "మా రిటర్న్ పాలసీ ప్రకారం, డెలివరీ అయిన 7 రోజుల్లో చాలా ఐటమ్‌లను రిటర్న్ చేయవచ్చు. ప్రొడక్ట్ వాడకుండా ఒరిజినల్ ప్యాకేజింగ్‌లో ఉండాలి.",
    },
    "escalation": {
        "en": "I understand your concern and sincerely apologise. I have queued a demo support handoff summary for a human specialist (Demo Simulation — no live ticketing or agent notification service is currently connected).",
        "hi": "मैं आपकी परेशानी समझता हूँ और खेद प्रकट करता हूँ। मैंने मानव विशेषज्ञ के लिए एक डेमो हैंडऑफ़ सारांश तैयार कर दिया है (डेमो सिमुलेशन — वर्तमान में कोई लाइव एजेंट या टिकटिंग सेवा कनेक्ट नहीं है)।",
        "kn": "ನಿಮ್ಮ ಸಮಸ್ಯೆ ನನಗೆ ಅರ್ಥವಾಗುತ್ತದೆ, ಕ್ಷಮಿಸಿ. ನಾನು ಮಾನವ ತಜ್ಞರಿಗಾಗಿ ಡೆಮೊ ಹ್ಯಾಂಡ್‌ಆಫ್ ಸಾರಾಂಶವನ್ನು ಸಿದ್ಧಪಡಿಸಿದ್ದೇನೆ (ಡೆಮೊ ಸಿಮ್ಯುಲೇಶನ್ — ಯಾವುದೇ ಲೈವ್ ಏಜೆಂಟ್ ಸೇವೆ ಸಂಪರ್ಕಗೊಂಡಿಲ್ಲ).",
        "hinglish": "Main aapki pareshani samajhta hoon aur maafi chahta hoon. Maine human support specialist ke liye ek demo handoff summary queue kar di hai (Demo Simulation — abhi koi live agent ya ticketing service connected nahi hai).",
        "ta": "உங்கள் சிரமத்தை நான் புரிந்துகொள்கிறேன், மன்னிக்கவும். மனித ஆதரவு நிபுணருக்கான டெமோ ஹேண்ட்ஆஃப் சுருக்கத்தை வரிசையில் சேர்த்துள்ளேன் (டெமோ சிமுலேஷன் — நேரடி முகவர் சேவை இணைக்கப்படவில்லை).",
        "te": "మీ ఇబ్బందిని నేను అర్థం చేసుకుంటున్నాను, క్షమించండి. హ్యూమన్ సపోర్ట్ స్పెషలిస్ట్ కోసం డెమో హ్యాండ్ఆఫ్ సారాంశాన్ని సిద్ధం చేశాను (డెమో సిమ్యులేషన్ — లైవ్ ఏజెంట్ సర్వీస్ కనెక్ట్ చేయబడలేదు).",
    },
    "escalation_after_hours": {
        "en": "Our human support team is offline right now (working hours: 9 AM – 9 PM IST). I have queued a simulated after-hours callback ticket for tomorrow between 9:00 AM and 11:00 AM IST (Demo Simulation — no external callback provider is connected).",
        "hi": "हमारी मानव टीम अभी ऑफ़लाइन है (कार्य समय: सुबह 9 बजे से रात 9 बजे तक IST)। मैंने कल सुबह 9:00 से 11:00 बजे के लिए एक सिमुलेटेड कॉलबैक टिकट कतारबद्ध किया है (डेमो सिमुलेशन — कोई बाहरी कॉलबैक सेवा कनेक्ट नहीं है)।",
        "kn": "ನಮ್ಮ ಮಾನವ ತಂಡ ಪ್ರಸ್ತುತ ಆಫ್‌ಲೈನ್‌ನಲ್ಲಿದೆ (ಕೆಲಸದ ಸಮಯ: ಬೆಳಿಗ್ಗೆ 9 ರಿಂದ ರಾತ್ರಿ 9 IST). ನಾಳೆ ಬೆಳಿಗ್ಗೆ 9:00 ರಿಂದ 11:00 ರ ನಡುವೆ ಸಿಮ್ಯುಲೇಟೆಡ್ ಕಾಲ್‌ಬ್ಯಾಕ್ ಟಿಕೆಟ್ ಅನ್ನು ಕ್ಯೂ ಮಾಡಲಾಗಿದೆ (ಡೆಮೊ ಸಿಮ್ಯುಲೇಶನ್).",
        "hinglish": "Humari human team abhi offline hai (working hours: 9 AM – 9 PM IST). Maine kal subah 9:00 AM se 11:00 AM ke liye ek simulated priority callback ticket queue kar diya hai (Demo Simulation — koi live callback service connected nahi hai).",
        "ta": "எங்கள் நேரடி ஆதரவு குழு தற்போது ஆஃப்லைனில் உள்ளது (வேலை நேரம்: காலை 9 முதல் இரவு 9 வரை IST). நாளை காலை 9:00 முதல் 11:00 மணிக்குள் ஒரு சிமுலேட்டட் கால்பேக் டிக்கெட் வரிசையில் வைக்கப்பட்டுள்ளது (டெமோ சிமுலேஷன்).",
        "te": "మా హ్యూమన్ సపోర్ట్ బృందం ప్రస్తుతం ఆఫ్‌లైన్‌లో ఉంది (పని వేళలు: ఉదయం 9 నుండి రాత్రి 9 వరకు IST). రేపు ఉదయం 9:00 నుండి 11:00 గంటల మధ్య సిమ్యులేటెడ్ కాల్‌బ್ಯಾక్ టిక్కెట్ క్యూ చేయబడింది (డెమో సిమ్యులేషన్).",
    },
    "off_topic": {
        "en": "I appreciate your interest! However, I'm here to help with your {company} support queries. How can I assist you with your account, orders, or services today?",
        "hi": "आपकी रुचि के लिए धन्यवाद! लेकिन मैं केवल आपके {company} सपोर्ट प्रश्नों में मदद कर सकता हूँ। आज मैं आपके खाते या सेवाओं में कैसे मदद कर सकता हूँ?",
        "kn": "ನಿಮ್ಮ ಆಸಕ್ತಿಗೆ ಧನ್ಯವಾದ! ಆದರೆ ನಾನು ಕೇವಲ ನಿಮ್ಮ {company} ಸಪೋರ್ಟ್ ಪ್ರಶ್ನೆಗಳಿಗೆ ಮಾತ್ರ ಸಹಾಯ ಮಾಡಬಹುದು. ಇಂದು ನಿಮ್ಮ ಖಾತೆ ಅಥವಾ ಸೇವೆಗಳ ಬಗ್ಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಲಿ?",
        "hinglish": "Aapki interest ke liye shukriya! Lekin main sirf aapke {company} support queries mein help kar sakta hoon. Aaj aapke account ya services mein kaise help karun?",
        "ta": "உங்கள் ஆர்வத்திற்கு நன்றி! ஆனால் நான் உங்கள் {company} ஆதரவு கேள்விகளுக்கு மட்டுமே உதவ முடியும். இன்று உங்கள் கணக்கு அல்லது சேவைகளில் எப்படி உதவ முடியும்?",
        "te": "మీ ఆసక్తికి ధన్యవాదాలు! కానీ నేను మీ {company} సపోర్ట్ ప్రశ్నలకు మాత్రమే సహాయం చేయగలను. ఈ రోజు మీ ఖాతా లేదా సేవల్లో ఎలా సహాయం చేయగలను?",
    },
    "out_of_scope_pack": {
        "en": "I am the support assistant for {company}. I can only assist with our active {company} services and do not have access to external industry records. How can I assist you with your {company} account today?",
        "hi": "मैं {company} का सहायता सहायक हूँ। मैं केवल हमारी {company} सेवाओं में मदद कर सकता हूँ और अन्य सेवाओं की जानकारी नहीं दे सकता। आज मैं आपकी {company} सेवा में कैसे मदद करूँ?",
        "kn": "ನಾನು {company} ನ ಸಹಾಯಕರಾಗಿದ್ದೇನೆ. ನಾನು ಕೇವಲ ನಮ್ಮ ಸೇವೆಗಳ ಕುರಿತು ಮಾತ್ರ ಸಹಾಯ ಮಾಡಬಲ್ಲೆ, ಇತರ ಬಾಹ್ಯ ಆರ್ಡರ್‌ಗಳ ಬಗ್ಗೆ ಮಾಹಿತಿ ನೀಡಲು ಸಾಧ್ಯವಿಲ್ಲ. ಇಂದು ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಲಿ?",
        "hinglish": "Main {company} ka support assistant hoon. Main sirf humari services mein help kar sakta hoon, doosre industry packs ka data mere paas nahi hai. Main aapki {company} account mein kaise help karun?",
        "ta": "நான் {company} இன் ஆதரவு உதவியாளர். எங்கள் சேவைகளில் மட்டுமே என்னால் உதவ முடியும். இன்று உங்கள் {company} சேவையில் நான் எப்படி உதவ முடியும்?",
        "te": "నేను {company} సపోర్ట్ అసిస్టెంట్‌ని. నేను మా సేవలలో మాత్రమే సహాయం చేయగలను. ఈ రోజు మీ {company} సేవలో నేను ఎలా సహాయం చేయగలను?",
    },
    "vague_clarification": {
        "en": "I'd be glad to help! Could you please clarify which order ID or account service you are referring to, and what specific issue you are experiencing?",
        "hi": "मैं आपकी मदद करने के लिए तैयार हूँ! कृपया स्पष्ट करें कि आप किस ऑर्डर आईडी या सेवा की बात कर रहे हैं और उसमें क्या परेशानी आ रही है?",
        "kn": "ನಾನು ನಿಮಗೆ ಸಹಾಯ ಮಾಡುತ್ತೇನೆ! ನೀವು ಯಾವ ಆರ್ಡರ್ ಐಡಿ ಅಥವಾ ಸೇವೆಯ ಬಗ್ಗೆ ಮಾತನಾಡುತ್ತಿದ್ದೀರಿ ಮತ್ತು ಅದರಲ್ಲಿ ಏನು ಸಮಸ್ಯೆ ಇದೆ ಎಂದು ದಯವಿಟ್ಟು ಸ್ಪಷ್ಟಪಡಿಸಿ?",
        "hinglish": "Main bilkul help karunga! Kya aap clarify kar sakte hain ki aap kis order ID ya service ki baat kar rahe hain, aur usme kya exact issue aa raha hai?",
        "ta": "நான் உதவ தயாராக உள்ளேன்! எந்த ஆர்டர் ஐடி அல்லது சேவை, என்ன பிரச்சனை என்பதை தெளிவுபடுத்த முடியுமா?",
        "te": "నేను సహాయం చేయడానికి సిద్ధంగా ఉన్నాను! మీరు ఏ ఆర్డర్ ఐడి లేదా సేవ గురించి మాట్లాడుతున్నారు మరియు ఏమి సమస్య ఉందో దయచేసి స్పష్టం చేయండి?",
    },
    "low_confidence_escalate": {
        "en": "I'm having trouble identifying your specific issue from the information provided. I have queued a demo handoff for a human support specialist to assist you (Demo Simulation — no live agent service connected).",
        "hi": "पर्याप्त जानकारी न होने के कारण मैं आपकी समस्या की सही पहचान नहीं कर पा रहा हूँ। मैंने मानव विशेषज्ञ के लिए एक डेमो हैंडऑफ़ तैयार कर दिया है (डेमो सिमुलेशन)।",
        "kn": "ನಿಖರ ಮಾಹಿತಿ ಇಲ್ಲದೆ ಸಮಸ್ಯೆಯನ್ನು ಗುರುತಿಸಲು ಸಾಧ್ಯವಾಗುತ್ತಿಲ್ಲ. ಮಾನವ ತಜ್ಞರಿಗಾಗಿ ಡೆಮೊ ಹ್ಯಾಂಡ್‌ಆಫ್ ಅನ್ನು ಕ್ಯೂ ಮಾಡಿದ್ದೇನೆ (ಡೆಮೊ ಸಿಮ್ಯುಲೇಶನ್).",
        "hinglish": "Specific issue identify na hone ki wajah se main aapke liye human specialist ka demo handoff queue kar raha hoon (Demo Simulation — no live agent connected).",
        "ta": "விவரங்கள் தெளிவாக இல்லாததால் மனித நிபுணருக்கான டெமோ ஹேண்ட்ஆஃப் வரிசையில் சேர்க்கப்பட்டுள்ளது (டெமோ சிமுலேஷன்).",
        "te": "వివరాలు స్పష్టంగా లేనందున హ్యూమన్ స్పెషలిస్ట్ కోసం డెమో హ్యాండ్ఆఫ్ క్యూ చేయబడింది (డెమో సిమ్యులేషన్).",
    },
    "greeting": {
        "en": "Hello! Welcome to {company} support. I'm here to help with your sample account records and support queries. How can I assist you today?",
        "hi": "नमस्ते! {company} सपोर्ट में आपका स्वागत है। आज मैं आपकी कैसे मदद कर सकता हूँ?",
        "kn": "ನಮಸ್ಕಾರ! {company} ಸಪೋರ್ಟ್‌ಗೆ ಸ್ವಾಗತ. ಇಂದು ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಬಹುದು?",
        "hinglish": "Hello! {company} support mein aapka swagat hai. Aaj main aapki kaise help kar sakta hoon?",
        "ta": "வணக்கம்! {company} ஆதரவுக்கு வரவேற்கிறோம். இன்று நான் உங்களுக்கு எப்படி உதவ முடியும்?",
        "te": "నమస్కారం! {company} సపోర్ట్‌కు స్వాగతం. ఈ రోజు నేను మీకు ఎలా సహాయం చేయగలను?",
    },
    "order_not_found": {
        "en": "I'm sorry, order {order_id} could not be found for your account. Please check and share the correct order ID.",
        "hi": "क्षमा करें, आपके खाते के लिए ऑर्डर {order_id} नहीं मिला। कृपया जाँच कर सही ऑर्डर आईडी बताएं।",
        "kn": "ಕ್ಷಮಿಸಿ, ನಿಮ್ಮ ಖಾತೆಯಲ್ಲಿ ಆರ್ಡರ್ {order_id} ಕಂಡುಬಂದಿಲ್ಲ. ದಯವಿಟ್ಟು ಪರಿಶೀಲಿಸಿ ಸರಿಯಾದ ಆರ್ಡರ್ ಐಡಿಯನ್ನು ತಿಳಿಸಿ.",
        "hinglish": "Sorry, aapke account ke liye order {order_id} nahi mila. Kripya check karke sahi order ID batayein.",
        "ta": "மன்னிக்கவும், உங்கள் கணக்கில் ஆர்டர் {order_id} கண்டறியப்படவில்லை. தயவுசெய்து சரிபார்த்து சரியான ஆர்டர் ஐடியைக் கூறவும்.",
        "te": "క్షమించండి, మీ ఖాతాలో ఆర్డర్ {order_id} కనుగొనబడలేదు. దయచేసి సరిచూసి సరైన ఆర్డర్ ఐడిని తెలియజేయండి.",
    },
    "unavailable_info": {
        "en": "That specific detail is not available in your current sample records for {company}. Would you like me to check your available account/order status or queue a demo support ticket for further assistance?",
        "hi": "{company} के आपके वर्तमान सैंपल रिकॉर्ड में यह जानकारी उपलब्ध नहीं है। क्या आप चाहेंगे कि मैं आपके उपलब्ध ऑर्डर/खाते की स्थिति की जाँच करूँ या सहायता टिकट बनाऊँ?",
        "kn": "{company} ನ ನಿಮ್ಮ ಪ್ರಸ್ತುತ ಸ್ಯಾಂಪಲ್ ದಾಖಲೆಗಳಲ್ಲಿ ಆ ನಿರ್ದಿಷ್ಟ ಮಾಹಿತಿ ಲಭ್ಯವಿಲ್ಲ. ನಿಮ್ಮ ಲಭ್ಯವಿರುವ ಆರ್ಡರ್/ಖಾತೆ ಸ್ಥಿತಿಯನ್ನು ಪರಿಶೀಲಿಸಲೇ?",
        "hinglish": "{company} ke current sample records mein yeh specific detail available nahi hai. Kya main aapka available order/account status check karun ya demo support ticket queue karun?",
        "ta": "{company}க்கான உங்கள் தற்போதைய மாதிரிப் பதிவுகளில் அந்த விவரம் இல்லை. உங்கள் ஆர்டர்/கணக்கு நிலையைச் சரிபார்க்கட்டுமா?",
        "te": "{company} యొక్క మీ ప్రస్తుత శాంపిల్ రికార్డులలో ఆ వివరాలు అందుబాటులో లేవు. మీ ఆర్డర్/ఖాతా స్థితిని తనిఖీ చేయమంటారా?",
    },
}

# Intent keywords for demo mode detection (ordered & multilingual across EN, HI, Hinglish, KN, TA, TE)
_INTENT_KEYWORDS = {
    # Specific E-commerce actions first
    "cancel_order": [
        "cancel", "cancellation", "ರದ್ದು", "ರದ್ದುಗೊಳಿಸಿ", "रद्द", "कैंसिल",
        "ரத்து", "రద్దు", "band karo",
    ],
    "refund_status": [
        "refund", "rif", "paisa wapas", "paise wapas", "money back", "रिफंड",
        "वापस", "ಮರುಪಾವತಿ", "திரும்ப", "பணம் திரும்ப", "రీఫండ్", "wapas",
    ],
    "order_status": [
        "order", "ord", "ऑर्डर", "आर्डर", "ಆರ್ಡರ್", "ஆர்டர்", "ఆర్డర్",
        "deliver", "delivery", "ship", "status", "kab aayega", "kahan hai",
        "kidhar", "where is", "ಯಾವಾಗ", "ಎಲ್ಲಿದೆ", "எங்கே", "எப்போது",
        "ఎక్కడ", "ఎప్పుడు", "स्थिति", "डिलीवरी", "parcel", "पार्सल", "ಪಾರ್ಸೆಲ್",
        "பார்சல்", "పార్సెల్",
    ],
    # Specific Bank actions first
    "block_card": [
        "block", "card", "kho gaya", "lost", "ಕಾರ್ಡ್", "कार्ड", "கார்டு",
        "కార్డ్", "stolen", "ಬ್ಲಾಕ್", "ब्लॉक", "தடு", "బ్లాక్",
    ],
    "loan_info": [
        "loan", "emi", "ಸಾಲ", "लोन", "kist", "கடன்", "రుణం", "किस्त",
    ],
    "recent_transactions": [
        "transaction", "transactions", "statement", "lenden", "लेन-देन",
        "लेनदेन", "ವಹಿವಾಟು", "பரிவர்த்தனை", "లావాదేవీ",
    ],
    "account_info": [
        "balance", "account", "khata", "बैलेंस", "ಖಾತೆ", "ब्यालेन्स",
        "இருப்பு", "బ్యాలెన్స్", "खाता", "ಬ್ಯಾಲೆನ್ಸ್", "கணக்கு", "ఖాతా",
    ],
    # Specific Telecom actions first
    "data_usage": [
        "data", "gb", "usage", "डेटा", "ಡೇಟಾ", "டேட்டா", "డేటా", "bacha", "remaining",
    ],
    "recharge_status": [
        "recharge", "रिचार्ज", "ರೀಚಾರ್ಜ್", "ரீசார்ஜ்", "రీచార్జ్", "topup",
    ],
    "bill_info": [
        "bill", "due", "invoice", "बिल", "ಬಿಲ್", "பில்", "బిల్", "postpaid bill",
    ],
    "plan_details": [
        "plan", "pack", "validity", "प्लान", "ಪ್ಲಾನ್", "திட்டம்", "ప్లాన్", "वैलिडिटी",
    ],
    # Common
    "faq": [
        "return policy", "return", "policy", "exchange", "working hours", "faq",
        "niyam", "ಪಾಲಿಸಿ", "ನಿಯಮ", "கொள்கை", "పాలసీ", "रिटर्न पॉलिसी", "रिटर्न",
    ],
    "escalation": [
        "manager", "supervisor", "useless", "worst", "terrible", "angry",
        "human", "human agent", "live agent", "real person", "representative",
        "insaan", "agent se baat", "baat karao", "इंसान", "मानव", "एजेंट से बात",
        "सीनियर", "ಮನುಷ್ಯ", "ಮಾನವ", "ಪ್ರತಿನಿಧಿ", "மனித", "முகவர்",
        "మనిషి", "ఏజెంట్", "pathetic", "disgusted", "fraud", "hacked",
        "legal", "lawyer", "consumer court", "talk to a person", "connect me to",
    ],
    "off_topic": [
        "poem", "write a", "who is", "tell me about", "capital of",
        "weather", "latest iphone", "prime minister", "kavita", "shairi",
        "recipe", "cricket score", "movie",
    ],
    "unavailable_info": [
        "tracking number", "tracking link", "awb", "courier phone",
        "delivery boy phone", "driver number", "ifsc", "swift code",
        "branch address", "cibil", "credit score", "imei", "puk code",
        "international roaming",
    ],
}


def _infer_prior_order_intent(history: list | None) -> str:
    """Inspect recent conversation history to see which order intent was active."""
    if not history:
        return "order_status"
    for msg in reversed(history[-6:]):
        intent = msg.get("intent", "")
        if intent in ("cancel_order", "refund_status", "order_status"):
            return intent
        text = (msg.get("content") or "").lower()
        if any(k in text for k in _INTENT_KEYWORDS["cancel_order"]):
            return "cancel_order"
        if any(k in text for k in _INTENT_KEYWORDS["refund_status"]):
            return "refund_status"
    return "order_status"


def _detect_demo_intent(message: str, pack_tools: list, history: list = None) -> str:
    """Keyword-based intent detection for demo mode, respects active pack and hard cases (Part C)."""
    lower = message.lower()
    has_ord_id = bool(re.search(r"\bord\d+\b", lower))

    # 0. Unavailable specific fields not in sample DB schema
    if any(kw in lower for kw in _INTENT_KEYWORDS["unavailable_info"]):
        return "unavailable_info"

    # 1. Part C: Hard case - Local expression (slang/idioms)
    if (
        "kidhar atka" in lower
        or "bhai mera parcel" in lower
        or ("bhai" in lower and "parcel" in lower)
        or ("tension" in lower and "parcel" in lower)
    ):
        return "local_expression"

    # 2. Part C: Hard case - Mid-conversation correction (e.g. "Sorry, I meant ORD1002")
    correction_markers = [
        "sorry, i meant", "i meant", "meant ord", "sorry ord", "instead of ord",
        "actually ord", "no, ord", "wait, ord", "मेरा मतलब", "माफ़ करें", "गलती से",
        "के बजाय", "ಕ್ಷಮಿಸಿ", "ಬದಲಿಗೆ", "மன்னிக்கவும்", "பதிலாக",
        "క్షమించండి", "బదులుగా", "bolna tha", "galat order", "ki jagah",
    ]
    if has_ord_id and any(m in lower for m in correction_markers):
        return "correction_order"

    # 3. Part C: Hard case - Multi-part query
    has_cancel = any(k in lower for k in _INTENT_KEYWORDS["cancel_order"])
    has_refund = any(k in lower for k in _INTENT_KEYWORDS["refund_status"])
    has_faq = any(k in lower for k in ["return policy", "policy", "पॉलिसी", "ಪಾಲಿಸಿ", "கொள்கை", "పాలసీ"])
    if (has_cancel and has_refund) or (has_cancel and has_faq) or (has_refund and has_faq):
        return "multipart_query"

    # 4. Part C: Hard case - Cannot resolve confidently (Turn 1: clarify, Turn 2: escalate)
    vague_phrases = [
        "not working properly", "my thing is not working", "kuch kaam nahi kar raha",
        "not working", "just broken", "just fix it",
    ]
    if any(phrase in lower for phrase in vague_phrases) and not any(
        k in lower for k in ["order", "ord", "plan", "card", "recharge", "balance"]
    ):
        clarification_asked = False
        if history:
            for m in reversed(history):
                if m.get("role") in ("agent", "assistant"):
                    content = m.get("content", "").lower()
                    if any(w in content for w in ["clarify", "which order", "which item", "स्पष्ट", "ಸ್ಪಷ್ಟ", "தெளிவு", "స్పష్టం"]):
                        clarification_asked = True
                        break
        if clarification_asked or "just broken" in lower or "just fix it" in lower:
            return "low_confidence_escalate"
        return "vague_clarification"

    # 5. Check escalation and off-topic
    for kw in _INTENT_KEYWORDS["escalation"]:
        if kw in lower:
            return "escalation"
    for kw in _INTENT_KEYWORDS["off_topic"]:
        if kw in lower:
            return "off_topic"

    # 6. Map pack tools to prioritized intent names (specific actions before generic status)
    tool_set = set(pack_tools or [])
    prioritized_tool_intents = [
        ("cancel_order", "cancel_order"),
        ("get_refund_status", "refund_status"),
        ("get_order_status", "order_status"),
        ("block_card", "block_card"),
        ("get_loan_info", "loan_info"),
        ("get_recent_transactions", "recent_transactions"),
        ("get_account_info", "account_info"),
        ("get_data_usage", "data_usage"),
        ("get_recharge_status", "recharge_status"),
        ("get_bill_info", "bill_info"),
        ("get_plan_details", "plan_details"),
    ]
    active_intents = [intent for tool_name, intent in prioritized_tool_intents if not tool_set or tool_name in tool_set]
    active_intents.append("faq")

    # If the user just replied with an order ID (e.g. "ORD1002") after being asked which order they mean
    if has_ord_id and "order_status" in active_intents:
        # Check if an explicit cancel or refund keyword is in this message first
        if has_cancel and "cancel_order" in active_intents:
            return "cancel_order"
        if has_refund and "refund_status" in active_intents:
            return "refund_status"
        # Otherwise inherit from history if prior turn was cancel_order or refund_status
        return _infer_prior_order_intent(history)

    # Match active pack intents in priority order
    for intent in active_intents:
        for kw in _INTENT_KEYWORDS.get(intent, []):
            if kw.lower() in lower:
                return intent

    # Check out-of-scope pack query
    for intent, keywords in _INTENT_KEYWORDS.items():
        if intent in ("escalation", "off_topic", "faq", "unavailable_info"):
            continue
        if intent not in active_intents:
            for kw in keywords:
                if kw.lower() in lower:
                    return "out_of_scope_pack"

    # Check for greetings
    if any(w in lower for w in ["hi", "hello", "hey", "namaste", "नमस्ते", "ನಮಸ್ಕಾರ", "வணக்கம்", "నమస్కారం"]):
        return "greeting"

    return "greeting"


def _format_order_status_reply(lang: str, order_info: dict, is_local_expr: bool = False) -> str:
    """Format a grounded order status reply in the target language using real DB fields."""
    oid = order_info["order_id"]
    item = order_info["item"]
    amt = order_info["amount"]
    status = order_info["status"]
    exp = order_info.get("expected_date") or "soon"

    if is_local_expr:
        replies = {
            "en": f"No tension at all! According to your sample records, order {oid} ({item}, ₹{amt:,.0f}) has status '{status}' (expected date: {exp}).",
            "hi": f"भाई बिल्कुल टेंशन मत लो! आपके सैंपल रिकॉर्ड के अनुसार, ऑर्डर {oid} ({item}, ₹{amt:,.0f}) की स्थिति '{status}' है (संभावित तिथि: {exp})।",
            "kn": f"ಚಿಂತೆ ಬೇಡ! ನಿಮ್ಮ ಸ್ಯಾಂಪಲ್ ದಾಖಲೆಯ ಪ್ರಕಾರ, ಆರ್ಡರ್ {oid} ({item}, ₹{amt:,.0f}) ಸ್ಥಿತಿ '{status}' ಆಗಿದೆ (ನಿರೀಕ್ಷಿತ ದಿನಾಂಕ: {exp}).",
            "hinglish": f"Bhai tension mat lo! Aapke sample record ke mutabik, order {oid} ({item}, ₹{amt:,.0f}) abhi '{status}' status mein hai (expected date: {exp}).",
            "ta": f"கவலைப்படாதீர்கள்! உங்கள் மாதிரிப் பதிவின்படி, ஆர்டர் {oid} ({item}, ₹{amt:,.0f}) தற்போது '{status}' நிலையில் உள்ளது (எதிர்பார்க்கப்படும் தேதி: {exp}).",
            "te": f"టెన్షన్ పడకండి! మీ శాంపిల్ రికార్డు ప్రకారం, ఆర్డర్ {oid} ({item}, ₹{amt:,.0f}) ప్రస్తుతం '{status}' స్థితిలో ఉంది (ఆశించిన తేదీ: {exp}).",
        }
        return replies.get(lang, replies["en"])

    replies = {
        "en": f"Your order {oid} ({item}, ₹{amt:,.0f}) currently has status '{status}' with expected delivery date {exp} (sample data).",
        "hi": f"आपके ऑर्डर {oid} ({item}, ₹{amt:,.0f}) की वर्तमान स्थिति '{status}' है और संभावित डिलीवरी तिथि {exp} है (सैंपल डेटा)।",
        "kn": f"ನಿಮ್ಮ ಆರ್ಡರ್ {oid} ({item}, ₹{amt:,.0f}) ಪ್ರಸ್ತುತ '{status}' ಸ್ಥಿತಿಯಲ್ಲಿದೆ ಮತ್ತು ನಿರೀಕ್ಷಿತ ಡೆಲಿವರಿ ದಿನಾಂಕ {exp} (ಸ್ಯಾಂಪಲ್ ಡೇಟಾ).",
        "hinglish": f"Aapka order {oid} ({item}, ₹{amt:,.0f}) abhi '{status}' status mein hai aur expected delivery date {exp} hai (sample data).",
        "ta": f"உங்கள் ஆர்டர் {oid} ({item}, ₹{amt:,.0f}) நிலை '{status}', எதிர்பார்க்கப்படும் டெலிவரி தேதி {exp} (மாதிரி தரவு).",
        "te": f"మీ ఆర్డర్ {oid} ({item}, ₹{amt:,.0f}) స్థితి '{status}', ఆశించిన డెలివరీ తేదీ {exp} (శాంపిల్ డేటా).",
    }
    return replies.get(lang, replies["en"])


def _format_refund_status_reply(lang: str, order_info: dict, ref_info: dict) -> str:
    """Format a grounded refund status reply in the target language using real DB fields."""
    oid = order_info["order_id"]
    item = order_info["item"]
    status = order_info["status"]

    if ref_info.get("success"):
        rid = ref_info["refund_id"]
        r_stat = ref_info["status"]
        r_amt = ref_info["amount"]
        r_date = ref_info["initiated_on"]
        replies = {
            "en": f"Your refund {rid} for order {oid} ({item}) of ₹{r_amt:,.0f} is currently '{r_stat}' (initiated on {r_date}, sample data).",
            "hi": f"आपके ऑर्डर {oid} ({item}) के लिए ₹{r_amt:,.0f} का रिफंड {rid} वर्तमान में '{r_stat}' स्थिति में है (प्रारंभ तिथि: {r_date}, सैंपल डेटा)।",
            "kn": f"ನಿಮ್ಮ ಆರ್ಡರ್ {oid} ({item}) ನ ₹{r_amt:,.0f} ಮರುಪಾವತಿ {rid} ಪ್ರಸ್ತುತ '{r_stat}' ಸ್ಥಿತಿಯಲ್ಲಿದೆ (ದಿನಾಂಕ: {r_date}, ಸ್ಯಾಂಪಲ್ ಡೇಟಾ).",
            "hinglish": f"Aapke order {oid} ({item}) ka ₹{r_amt:,.0f} refund ({rid}) abhi '{r_stat}' status mein hai (initiated on {r_date}, sample data).",
            "ta": f"உங்கள் ஆர்டர் {oid} ({item})க்கான ₹{r_amt:,.0f} ரீஃபண்ட் ({rid}) தற்போது '{r_stat}' நிலையில் உள்ளது (தேதி: {r_date}, மாதிரி தரவு).",
            "te": f"మీ ఆర్డర్ {oid} ({item}) కోసం ₹{r_amt:,.0f} రీఫండ్ ({rid}) ప్రస్తుతం '{r_stat}' స్థితిలో ఉంది (తేదీ: {r_date}, శాంపిల్ డేటా).",
        }
    else:
        replies = {
            "en": f"No refund record was found for your order {oid} ({item}, current order status: '{status}'). Would you like help with another order ID?",
            "hi": f"आपके ऑर्डर {oid} ({item}, वर्तमान स्थिति: '{status}') के लिए कोई रिफंड रिकॉर्ड नहीं मिला। क्या आप किसी अन्य ऑर्डर आईडी की जाँच करना चाहेंगे?",
            "kn": f"ನಿಮ್ಮ ಆರ್ಡರ್ {oid} ({item}, ಸ್ಥಿತಿ: '{status}') ಗೆ ಯಾವುದೇ ಮರುಪಾವತಿ ದಾಖಲೆ ಕಂಡುಬಂದಿಲ್ಲ. ಮತ್ತೊಂದು ಆರ್ಡರ್ ಐಡಿಯನ್ನು ಪರಿಶೀಲಿಸಲೇ?",
            "hinglish": f"Aapke order {oid} ({item}, current status: '{status}') ke liye koi refund record nahi mila. Kya aap kisi aur order ID ke baare mein puchna chahte hain?",
            "ta": f"உங்கள் ஆர்டர் {oid} ({item}, நிலை: '{status}')க்கு ரீஃபண்ட் பதிவு எதுவும் இல்லை. வேறு ஆர்டர் ஐடியைச் சரிபார்க்கட்டுமா?",
            "te": f"మీ ఆర్డర్ {oid} ({item}, స్థితి: '{status}') కోసం రీఫండ్ రికార్డు కనుగొనబడలేదు. మరొక ఆర్డర్ ఐడిని తనిఖీ చేయమంటారా?",
        }
    return replies.get(lang, replies["en"])


def _format_cancel_order_reply(lang: str, order_info: dict, cancel_res: dict) -> str:
    """Format a grounded order cancellation reply — claims cancellation ONLY if cancel_res['success'] is True."""
    oid = order_info["order_id"]
    item = order_info["item"]
    amt = order_info["amount"]
    status = order_info["status"]

    if cancel_res.get("success"):
        replies = {
            "en": f"Your order {oid} ({item}) has been cancelled successfully. ₹{amt:,.0f} will be refunded within 3-5 business days (sample data).",
            "hi": f"आपका ऑर्डर {oid} ({item}) सफलतापूर्वक रद्द कर दिया गया है। ₹{amt:,.0f} 3-5 कार्य दिवसों में रिफंड हो जाएगा (सैंपल डेटा)।",
            "kn": f"ನಿಮ್ಮ ಆರ್ಡರ್ {oid} ({item}) ಯಶಸ್ವಿಯಾಗಿ ರದ್ದುಗೊಳಿಸಲಾಗಿದೆ. ₹{amt:,.0f} 3-5 ಕೆಲಸದ ದಿನಗಳಲ್ಲಿ ಮರಳಿ ಬರುತ್ತದೆ (ಸ್ಯಾಂಪಲ್ ಡೇಟಾ).",
            "hinglish": f"Aapka order {oid} ({item}) successfully cancel kar diya gaya hai. ₹{amt:,.0f} 3-5 business days mein refund ho jayega (sample data).",
            "ta": f"உங்கள் ஆர்டர் {oid} ({item}) வெற்றிகரமாக ரத்து செய்யப்பட்டது. ₹{amt:,.0f} 3-5 வணிக நாட்களில் திரும்பப் பெறப்படும் (மாதிரி தரவு).",
            "te": f"మీ ఆర్డర్ {oid} ({item}) విజయవంతంగా రద్దు చేయబడింది. ₹{amt:,.0f} 3-5 పని దినాల్లో రీఫండ్ అవుతుంది (శాంపిల్ డేటా).",
        }
    else:
        replies = {
            "en": f"Order {oid} ({item}) cannot be cancelled because its status is already '{status}'. Only orders with status 'placed' can be cancelled.",
            "hi": f"ऑर्डर {oid} ({item}) को रद्द नहीं किया जा सकता क्योंकि इसकी स्थिति पहले से '{status}' है। केवल 'placed' स्थिति वाले ऑर्डर ही रद्द किए जा सकते हैं।",
            "kn": f"ಆರ್ಡರ್ {oid} ({item}) ಅನ್ನು ರದ್ದುಗೊಳಿಸಲು ಸಾಧ್ಯವಿಲ್ಲ ಏಕೆಂದರೆ ಅದರ ಸ್ಥಿತಿ ಈಗಾಗಲೇ '{status}' ಆಗಿದೆ. ಕೇವಲ 'placed' ಸ್ಥಿತಿಯಲ್ಲಿರುವ ಆರ್ಡರ್‌ಗಳನ್ನು ಮಾತ್ರ ರದ್ದುಗೊಳಿಸಬಹುದು.",
            "hinglish": f"Order {oid} ({item}) cancel nahi kiya ja sakta kyunki iska status pehle se '{status}' hai. Sirf 'placed' status wale orders hi cancel ho sakte hain.",
            "ta": f"ஆர்டர் {oid} ({item}) ஏற்கனவே '{status}' நிலையில் உள்ளதால் அதை ரத்து செய்ய முடியாது. 'placed' நிலையில் உள்ள ஆர்டர்களை மட்டுமே ரத்து செய்ய முடியும்.",
            "te": f"ఆర్డర్ {oid} ({item}) ఇప్పటికే '{status}' స్థితిలో ఉన్నందున రద్దు చేయలేము. కేవలం 'placed' స్థితిలో ఉన్న ఆర్డర్లను మాత్రమే రద్దు చేయవచ్చు.",
        }
    return replies.get(lang, replies["en"])


def _format_which_order_prompt(lang: str, orders: list[dict], intent: str) -> str:
    """When the customer has multiple orders and did not provide an order ID, ask which order they mean."""
    summary_items = ", ".join(f"{o['order_id']} ({o['item']} — {o['status']})" for o in orders)
    if intent == "cancel_order":
        placed_ids = [o["order_id"] for o in orders if o["status"] == "placed"]
        placed_hint = f" (eligible 'placed' order: {', '.join(placed_ids)})" if placed_ids else " (note: only 'placed' orders can be cancelled)"
        replies = {
            "en": f"To cancel an order, please specify the order ID. Your sample account has the following orders: {summary_items}{placed_hint}. Which order ID would you like to cancel?",
            "hi": f"ऑर्डर रद्द करने के लिए कृपया ऑर्डर आईडी बताएं। आपके खाते में ये ऑर्डर हैं: {summary_items}। आप कौन-सा ऑर्डर आईडी रद्द करना चाहते हैं?",
            "kn": f"ಆರ್ಡರ್ ರದ್ದುಗೊಳಿಸಲು ದಯವಿಟ್ಟು ಆರ್ಡರ್ ಐಡಿಯನ್ನು ತಿಳಿಸಿ. ನಿಮ್ಮ ಖಾತೆಯಲ್ಲಿ ಈ ಆರ್ಡರ್‌ಗಳಿವೆ: {summary_items}. ನೀವು ಯಾವ ಆರ್ಡರ್ ಐಡಿಯನ್ನು ರದ್ದುಗೊಳಿಸಲು ಬಯಸುತ್ತೀರಿ?",
            "hinglish": f"Order cancel karne ke liye kripya order ID batayein. Aapke sample account mein yeh orders hain: {summary_items}{placed_hint}. Aap kaunsa order ID cancel karna chahte hain?",
            "ta": f"ஆர்டரை ரத்து செய்ய தயவுசெய்து ஆர்டர் ஐடியைக் குறிப்பிடவும். உங்கள் கணக்கில் உள்ள ஆர்டர்கள்: {summary_items}. எந்த ஆர்டர் ஐடியை ரத்து செய்ய விரும்புகிறீர்கள்?",
            "te": f"ఆర్డర్‌ను రద్దు చేయడానికి దయచేసి ఆర్డర్ ఐడిని తెలపండి. మీ ఖాతాలో ఈ ఆర్డర్లు ఉన్నాయి: {summary_items}. మీరు ఏ ఆర్డర్ ఐడిని రద్దు చేయాలనుకుంటున్నారు?",
        }
        return replies.get(lang, replies["en"])

    if intent == "refund_status":
        replies = {
            "en": f"You have multiple orders on your sample account: {summary_items}. Which order ID would you like me to check the refund status for?",
            "hi": f"आपके सैंपल खाते में एक से अधिक ऑर्डर हैं: {summary_items}। आप किस ऑर्डर आईडी के रिफंड की स्थिति जानना चाहते हैं?",
            "kn": f"ನಿಮ್ಮ ಖಾತೆಯಲ್ಲಿ ಹಲವು ಆರ್ಡರ್‌ಗಳಿವೆ: {summary_items}. ನೀವು ಯಾವ ಆರ್ಡರ್ ಐಡಿಯ ಮರುಪಾವತಿ ಸ್ಥಿತಿಯನ್ನು ಪರಿಶೀಲಿಸಲು ಬಯಸುತ್ತೀರಿ?",
            "hinglish": f"Aapke sample account mein multiple orders hain: {summary_items}. Aap kis order ID ka refund status check karna chahte hain?",
            "ta": f"உங்கள் கணக்கில் பல ஆர்டர்கள் உள்ளன: {summary_items}. எந்த ஆர்டர் ஐடியின் ரீஃபண்ட் நிலையைச் சரிபார்க்க வேண்டும்?",
            "te": f"మీ ఖాతాలో బహుళ ఆర్డర్లు ఉన్నాయి: {summary_items}. మీరు ఏ ఆర్డర్ ఐడి రీఫండ్ స్థితిని తనిఖీ చేయాలనుకుంటున్నారు?",
        }
        return replies.get(lang, replies["en"])

    # Default: order_status or local_expression
    prefix_en = "No tension at all! " if intent == "local_expression" else ""
    prefix_hi = "भाई बिल्कुल टेंशन मत लो! " if intent == "local_expression" else ""
    prefix_hing = "Bhai tension mat lo! " if intent == "local_expression" else ""
    replies = {
        "en": f"{prefix_en}You have multiple orders on your sample account: {summary_items}. Which order ID would you like to check?",
        "hi": f"{prefix_hi}आपके सैंपल खाते में एक से अधिक ऑर्डर हैं: {summary_items}। कृपया बताएं कि आप किस ऑर्डर आईडी की जानकारी चाहते हैं?",
        "kn": f"ನಿಮ್ಮ ಖಾತೆಯಲ್ಲಿ ಹಲವು ಆರ್ಡರ್‌ಗಳಿವೆ: {summary_items}. ನೀವು ಯಾವ ಆರ್ಡರ್ ಐಡಿಯನ್ನು ಪರಿಶೀಲಿಸಲು ಬಯಸುತ್ತೀರಿ?",
        "hinglish": f"{prefix_hing}Aapke sample account mein multiple orders hain: {summary_items}. Kripya batayein aap kis order ID ka status dekhna chahte hain?",
        "ta": f"உங்கள் கணக்கில் பல ஆர்டர்கள் உள்ளன: {summary_items}. எந்த ஆர்டர் ஐடியைச் சரிபார்க்க விரும்புகிறீர்கள்?",
        "te": f"మీ ఖాతాలో బహుళ ఆర్డర్లు ఉన్నాయి: {summary_items}. మీరు ఏ ఆర్డర్ ఐడిని తనిఖీ చేయాలనుకుంటున్నారు?",
    }
    return replies.get(lang, replies["en"])


def _build_customer_scoped_demo_reply(
    lang: str,
    intent: str,
    message: str,
    cust_id: str,
    company_name: str,
    history: list | None = None,
) -> tuple[str, str | None, str] | None:
    """Build a 100% customer-scoped Demo Mode reply from SQLite via tools.py.

    Returns (reply_text, tool_used, resolved_intent) or None if not a data-backed intent.
    """
    mentioned_oids = [m.upper() for m in re.findall(r"\bORD\d+\b", message, re.IGNORECASE)]
    not_found_map = DEMO_REPLIES["order_not_found"]

    # ---- 1. E-COMMERCE INTENTS OR MENTIONED ORDER IDs ----
    if mentioned_oids or intent in ("order_status", "refund_status", "cancel_order", "local_expression", "correction_order", "multipart_query"):
        effective_intent = intent
        if intent == "correction_order":
            effective_intent = _infer_prior_order_intent(history)

        # Case A: One or more order IDs explicitly mentioned in the message
        if mentioned_oids:
            target_oid = mentioned_oids[-1]
            order_info = execute_tool("get_order_status", {"order_id": target_oid}, customer_id=cust_id)
            if not order_info.get("success"):
                nf_text = not_found_map.get(lang, not_found_map["en"]).format(order_id=target_oid)
                if intent == "multipart_query" and any(w in message.lower() for w in ["return", "policy", "पॉलिसी", "ಪಾಲಿಸಿ", "கொள்கை", "పాలసీ"]):
                    faq_text = DEMO_REPLIES["faq"].get(lang, DEMO_REPLIES["faq"]["en"])
                    return f"{nf_text}\n\n{faq_text}", "get_order_status", "order_status"
                tool_name = (
                    "get_refund_status" if effective_intent == "refund_status"
                    else "cancel_order" if effective_intent == "cancel_order"
                    else "get_order_status"
                )
                return nf_text, tool_name, effective_intent

            # Order belongs to cust_id!
            if intent == "multipart_query":
                parts = []
                used_tool = "get_order_status"
                lower_msg = message.lower()
                if any(k in lower_msg for k in _INTENT_KEYWORDS["cancel_order"]):
                    c_res = execute_tool("cancel_order", {"order_id": target_oid}, customer_id=cust_id)
                    parts.append("1) " + _format_cancel_order_reply(lang, order_info, c_res))
                    used_tool = "cancel_order"
                if any(k in lower_msg for k in _INTENT_KEYWORDS["refund_status"]):
                    ref_info = execute_tool("get_refund_status", {"order_id": target_oid}, customer_id=cust_id)
                    parts.append(f"{len(parts)+1}) " + _format_refund_status_reply(lang, order_info, ref_info))
                    if used_tool == "get_order_status":
                        used_tool = "get_refund_status"
                if any(w in lower_msg for w in ["return", "policy", "पॉलिसी", "ಪಾಲಿಸಿ", "கொள்கை", "పాలసీ"]):
                    parts.append(f"{len(parts)+1}) " + DEMO_REPLIES["faq"].get(lang, DEMO_REPLIES["faq"]["en"]))
                if not parts:
                    parts.append(_format_order_status_reply(lang, order_info))
                return "\n".join(parts), used_tool, "order_status"

            if effective_intent == "refund_status":
                ref_info = execute_tool("get_refund_status", {"order_id": target_oid}, customer_id=cust_id)
                reply = _format_refund_status_reply(lang, order_info, ref_info)
                return reply, "get_refund_status", "refund_status"

            if effective_intent == "cancel_order":
                c_res = execute_tool("cancel_order", {"order_id": target_oid}, customer_id=cust_id)
                reply = _format_cancel_order_reply(lang, order_info, c_res)
                if intent == "correction_order":
                    prefix = {
                        "en": f"Got it, switching to order {target_oid}. ",
                        "hi": f"समझ गया, ऑर्डर {target_oid} की जाँच कर रहा हूँ। ",
                        "kn": f"ಅರ್ಥವಾಯಿತು, ಆರ್ಡರ್ {target_oid} ಪರಿಶೀಲಿಸುತ್ತಿದ್ದೇನೆ. ",
                        "hinglish": f"Samajh gaya, order {target_oid} par switch kar diya hai. ",
                        "ta": f"புரிந்தது, ஆர்டர் {target_oid}க்கு மாற்றுகிறேன். ",
                        "te": f"అర్థమైంది, ఆర్డర్ {target_oid}కి మారుస్తున్నాను. ",
                    }.get(lang, f"Got it, switching to order {target_oid}. ")
                    reply = prefix + reply
                return reply, "cancel_order", "cancel_order"

            # Default order status (including correction_order -> order_status or local_expression)
            reply = _format_order_status_reply(lang, order_info, is_local_expr=(intent == "local_expression"))
            if intent == "correction_order":
                prefix = {
                    "en": f"Got it, switching to order {target_oid}. ",
                    "hi": f"समझ गया, ऑर्डर {target_oid} की जानकारी: ",
                    "kn": f"ಅರ್ಥವಾಯಿತು, ಆರ್ಡರ್ {target_oid} ವಿವರ: ",
                    "hinglish": f"Samajh gaya, order {target_oid} ki details: ",
                    "ta": f"புரிந்தது, ஆர்டர் {target_oid} விவரம்: ",
                    "te": f"అర్థమైంది, ఆర్డర్ {target_oid} వివరాలు: ",
                }.get(lang, f"Got it, switching to order {target_oid}. ")
                reply = prefix + reply
            return reply, "get_order_status", "order_status"

        # Case B: No order ID mentioned in the message
        cust_orders_res = get_customer_orders(cust_id)
        orders = cust_orders_res if isinstance(cust_orders_res, list) else cust_orders_res.get("orders", [])

        if not orders:
            no_ord = {
                "en": "No orders were found for your sample account. Please share an order ID if you have one.",
                "hi": "आपके सैंपल खाते में कोई ऑर्डर नहीं मिला। यदि आपके पास कोई ऑर्डर आईडी है तो कृपया साझा करें।",
                "kn": "ನಿಮ್ಮ ಸ್ಯಾಂಪಲ್ ಖಾತೆಯಲ್ಲಿ ಯಾವುದೇ ಆರ್ಡರ್ ಕಂಡುಬಂದಿಲ್ಲ.",
                "hinglish": "Aapke sample account mein koi order nahi mila. Agar aapke paas order ID hai toh kripya share karein.",
                "ta": "உங்கள் மாதிரி கணக்கில் ஆர்டர்கள் எதுவும் இல்லை.",
                "te": "మీ శాంపిల్ ఖాతాలో ఆర్డర్లు ఏవీ కనుగొనబడలేదు.",
            }
            return no_ord.get(lang, no_ord["en"]), None, effective_intent

        # For cancellations, ALWAYS require an explicit order ID
        if effective_intent == "cancel_order":
            return _format_which_order_prompt(lang, orders, "cancel_order"), None, "cancel_order"

        # If the customer has only 1 order, use it directly
        if len(orders) == 1:
            single_order = orders[0]
            oid = single_order["order_id"]
            if effective_intent == "refund_status":
                ref_info = execute_tool("get_refund_status", {"order_id": oid}, customer_id=cust_id)
                return _format_refund_status_reply(lang, single_order, ref_info), "get_refund_status", "refund_status"
            return _format_order_status_reply(lang, single_order, is_local_expr=(intent == "local_expression")), "get_order_status", "order_status"

        # Multiple orders exist — check if the customer uniquely named one of their items
        lower_msg = message.lower()
        matched_by_item = [
            o for o in orders
            if any(word.lower() in lower_msg for word in o["item"].split() if len(word) >= 4)
        ]
        if len(matched_by_item) == 1:
            matched_order = matched_by_item[0]
            oid = matched_order["order_id"]
            if effective_intent == "refund_status":
                ref_info = execute_tool("get_refund_status", {"order_id": oid}, customer_id=cust_id)
                return _format_refund_status_reply(lang, matched_order, ref_info), "get_refund_status", "refund_status"
            return _format_order_status_reply(lang, matched_order, is_local_expr=(intent == "local_expression")), "get_order_status", "order_status"

        # Multiple possible records and no order ID specified -> ask which order they mean!
        prompt_reply = _format_which_order_prompt(lang, orders, effective_intent)
        if intent == "multipart_query" and any(w in lower_msg for w in ["return", "policy", "पॉलिसी", "ಪಾಲಿಸಿ", "கொள்கை", "పాలసీ"]):
            faq_text = DEMO_REPLIES["faq"].get(lang, DEMO_REPLIES["faq"]["en"])
            prompt_reply = f"{prompt_reply}\n\n{faq_text}"
        return prompt_reply, None, effective_intent

    # ---- 2. BANKING INTENTS ----
    if intent == "account_info":
        res = execute_tool("get_account_info", {"customer_id": cust_id}, customer_id=cust_id)
        if not res.get("success"):
            return DEMO_REPLIES["unavailable_info"].get(lang, DEMO_REPLIES["unavailable_info"]["en"]).replace("{company}", company_name), "get_account_info", intent
        plan = res["plan_name"]
        bal = res["balance"]
        due = res.get("due_date") or "N/A"
        replies = {
            "en": f"Your {plan} account ({cust_id}) has a sample balance of ₹{bal:,.2f}. Your next statement/due date is {due}.",
            "hi": f"आपके {plan} खाते ({cust_id}) में ₹{bal:,.2f} का सैंपल बैलेंस है। अगली स्टेटमेंट तिथि {due} है।",
            "kn": f"ನಿಮ್ಮ {plan} ಖಾತೆಯಲ್ಲಿ ({cust_id}) ₹{bal:,.2f} ಸ್ಯಾಂಪಲ್ ಬ್ಯಾಲೆನ್ಸ್ ಇದೆ. ಮುಂದಿನ ದಿನಾಂಕ {due}.",
            "hinglish": f"Aapke {plan} account ({cust_id}) mein ₹{bal:,.2f} ka sample balance hai. Next statement date {due} hai.",
            "ta": f"உங்கள் {plan} கணக்கில் ({cust_id}) ₹{bal:,.2f} மாதிரி இருப்பு உள்ளது. அடுத்த தேதி {due}.",
            "te": f"మీ {plan} ఖాతాలో ({cust_id}) ₹{bal:,.2f} శాంపిల్ బ్యాలెన్స్ ఉంది. తదుపరి తేదీ {due}.",
        }
        return replies.get(lang, replies["en"]), "get_account_info", intent

    if intent == "recent_transactions":
        res = execute_tool("get_recent_transactions", {"customer_id": cust_id}, customer_id=cust_id)
        if not res.get("success") or not res.get("transactions"):
            return DEMO_REPLIES["unavailable_info"].get(lang, DEMO_REPLIES["unavailable_info"]["en"]).replace("{company}", company_name), "get_recent_transactions", intent
        txns = res["transactions"]
        txn_summary = "; ".join(
            f"{i+1}) {t['description']} {'+' if t['type']=='credit' else '-'}₹{t['amount']:,.0f} ({t['date']})"
            for i, t in enumerate(txns)
        )
        replies = {
            "en": f"Here are the last {len(txns)} sample transactions for {cust_id}: {txn_summary}.",
            "hi": f"खाता {cust_id} के पिछले {len(txns)} सैंपल लेन-देन: {txn_summary}।",
            "kn": f"ಖಾತೆ {cust_id} ನ ಕೊನೆಯ {len(txns)} ಸ್ಯಾಂಪಲ್ ವಹಿವಾಟುಗಳು: {txn_summary}.",
            "hinglish": f"Account {cust_id} ke last {len(txns)} sample transactions: {txn_summary}.",
            "ta": f"கணக்கு {cust_id}க்கான கடந்த {len(txns)} மாதிரி பரிவர்த்தனைகள்: {txn_summary}.",
            "te": f"ఖాతా {cust_id} యొక్క చివరి {len(txns)} శాంపిల్ లావాదేవీలు: {txn_summary}.",
        }
        return replies.get(lang, replies["en"]), "get_recent_transactions", intent

    if intent == "block_card":
        res = execute_tool("block_card", {"customer_id": cust_id}, customer_id=cust_id)
        ref_no = res.get("reference_id", f"BLK-{cust_id}")
        replies = {
            "en": f"Your card for account {cust_id} has been blocked in this demo simulation (Ref: {ref_no}). A replacement card request has been logged.",
            "hi": f"खाता {cust_id} का आपका कार्ड इस डेमो सिमुलेशन में ब्लॉक कर दिया गया है (संदर्भ: {ref_no})। नए कार्ड का अनुरोध दर्ज हो गया है।",
            "kn": f"ಖಾತೆ {cust_id} ನ ನಿಮ್ಮ ಕಾರ್ಡ್ ಅನ್ನು ಈ ಡೆಮೊ ಸಿಮ್ಯುಲೇಶನ್‌ನಲ್ಲಿ ಬ್ಲಾಕ್ ಮಾಡಲಾಗಿದೆ (Ref: {ref_no}).",
            "hinglish": f"Account {cust_id} ka aapka card is demo simulation mein turant block kar diya gaya hai (Ref: {ref_no}). Replacement card request log ho gayi hai.",
            "ta": f"கணக்கு {cust_id}க்கான உங்கள் கார்டு இந்த டெமோ சிமுலேஷனில் தடுக்கப்பட்டுள்ளது (Ref: {ref_no}).",
            "te": f"ఖాతా {cust_id} కోసం మీ కార్డ్ ఈ డెమో సిమ్యులేషన్‌లో బ్లాక్ చేయబడింది (Ref: {ref_no}).",
        }
        return replies.get(lang, replies["en"]), "block_card", intent

    if intent == "loan_info":
        res = execute_tool("get_loan_info", {"customer_id": cust_id}, customer_id=cust_id)
        if not res.get("success") or res.get("loan_type") == "None":
            replies = {
                "en": f"No active loan was found on your sample account ({cust_id}). Would you like to check your account balance or enquire about new loan eligibility?",
                "hi": f"आपके सैंपल खाते ({cust_id}) पर कोई सक्रिय लोन नहीं मिला। क्या आप अपना खाता बैलेंस या नए लोन की पात्रता जानना चाहेंगे?",
                "kn": f"ನಿಮ್ಮ ಸ್ಯಾಂಪಲ್ ಖಾತೆಯಲ್ಲಿ ({cust_id}) ಯಾವುದೇ ಸಕ್ರಿಯ ಸಾಲ ಕಂಡುಬಂದಿಲ್ಲ. ನಿಮ್ಮ ಖಾತೆಯ ಬ್ಯಾಲೆನ್ಸ್ ಪರಿಶೀಲಿಸಲೇ?",
                "hinglish": f"Aapke sample account ({cust_id}) par koi active loan nahi mila. Kya aap apna account balance ya loan eligibility check karna chahenge?",
                "ta": f"உங்கள் மாதிரி கணக்கில் ({cust_id}) செயலில் உள்ள கடன் எதுவும் இல்லை. உங்கள் கணக்கு இருப்பைச் சரிபார்க்கட்டுமா?",
                "te": f"మీ శాంపిల్ ఖాతాలో ({cust_id}) యాక్టివ్ లోన్ ఏదీ కనుగొనబడలేదు. మీ ఖాతా బ్యాలెన్స్ తనిఖీ చేయమంటారా?",
            }
            return replies.get(lang, replies["en"]), "get_loan_info", intent
        ltype = res["loan_type"]
        prin = res["principal"]
        emi = res["emi_amount"]
        rem = res["remaining_emis"]
        ndate = res["next_emi_date"]
        replies = {
            "en": f"Your sample {ltype} details ({cust_id}): Principal ₹{prin:,.0f}, EMI ₹{emi:,.0f}/month, {rem} EMIs remaining. Next EMI due on {ndate}.",
            "hi": f"आपके सैंपल {ltype} का विवरण ({cust_id}): मूलधन ₹{prin:,.0f}, EMI ₹{emi:,.0f}/माह, {rem} EMI शेष। अगली EMI {ndate} को देय है।",
            "kn": f"ನಿಮ್ಮ ಸ್ಯಾಂಪಲ್ {ltype} ವಿವರ ({cust_id}): ಮೂಲ ₹{prin:,.0f}, EMI ₹{emi:,.0f}/ತಿಂಗಳು, {rem} EMI ಬಾಕಿ. ಮುಂದಿನ EMI {ndate}.",
            "hinglish": f"Aapke sample {ltype} ki details ({cust_id}): Principal ₹{prin:,.0f}, EMI ₹{emi:,.0f}/month, {rem} EMIs baki hain. Next EMI {ndate} ko hai.",
            "ta": f"உங்கள் மாதிரி {ltype} விவரங்கள் ({cust_id}): அசல் ₹{prin:,.0f}, EMI ₹{emi:,.0f}/மாதம், {rem} EMI மீதமுள்ளது. அடுத்த EMI {ndate}.",
            "te": f"మీ శాంపిల్ {ltype} వివరాలు ({cust_id}): ప్రిన్సిపల్ ₹{prin:,.0f}, EMI ₹{emi:,.0f}/నెల, {rem} EMIలు మిగిలి ఉన్నాయి. తదుపరి EMI {ndate}.",
        }
        return replies.get(lang, replies["en"]), "get_loan_info", intent

    # ---- 3. TELECOM INTENTS ----
    if intent == "plan_details":
        res = execute_tool("get_plan_details", {"customer_id": cust_id}, customer_id=cust_id)
        if not res.get("success"):
            return DEMO_REPLIES["unavailable_info"].get(lang, DEMO_REPLIES["unavailable_info"]["en"]).replace("{company}", company_name), "get_plan_details", intent
        plan = res["plan_name"]
        bal = res["balance"]
        due = res.get("due_date") or "N/A"
        replies = {
            "en": f"Your telecom account ({cust_id}) is on the '{plan}' plan (amount/balance: ₹{bal:,.0f}, validity/due date: {due}, sample data).",
            "hi": f"आपका टेलीकॉम खाता ({cust_id}) '{plan}' प्लान पर है (राशि/बैलेंस: ₹{bal:,.0f}, वैधता/देय तिथि: {due}, सैंपल डेटा)।",
            "kn": f"ನಿಮ್ಮ ಟೆಲಿಕಾಂ ಖಾತೆ ({cust_id}) '{plan}' ಪ್ಲಾನ್‌ನಲ್ಲಿದೆ (ಮೊತ್ತ: ₹{bal:,.0f}, ದಿನಾಂಕ: {due}, ಸ್ಯಾಂಪಲ್ ಡೇಟಾ).",
            "hinglish": f"Aapka telecom account ({cust_id}) '{plan}' plan par hai (amount/balance: ₹{bal:,.0f}, validity/due date: {due}, sample data).",
            "ta": f"உங்கள் டெலிகாம் கணக்கு ({cust_id}) '{plan}' திட்டத்தில் உள்ளது (தொகை: ₹{bal:,.0f}, தேதி: {due}, மாதிரி தரவு).",
            "te": f"మీ టెలికాం ఖాతా ({cust_id}) '{plan}' ప్లాన్‌లో ఉంది (మొత్తం: ₹{bal:,.0f}, తేదీ: {due}, శాంపిల్ డేటా).",
        }
        return replies.get(lang, replies["en"]), "get_plan_details", intent

    if intent == "data_usage":
        res = execute_tool("get_data_usage", {"customer_id": cust_id}, customer_id=cust_id)
        if not res.get("success"):
            return DEMO_REPLIES["unavailable_info"].get(lang, DEMO_REPLIES["unavailable_info"]["en"]).replace("{company}", company_name), "get_data_usage", intent
        used = res["used_today_gb"]
        lim = res["daily_limit_gb"]
        rem = res["remaining_gb"]
        plan = res["plan_name"]
        replies = {
            "en": f"On your '{plan}' plan ({cust_id}), you have used {used} GB out of your {lim} GB daily limit today ({rem} GB remaining, sample data).",
            "hi": f"आपके '{plan}' प्लान ({cust_id}) पर आज आपने {lim} GB दैनिक सीमा में से {used} GB डेटा उपयोग किया है ({rem} GB शेष, सैंपल डेटा)।",
            "kn": f"ನಿಮ್ಮ '{plan}' ಪ್ಲಾನ್‌ನಲ್ಲಿ ({cust_id}) ಇಂದು {lim} GB ಮಿತಿಯಲ್ಲಿ {used} GB ಬಳಸಿದ್ದೀರಿ ({rem} GB ಉಳಿದಿದೆ, ಸ್ಯಾಂಪಲ್ ಡೇಟಾ).",
            "hinglish": f"Aapke '{plan}' plan ({cust_id}) par aaj aapne {lim} GB daily limit mein se {used} GB use kiya hai ({rem} GB remaining, sample data).",
            "ta": f"உங்கள் '{plan}' திட்டத்தில் ({cust_id}) இன்று {lim} GB வரம்பில் {used} GB பயன்படுத்தியுள்ளீர்கள் ({rem} GB மீதமுள்ளது, மாதிரி தரவு).",
            "te": f"మీ '{plan}' ప్లాన్‌లో ({cust_id}) ఈ రోజు {lim} GB లిమిట్‌లో {used} GB వాడారు ({rem} GB మిగిలి ఉంది, శాంపిల్ డేటా).",
        }
        return replies.get(lang, replies["en"]), "get_data_usage", intent

    if intent == "recharge_status":
        res = execute_tool("get_recharge_status", {"customer_id": cust_id}, customer_id=cust_id)
        if not res.get("success"):
            return DEMO_REPLIES["unavailable_info"].get(lang, DEMO_REPLIES["unavailable_info"]["en"]).replace("{company}", company_name), "get_recharge_status", intent
        rdate = res["last_recharge_date"]
        ramt = res["last_recharge_amount"]
        rval = res["plan_valid_until"]
        replies = {
            "en": f"For account {cust_id}, your last recharge of ₹{ramt:,.0f} on {rdate} was successful. Your plan is valid until {rval} (sample data).",
            "hi": f"खाता {cust_id} के लिए आपका पिछला रिचार्ज ₹{ramt:,.0f} ({rdate}) सफल रहा। आपका प्लान {rval} तक वैध है (सैंपल डेटा)।",
            "kn": f"ಖಾತೆ {cust_id} ಗಾಗಿ ನಿಮ್ಮ ಕೊನೆಯ ₹{ramt:,.0f} ರೀಚಾರ್ಜ್ ({rdate}) ಯಶಸ್ವಿಯಾಗಿದೆ. ಪ್ಲಾನ್ {rval} ವರೆಗೆ ಮಾನ್ಯವಾಗಿದೆ (ಸ್ಯಾಂಪಲ್ ಡೇಟಾ).",
            "hinglish": f"Account {cust_id} ke liye aapka last recharge ₹{ramt:,.0f} ({rdate}) successful raha. Plan {rval} tak valid hai (sample data).",
            "ta": f"கணக்கு {cust_id}க்கான உங்கள் கடைசி ₹{ramt:,.0f} ரீசார்ஜ் ({rdate}) வெற்றிகரமாக முடிந்தது. திட்டம் {rval} வரை செல்லுபடியாகும் (மாதிரி தரவு).",
            "te": f"ఖాతా {cust_id} కోసం మీ చివరి ₹{ramt:,.0f} రీచార్జ్ ({rdate}) విజయవంతమైంది. ప్లాన్ {rval} వరకు చెల్లుబాటు అవుతుంది (శాంపిల్ డేటా).",
        }
        return replies.get(lang, replies["en"]), "get_recharge_status", intent

    if intent == "bill_info":
        res = execute_tool("get_bill_info", {"customer_id": cust_id}, customer_id=cust_id)
        if not res.get("success"):
            return DEMO_REPLIES["unavailable_info"].get(lang, DEMO_REPLIES["unavailable_info"]["en"]).replace("{company}", company_name), "get_bill_info", intent
        plan = res.get("plan_name", "Plan")
        if "bill_amount" in res:
            bamt = res["bill_amount"]
            bdue = res["due_date"]
            replies = {
                "en": f"Your postpaid bill ({plan}, {cust_id}) of ₹{bamt:,.0f} is due on {bdue} (status: {res.get('status', 'unpaid')}, sample data).",
                "hi": f"आपका पोस्टपेड बिल ({plan}, {cust_id}) ₹{bamt:,.0f} {bdue} को देय है (सैंपल डेटा)।",
                "kn": f"ನಿಮ್ಮ ಪೋಸ್ಟ್‌ಪೇಡ್ ಬಿಲ್ ({plan}, {cust_id}) ₹{bamt:,.0f} ದಿನಾಂಕ {bdue} ರೊಳಗೆ ಪಾವತಿಸಬೇಕು (ಸ್ಯಾಂಪಲ್ ಡೇಟಾ).",
                "hinglish": f"Aapka postpaid bill ({plan}, {cust_id}) ₹{bamt:,.0f} {bdue} tak due hai (sample data).",
                "ta": f"உங்கள் போஸ்ட்பெய்ட் பில் ({plan}, {cust_id}) ₹{bamt:,.0f} தேதி {bdue}க்குள் செலுத்த வேண்டும் (மாதிரி தரவு).",
                "te": f"మీ పోస్ట్‌పెయిడ్ బిల్ ({plan}, {cust_id}) ₹{bamt:,.0f} తేదీ {bdue} లోపు చెల్లించాలి (శాంపిల్ డేటా).",
            }
        else:
            replies = {
                "en": f"Your account ({cust_id}) is on a prepaid plan ({plan}), so there is no monthly postpaid bill. Would you like to check your recharge status or data usage instead?",
                "hi": f"आपका खाता ({cust_id}) प्रीपेड प्लान ({plan}) पर है, इसलिए कोई मासिक पोस्टपेड बिल नहीं है। क्या आप अपना रिचार्ज या डेटा उपयोग देखना चाहेंगे?",
                "kn": f"ನಿಮ್ಮ ಖಾತೆ ({cust_id}) ಪ್ರಿಪೇಡ್ ಪ್ಲಾನ್ ({plan}) ಆಗಿರುವುದರಿಂದ ಮಾಸಿಕ ಬಿಲ್ ಇಲ್ಲ. ನಿಮ್ಮ ರೀಚಾರ್ಜ್ ಅಥವಾ ಡೇಟಾ ಬಳಕೆಯನ್ನು ಪರಿಶೀಲಿಸಲೇ?",
                "hinglish": f"Aapka account ({cust_id}) prepaid plan ({plan}) par hai, isliye koi monthly postpaid bill nahi hai. Kya aap recharge status ya data usage check karna chahenge?",
                "ta": f"உங்கள் கணக்கு ({cust_id}) ப்ரீபெய்ட் திட்டத்தில் ({plan}) உள்ளதால் மாதாந்திர பில் இல்லை. உங்கள் ரீசார்ஜ் அல்லது டேட்டா பயன்பாட்டைச் சரிபார்க்கட்டுமா?",
                "te": f"మీ ఖాతా ({cust_id}) ప్రీపెయిడ్ ప్లాన్ ({plan})లో ఉన్నందున నెలవారీ బిల్లు లేదు. మీ రీచార్జ్ స్థితి లేదా డేటా వినియోగాన్ని తనిఖీ చేయమంటారా?",
            }
        return replies.get(lang, replies["en"]), "get_bill_info", intent

    return None


def get_demo_response(message: str, pack_tools: list = None,
                      company_name: str = "Support", history: list = None,
                      is_after_hours: bool = False,
                      selected_language: str | None = None,
                      customer_profile: dict | None = None) -> dict:
    """Return a customer-grounded response for demo mode, in the selected or detected language."""
    from datetime import datetime, timedelta

    forced = (selected_language or "").strip().lower()
    lang = forced if (forced and forced != "auto" and forced in LANGUAGE_SPECS) else detect_language_from_script(message)
    intent = _detect_demo_intent(message, pack_tools or [], history)
    future_date = (datetime.now() + timedelta(days=15)).strftime("%d %B %Y")
    cust_id = (customer_profile or {}).get("id", "CUST001").strip().upper()

    # 1. Check customer-scoped data-backed reply (E-commerce, Bank, Telecom)
    scoped = _build_customer_scoped_demo_reply(
        lang=lang,
        intent=intent,
        message=message,
        cust_id=cust_id,
        company_name=company_name,
        history=history,
    )
    if scoped is not None:
        scoped_reply, scoped_tool, resolved_intent = scoped
        sentiment = "frustrated" if intent == "local_expression" else "neutral"
        return _demo(
            lang=lang,
            sentiment=sentiment,
            intent=resolved_intent,
            confidence=0.94,
            reply=scoped_reply,
            tool_used=scoped_tool,
        )

    # 2. If escalating after hours, use the simulated callback queued reply
    if is_after_hours and intent in ("escalation", "low_confidence_escalate"):
        cb_replies = DEMO_REPLIES["escalation_after_hours"]
        reply = cb_replies.get(lang, cb_replies.get("en", ""))
        reply = reply.replace("{date}", future_date).replace("{company}", company_name)
        triggers = ["After hours callback"]
        if intent == "escalation":
            triggers.insert(0, "Customer requested human agent")
            esc_reason = "Customer requested human agent outside working hours (queued callback simulation)"
        else:
            triggers.insert(0, "Low Confidence (38%)")
            esc_reason = "Cannot resolve confidently outside working hours (queued callback simulation)"
        return _demo(
            lang,
            "frustrated" if intent == "low_confidence_escalate" else "angry",
            "human_request",
            0.40,
            reply,
            escalate=True,
            esc_reason=esc_reason,
            triggers=triggers,
        )

    # 3. Non-record templates (FAQ, escalation, off_topic, out_of_scope_pack, vague_clarification, greeting, unavailable_info)
    intent_replies = DEMO_REPLIES.get(intent, DEMO_REPLIES["greeting"])
    reply = intent_replies.get(lang, intent_replies.get("en", "How can I help you?"))
    reply = reply.replace("{date}", future_date).replace("{company}", company_name)

    if intent == "escalation":
        return _demo(
            lang, "angry", "human_request", 0.40, reply,
            escalate=True,
            esc_reason="Customer requested human agent (demo handoff simulation)",
            triggers=["Angry Tone", "Customer requested human agent"],
        )
    if intent == "low_confidence_escalate":
        return _demo(
            lang, "frustrated", "other", 0.38, reply,
            escalate=True,
            esc_reason="Cannot resolve confidently after clarification (demo handoff simulation)",
            triggers=["Low Confidence (38%)"],
        )
    if intent == "vague_clarification":
        return _demo(lang, "neutral", "clarification", 0.52, reply, escalate=False)
    if intent == "off_topic":
        return _demo(lang, "neutral", "off_topic", 0.95, reply)
    if intent == "out_of_scope_pack":
        return _demo(lang, "neutral", "out_of_scope", 0.90, reply)
    if intent == "unavailable_info":
        return _demo(lang, "neutral", "unavailable_info", 0.85, reply)

    return _demo(lang, "neutral", intent, 0.92, reply)


# ---------------------------------------------------------------------------
# JSON parsing helper
# ---------------------------------------------------------------------------

def _parse_ai_json(text: str) -> dict | None:
    """Extract and parse JSON from the AI response text."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


def _default_response(message="I'm sorry, I didn't understand. Could you rephrase?"):
    """Return a safe default response when parsing fails."""
    return {
        "language": "en", "sentiment": "neutral", "intent": "other",
        "confidence": 0.5, "tool_call": None, "reply": message,
        "escalate": False, "escalation_reason": "", "escalation_triggers": [],
    }


# ---------------------------------------------------------------------------
# Main chat function
# ---------------------------------------------------------------------------

_PREFERRED_MODEL = DEFAULT_MODEL
_MODEL_CANDIDATES = list(MODEL_CANDIDATES)
_MODEL_COOLDOWN: dict[str, float] = {}
_CONNECTION_CACHE: dict = {}
_CLIENT_CACHE: dict = {}

# Automatic fallback & hedged latency settings (Part B5)
HEDGE_DELAY_S = 2.5                           # 2.5s wait before hedging with fast secondary model
MAX_PARALLEL_ATTEMPTS = 2                     # primary + 1 fallback attempt with short backoff
FIRST_TEXT_DEADLINE_S = TOTAL_REQUEST_TIMEOUT_SECONDS  # hard request timeout
_MODEL_TTFT_EWMA: dict[str, float] = {}       # observed time-to-first-text per model (seconds)


def _record_ttft(model: str, seconds: float):
    prev = _MODEL_TTFT_EWMA.get(model)
    _MODEL_TTFT_EWMA[model] = seconds if prev is None else (0.6 * prev + 0.4 * seconds)


def _get_genai_client(api_key: str):
    """Return cached google.genai.Client via warmup."""
    client = get_cached_genai_client(api_key)
    if client is not None:
        return client
    from google import genai
    return genai.Client(api_key=api_key)


def _ordered_candidates() -> list[str]:
    """Order models: not cooling down first, then by observed TTFT (fastest first), preferred as tiebreak."""
    now_ts = time.time()
    ready = [m for m in _MODEL_CANDIDATES if _MODEL_COOLDOWN.get(m, 0) < now_ts]
    if not ready:
        ready = list(_MODEL_CANDIDATES)

    def _key(m):
        observed = _MODEL_TTFT_EWMA.get(m)
        # Unmeasured models get a neutral estimate so they are still tried as backups
        est = observed if observed is not None else 8.0
        return (est, 0 if m == _PREFERRED_MODEL else 1, _MODEL_CANDIDATES.index(m))

    return sorted(ready, key=_key)


def _hedged_stream(client, candidates, contents, make_config, on_partial=None, on_status=None):
    """Stream from Gemini with hedged backup requests.

    Worker threads only do network I/O and push events to a queue; all callbacks
    (on_partial / on_status) run on the caller's thread so Streamlit UI updates stay safe.

    Returns (full_raw_text, winning_model, t_first_text_perf_counter).
    Raises RuntimeError if no model produced text before FIRST_TEXT_DEADLINE_S.
    """
    import queue
    import threading

    events: "queue.Queue[tuple]" = queue.Queue()
    winner_box = {"model": None}
    started: list[str] = []
    finished_err: set[str] = set()

    def _worker(model_name: str, t_launch: float):
        try:
            for chunk in client.models.generate_content_stream(
                model=model_name, contents=contents, config=make_config(model_name),
            ):
                if winner_box["model"] not in (None, model_name):
                    return  # another model won; stop consuming (result discarded)
                text = chunk.text or ""
                if text:
                    events.put(("text", model_name, text, time.perf_counter() - t_launch))
            events.put(("done", model_name, None, None))
        except Exception as exc:  # report to caller thread
            events.put(("error", model_name, exc, None))

    def _launch(model_name: str):
        started.append(model_name)
        threading.Thread(target=_worker, args=(model_name, time.perf_counter()), daemon=True).start()

    queue_models = list(candidates)
    t0 = time.perf_counter()
    _launch(queue_models.pop(0))
    next_hedge_at = t0 + HEDGE_DELAY_S

    raw = ""
    last_len = 0
    t_first = None

    while True:
        now = time.perf_counter()
        if winner_box["model"] is None:
            if now - t0 > FIRST_TEXT_DEADLINE_S:
                raise RuntimeError(f"Gemini did not respond within {int(FIRST_TEXT_DEADLINE_S)}s (models tried: {', '.join(started)})")
            # Launch a backup if the current attempts are slow (or all have errored)
            all_errored = len(finished_err) == len(started)
            if queue_models and len(started) < MAX_PARALLEL_ATTEMPTS and (now >= next_hedge_at or all_errored):
                backup = queue_models.pop(0)
                if on_status:
                    on_status(f"Gemini is busy — also trying {backup}…")
                print(f"[llm.py] No first text after {now - t0:.1f}s; hedging with {backup}")
                _launch(backup)
                next_hedge_at = now + HEDGE_DELAY_S
            elif all_errored and not queue_models:
                raise RuntimeError("All model candidates unavailable")
            elif all_errored and len(started) >= MAX_PARALLEL_ATTEMPTS and queue_models:
                # All parallel slots errored quickly (e.g. 429/503) — try the next one
                backup = queue_models.pop(0)
                _launch(backup)

        timeout = 0.25
        try:
            kind, model_name, payload, elapsed = events.get(timeout=timeout)
        except queue.Empty:
            continue

        if kind == "error":
            err_str = str(payload)
            if any(code in err_str for code in ("404", "429", "400")):
                _MODEL_COOLDOWN[model_name] = time.time() + 120.0
            elif any(code in err_str for code in ("503", "504")):
                _MODEL_COOLDOWN[model_name] = time.time() + 15.0
            print(f"[llm.py] Model {model_name} failed: {err_str[:90]}")
            if winner_box["model"] == model_name:
                raise payload  # mid-stream failure of the winner
            finished_err.add(model_name)
            continue

        if winner_box["model"] is None and kind == "text":
            winner_box["model"] = model_name
            t_first = time.perf_counter()
            _record_ttft(model_name, elapsed)
            # Penalise losers that were still waiting so the next turn prefers the faster model
            for other in started:
                if other != model_name and other not in finished_err:
                    _record_ttft(other, max(elapsed, time.perf_counter() - t0) + 2.0)

        if model_name != winner_box["model"]:
            if kind == "done" and winner_box["model"] is None:
                finished_err.add(model_name)  # finished without any text — treat as failed attempt
            continue  # discard output from losing attempts

        if kind == "text":
            raw += payload
            curr = _extract_partial_reply(raw)
            if curr and len(curr) > last_len:
                last_len = len(curr)
                if on_partial:
                    on_partial(curr)
        elif kind == "done":
            return raw, model_name, t_first


def _get_genai_client(api_key: str):
    """Return a cached google.genai.Client for the given API key to reuse TCP/TLS connections."""
    # pyrefly: ignore[missing-import]
    from google import genai
    if _CLIENT_CACHE.get("key") != api_key or _CLIENT_CACHE.get("client") is None:
        _CLIENT_CACHE["key"] = api_key
        _CLIENT_CACHE["client"] = genai.Client(api_key=api_key)
    return _CLIENT_CACHE["client"]


def _build_live_db_context(
    customer_profile: dict | None,
    user_message: str,
    history: list,
    available_tools: list | None = None,
) -> str:
    """Pre-fetch live SQLite records strictly scoped to the selected customer and active pack (<1ms).

    Never fetches or reveals another customer's name, order status, item, or refund details.
    """
    try:
        from database import get_connection
        from tools import get_loan_info, get_data_usage, get_recharge_status, get_bill_info, get_recent_transactions
        cust_id = (customer_profile or {}).get("id", "CUST001").strip().upper()
        cust_name = (customer_profile or {}).get("name", "Current Customer")

        tool_set = set(available_tools or [])
        needs_ecommerce = not tool_set or bool(
            tool_set.intersection({"get_order_status", "cancel_order", "get_refund_status"})
        )
        needs_acct = not tool_set or bool(
            tool_set.intersection({
                "get_account_info", "get_recent_transactions", "block_card",
                "get_loan_info", "get_plan_details", "get_data_usage",
                "get_recharge_status", "get_bill_info",
            })
        )

        combined_text = user_message + " " + " ".join(m.get("content", "") for m in (history or [])[-4:])
        mentioned_orders = {m.upper() for m in re.findall(r"\bORD\d+\b", combined_text, re.IGNORECASE)}

        conn = get_connection()
        found_orders = {}
        refund_rows = {}
        if needs_ecommerce or mentioned_orders:
            orders_rows = conn.execute(
                "SELECT o.*, c.name AS customer_name FROM orders o JOIN customers c ON o.customer_id = c.id "
                "WHERE UPPER(o.customer_id) = ?",
                (cust_id,),
            ).fetchall()
            found_orders = {r["order_id"].upper(): dict(r) for r in orders_rows}

            if found_orders:
                placeholders = ",".join("?" for _ in found_orders)
                r_rows = conn.execute(
                    f"SELECT r.*, o.item FROM refunds r JOIN orders o ON r.order_id = o.order_id "
                    f"WHERE r.order_id IN ({placeholders}) AND UPPER(o.customer_id) = ?",
                    tuple(found_orders.keys()) + (cust_id,),
                ).fetchall()
                refund_rows = {r["order_id"].upper(): dict(r) for r in r_rows}

        acct_row = None
        if needs_acct:
            acct_row = conn.execute(
                "SELECT a.*, c.name AS customer_name FROM accounts a JOIN customers c ON a.customer_id = c.id "
                "WHERE UPPER(a.customer_id) = ?",
                (cust_id,),
            ).fetchone()
        conn.close()

        lines = [
            f"Data Source: Sample / Demo SQLite Records (Customer: {cust_name}, ID: {cust_id})",
            f"Handoff Integration: {'Connected' if LIVE_HANDOFF_CONNECTED else 'Demo Simulation Only (No live agent or callback service connected)'}",
        ]
        if needs_ecommerce or mentioned_orders:
            if found_orders:
                lines.append(f"Orders belonging to current customer {cust_name} ({cust_id}):")
                for oid, o in sorted(found_orders.items()):
                    ref = refund_rows.get(oid)
                    ref_str = (
                        f" | Refund {ref['refund_id']}: status={ref['status']}, amount=₹{ref['amount']}, initiated_on={ref['initiated_on']}"
                        if ref else " | No refund record"
                    )
                    lines.append(
                        f"- {oid}: item='{o['item']}', amount=₹{o['amount']}, "
                        f"status='{o['status']}', expected_date={o['expected_date']}{ref_str}"
                    )
            else:
                lines.append(f"Orders belonging to current customer {cust_name} ({cust_id}): None")

            for oid in sorted(mentioned_orders):
                if oid not in found_orders:
                    lines.append(
                        f"- {oid}: NOT FOUND for current customer {cust_name} ({cust_id}). "
                        f"Do NOT share any details, owner name, status, or refund info about {oid}; "
                        f"politely tell the customer that order {oid} cannot be found for the current customer "
                        f"and ask them to provide the correct order ID."
                    )

        if acct_row:
            lines.append(
                f"Account/Plan for {cust_id} ({acct_row['customer_name']}): "
                f"plan_name='{acct_row['plan_name']}', balance=₹{acct_row['balance']}, due_date={acct_row['due_date']}"
            )
            if not tool_set or "get_data_usage" in tool_set:
                data_info = get_data_usage(cust_id)
                if data_info.get("success"):
                    lines.append(
                        f"Data usage for {cust_id}: daily_limit={data_info['daily_limit_gb']}GB, "
                        f"used_today={data_info['used_today_gb']}GB, remaining={data_info['remaining_gb']}GB"
                    )
            if not tool_set or "get_recharge_status" in tool_set:
                rech_info = get_recharge_status(cust_id)
                if rech_info.get("success"):
                    lines.append(
                        f"Last recharge for {cust_id}: date={rech_info['last_recharge_date']}, "
                        f"amount=₹{rech_info['last_recharge_amount']}, status={rech_info['status']}"
                    )
            if not tool_set or "get_bill_info" in tool_set:
                bill_info = get_bill_info(cust_id)
                if bill_info.get("success") and "bill_amount" in bill_info:
                    lines.append(
                        f"Postpaid bill for {cust_id}: bill_amount=₹{bill_info['bill_amount']}, "
                        f"due_date={bill_info['due_date']}, status={bill_info['status']}"
                    )
            if not tool_set or "get_loan_info" in tool_set:
                loan_info = get_loan_info(cust_id)
                if loan_info.get("success") and loan_info.get("loan_type") != "None":
                    lines.append(
                        f"Active loan for {cust_id}: type={loan_info['loan_type']}, principal=₹{loan_info['principal']}, "
                        f"emi=₹{loan_info['emi_amount']}, remaining_emis={loan_info['remaining_emis']}, next_emi_date={loan_info['next_emi_date']}"
                    )
                else:
                    lines.append(f"Active loan for {cust_id}: None")
            if "get_recent_transactions" in tool_set:
                txn_info = get_recent_transactions(cust_id)
                if txn_info.get("success") and txn_info.get("transactions"):
                    txn_str = "; ".join(
                        f"{t['date']}: {t['description']} ({'+' if t['type']=='credit' else '-'}₹{t['amount']})"
                        for t in txn_info["transactions"]
                    )
                    lines.append(f"Recent 5 transactions for {cust_id}: {txn_str}")
        return "\n".join(lines)
    except Exception as e:
        print(f"[llm.py] _build_live_db_context error: {e}")
        return ""


def _is_placeholder_reply(reply_text: str) -> bool:
    """Return True only if the reply is a short 'I am checking...' filler without the actual answer."""
    low = (reply_text or "").strip().lower()
    if not low:
        return True
    filler_phrases = (
        "i am checking", "i'm checking", "let me check", "checking the status",
        "checking your", "please wait", "one moment", "ek minute", "check kar raha", "check kar rahi"
    )
    return len(low.split()) < 16 and any(p in low for p in filler_phrases)


def check_gemini_connection(api_key: str) -> dict:
    """Verify the Gemini API key and model availability with a real API request."""
    global _PREFERRED_MODEL, _CONNECTION_CACHE
    if not api_key:
        return {"ok": False, "model": None, "error": "No API key configured"}
    now = time.time()
    if _CONNECTION_CACHE.get("key") == api_key:
        ttl = 300 if _CONNECTION_CACHE["result"]["ok"] else 15
        if now - _CONNECTION_CACHE["at"] < ttl:
            return _CONNECTION_CACHE["result"]
    last_err = "Unknown error"
    try:
        client = _get_genai_client(api_key)
        for model in [_PREFERRED_MODEL] + [m for m in _MODEL_CANDIDATES if m != _PREFERRED_MODEL]:
            try:
                info = client.models.get(model=model)
                if info and getattr(info, "name", None):
                    _PREFERRED_MODEL = model
                    res = {"ok": True, "model": model, "error": None}
                    _CONNECTION_CACHE = {"key": api_key, "result": res, "at": now}
                    return res
            except Exception as e:
                last_err = f"{type(e).__name__}: {e}"
                print(f"[llm.py] Connection check failed for {model}: {last_err[:200]}")
    except Exception as e:
        last_err = f"{type(e).__name__}: {e}"
        print(f"[llm.py] Connection check setup failed: {last_err[:200]}")
    res = {"ok": False, "model": None, "error": last_err}
    _CONNECTION_CACHE = {"key": api_key, "result": res, "at": now}
    return res


def _extract_partial_reply(raw_so_far: str) -> str:
    """Extract partial customer reply text from streaming JSON as it arrives."""
    m = re.search(r'"reply"\s*:\s*"((?:[^"\\]|\\.)*)', raw_so_far)
    if m:
        val = m.group(1)
        if val.endswith('\\'):
            val = val[:-1]
        try:
            return json.loads('"' + val + '"')
        except Exception:
            return val.replace('\\n', '\n').replace('\\"', '"').replace('\\t', '\t')
    return ""


def chat_with_agent(user_message: str, history: list,
                    company_name: str, faq_text: str,
                    customer_profile: dict = None,
                    available_tools: list = None,
                    is_after_hours: bool = False,
                    on_text_chunk = None,
                    selected_language: str = "auto",
                    on_status = None) -> dict:
    """Send a message to the AI agent and return the structured response.

    Supports live streaming via on_text_chunk callback and latency status via on_status.
    Measures TTFT (time to first text) and total response time.
    In demo mode, returns customer-scoped smart replies.
    """
    start = time.perf_counter()

    # Check if user explicitly selected a language chip, otherwise detect from message script
    t_detect_start = time.perf_counter()
    chosen_lang = (selected_language or "auto").strip().lower()
    forced_lang = chosen_lang if (chosen_lang and chosen_lang != "auto" and chosen_lang in LANGUAGE_SPECS) else None
    detected_lang = forced_lang or detect_language_from_script(user_message)
    t_after_lang = time.perf_counter()

    # Check 24-hour response cache for identical preset or FAQ queries (Part B6)
    cust_id = (customer_profile or {}).get("id", "CUST001").strip().upper()
    cache_key = get_query_cache_key(company_name, cust_id, forced_lang or detected_lang, user_message)
    cached_res = get_cached_response(cache_key)
    if cached_res:
        cached_res = dict(cached_res)
        elapsed = int((time.perf_counter() - start) * 1000)
        cached_res["ttft_ms"] = elapsed
        cached_res["response_ms"] = elapsed
        cached_res["cached"] = True
        log_performance(
            input_type="typed",
            language=cached_res.get("language", detected_lang),
            recording_length_s=0.0,
            upload_time_s=0.0,
            transcription_time_s=0.0,
            ttft_s=elapsed / 1000.0,
            total_response_s=elapsed / 1000.0,
            model_name="cache",
            num_ai_calls=0,
            prompt_size=len(user_message),
            error="",
        )
        return cached_res

    active_key = get_gemini_api_key()

    # --- Demo mode (active when no API key is configured) ---
    if not active_key:
        result = get_demo_response(
            user_message,
            available_tools,
            company_name,
            history,
            is_after_hours=is_after_hours,
            selected_language=forced_lang,
            customer_profile=customer_profile,
        )
        if forced_lang:
            result["language"] = forced_lang
        elif detected_lang != "en":
            result["language"] = detected_lang
        result["ttft_ms"] = "demo"
        result["response_ms"] = "demo"
        if not result.get("tool_used"):
            result["tool_used"] = None
        result["demo_mode"] = True
        result["data_source"] = "sample_sqlite"

        tool_det = result.get("tool_used") or "None"
        tool_tm = "24ms" if result.get("tool_used") else "—"
        result["step_timings"] = [
            {"step": "Language detected", "detail": result.get("language", "en").upper(), "time": "12ms"},
            {"step": "Intent understood", "detail": result.get("intent", "other").replace("_", " ").title(), "time": "18ms"},
            {"step": "Tool called", "detail": tool_det, "time": tool_tm},
            {"step": "Reply written", "detail": f"{len(result.get('reply', '').split())} words", "time": "35ms"},
        ]
        return result

    # --- Real Gemini call using google-genai streaming SDK ---
    global _PREFERRED_MODEL

    try:
        # pyrefly: ignore[missing-import]
        from google.genai import types

        client = _get_genai_client(active_key)
        cust_id = (customer_profile or {}).get("id", "CUST001").strip().upper()

        live_db_context = _build_live_db_context(
            customer_profile=customer_profile,
            user_message=user_message,
            history=history,
            available_tools=available_tools,
        )
        system_prompt = get_system_prompt(
            company_name=company_name,
            faq_text=faq_text,
            customer_profile=customer_profile,
            available_tools=available_tools,
            live_db_context=live_db_context,
            selected_language=forced_lang,
        )

        if forced_lang:
            lang_spec = LANGUAGE_SPECS[forced_lang]
            lang_hint = (
                f"\n[System instruction: The customer has selected '{forced_lang}' ({lang_spec}) on the language bar. "
                f"You MUST write your 'reply' in {lang_spec} and set 'language' to '{forced_lang}', "
                f"even if the message above is in another language. Hinglish means Hindi written in English letters.]"
            )
        else:
            lang_hint = f"\n[System hint: the customer's message appears to be in {detected_lang}. Reply in that language and script.]"

        messages = []
        for msg in (history or [])[-MAX_HISTORY:]:
            role = "user" if msg.get("role") == "customer" else "model"
            messages.append({"role": role, "parts": [{"text": msg.get("content", "")}]})
        messages.append({"role": "user", "parts": [{"text": user_message + lang_hint}]})

        def _make_config(model_name: str):
            kwargs = {
                "max_output_tokens": MAX_OUTPUT_TOKENS,
                "temperature": 0.2,
                "system_instruction": system_prompt,
            }
            # Fast response: disable internal thinking budget so Gemini outputs useful response tokens immediately
            if any(k in model_name for k in ("3.5-flash", "3.6-flash", "3.7-flash", "3.8-flash", "3.1", "3-flash")):
                try:
                    kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
                except Exception:
                    pass
            return types.GenerateContentConfig(**kwargs)

        candidates = _ordered_candidates()
        t_gemini_start = time.perf_counter()
        full_raw, _active_model, t_first_text = _hedged_stream(
            client, candidates, messages, _make_config,
            on_partial=on_text_chunk, on_status=on_status,
        )
        _PREFERRED_MODEL = _active_model
        t_gemini_end = time.perf_counter()

        if not full_raw:
            raise RuntimeError("All model candidates unavailable")

        ai_json = _parse_ai_json(full_raw)
        if not ai_json:
            print(f"[llm.py] Could not parse AI JSON. Raw: {full_raw[:300]}")
            result = _default_response(full_raw[:500])
        else:
            result = ai_json

        # --- Tool execution & deterministic cancellation/ownership enforcement ---
        tool_used = None
        t_tool_duration = 0
        followup_calls = 0
        mentioned_oids = [m.upper() for m in re.findall(r"\bORD\d+\b", user_message, re.IGNORECASE)]
        is_cancel_turn = (
            result.get("intent") == "cancel_order"
            or any(k in user_message.lower() for k in _INTENT_KEYWORDS["cancel_order"])
        )

        # If this is a cancellation turn with an order ID, ensure cancel_order tool is always invoked
        if is_cancel_turn and mentioned_oids and not result.get("tool_call"):
            result["tool_call"] = {"name": "cancel_order", "args": {"order_id": mentioned_oids[-1]}}

        if result.get("tool_call"):
            tool_info = result["tool_call"]
            tool_name = tool_info.get("name", "")
            tool_args = tool_info.get("args", {}) or {}

            t_tool_start = time.perf_counter()
            tool_result = execute_tool(tool_name, tool_args, customer_id=cust_id)
            t_after_tool = time.perf_counter()
            t_tool_duration = max(int((t_after_tool - t_tool_start) * 1000), 1)
            tool_used = tool_name

            # Enforce truthful cancellation outcome if cancel_order was called
            if tool_name == "cancel_order":
                target_oid = (tool_args.get("order_id") or (mentioned_oids[-1] if mentioned_oids else "")).strip().upper()
                active_lang = forced_lang or result.get("language", detected_lang)
                if not target_oid:
                    cust_orders_res = get_customer_orders(cust_id)
                    cust_orders = cust_orders_res if isinstance(cust_orders_res, list) else cust_orders_res.get("orders", [])
                    result["reply"] = _format_which_order_prompt(active_lang, cust_orders, "cancel_order")
                elif tool_result.get("error") == "not_found_for_customer":
                    nf_map = DEMO_REPLIES["order_not_found"]
                    result["reply"] = nf_map.get(active_lang, nf_map["en"]).format(order_id=target_oid)
                elif not tool_result.get("success"):
                    ord_info = execute_tool("get_order_status", {"order_id": target_oid}, customer_id=cust_id)
                    if ord_info.get("success"):
                        result["reply"] = _format_cancel_order_reply(active_lang, ord_info, tool_result)

            # Only make a 2nd follow-up LLM call if the 1st reply was a placeholder
            needs_followup = _is_placeholder_reply(result.get("reply", ""))
            if needs_followup:
                followup_prompt = get_tool_result_prompt(
                    tool_name=tool_name,
                    tool_result=tool_result,
                    original_query=user_message,
                    language=forced_lang or result.get("language", detected_lang),
                )
                messages.append({"role": "model", "parts": [{"text": json.dumps(result)}]})
                messages.append({"role": "user", "parts": [{"text": followup_prompt}]})

                followup_candidates = [_active_model] + [m for m in _ordered_candidates() if m != _active_model]
                followup_raw, _active_model, _f_first = _hedged_stream(
                    client, followup_candidates, messages, _make_config,
                    on_partial=on_text_chunk, on_status=on_status,
                )
                if t_first_text is None:
                    t_first_text = _f_first
                followup_calls = 1

                followup_json = _parse_ai_json(followup_raw)
                if followup_json:
                    result = followup_json

        if forced_lang:
            result["language"] = forced_lang

        t_finish = time.perf_counter()
        elapsed = int((t_finish - start) * 1000)
        ttft_ms = int((t_first_text - start) * 1000) if t_first_text else elapsed
        result["ttft_ms"] = ttft_ms
        result["response_ms"] = elapsed
        result["tool_used"] = tool_used
        result["demo_mode"] = False
        result["data_source"] = "live_business_api" if LIVE_BUSINESS_DATA_CONNECTED else "sample_sqlite"
        result["model"] = _active_model

        t_lang_ms = max(int((t_after_lang - t_detect_start) * 1000), 1)
        t_prep_ms = max(int((t_gemini_start - t_after_lang) * 1000), 0)
        t_gemini_ms = int((t_gemini_end - t_gemini_start) * 1000)
        tool_det = tool_used or "None"
        tool_tm = f"{t_tool_duration}ms" if tool_used else "—"
        result["timing_breakdown"] = {
            "language_detection_ms": t_lang_ms,
            "context_build_ms": t_prep_ms,
            "gemini_request_ms": t_gemini_ms,
            "tool_ms": t_tool_duration if tool_used else 0,
            "followup_calls": followup_calls,
            "ttft_ms": ttft_ms,
            "total_ms": elapsed,
        }
        result["step_timings"] = [
            {"step": "Language detected", "detail": result.get("language", detected_lang).upper(), "time": f"{t_lang_ms}ms"},
            {"step": "Context prepared", "detail": "customer records + prompt", "time": f"{t_prep_ms}ms"},
            {"step": "First text arrived (TTFT)", "detail": _active_model, "time": f"{ttft_ms}ms"},
            {"step": "Tool called", "detail": tool_det, "time": tool_tm},
            {"step": "Full reply finished", "detail": f"{len(result.get('reply', '').split())} words" + (" · 1 follow-up" if followup_calls else ""), "time": f"{elapsed}ms"},
        ]

        result.setdefault("language", detected_lang)
        result.setdefault("sentiment", "neutral")
        result.setdefault("intent", "other")
        result.setdefault("confidence", 0.5)
        result.setdefault("reply", "I'm here to help!")
        result.setdefault("escalate", False)
        result.setdefault("escalation_reason", "")
        result.setdefault("escalation_triggers", [])

        # Cache response for 24 hours (Part B6)
        set_cached_response(cache_key, result)

        # Log performance metrics (Part A)
        prompt_size = sum(len(m.get("parts", [{}])[0].get("text", "")) for m in messages)
        log_performance(
            input_type="typed",
            language=result.get("language", detected_lang),
            recording_length_s=0.0,
            upload_time_s=0.0,
            transcription_time_s=0.0,
            ttft_s=ttft_ms / 1000.0 if isinstance(ttft_ms, (int, float)) else 0.0,
            total_response_s=elapsed / 1000.0 if isinstance(elapsed, (int, float)) else 0.0,
            model_name=_active_model,
            num_ai_calls=1 + followup_calls,
            prompt_size=prompt_size,
            error="",
        )

        return result

    except Exception as e:
        err_str = str(e)
        print(f"[llm.py] Gemini API error: {type(e).__name__}: {err_str[:200]}")

        # Classify error for performance log (Part A & B5)
        is_429 = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str
        is_503 = "503" in err_str or "UNAVAILABLE" in err_str
        is_timeout = "timeout" in err_str.lower() or "did not respond within" in err_str
        err_code = "429" if is_429 else ("503" if is_503 else ("timeout" if is_timeout else type(e).__name__))

        log_performance(
            input_type="typed",
            language=detected_lang,
            recording_length_s=0.0,
            upload_time_s=0.0,
            transcription_time_s=0.0,
            ttft_s=0.0,
            total_response_s=round(time.perf_counter() - start, 2),
            model_name="fallback_demo",
            num_ai_calls=1,
            prompt_size=len(user_message),
            error=err_code,
        )

        result = get_demo_response(
            user_message,
            available_tools,
            company_name,
            history,
            is_after_hours=is_after_hours,
            selected_language=forced_lang,
            customer_profile=customer_profile,
        )
        if forced_lang:
            result["language"] = forced_lang
        elif detected_lang != "en":
            result["language"] = detected_lang
        result["ttft_ms"] = "demo"
        result["response_ms"] = "demo"
        if not result.get("tool_used"):
            result["tool_used"] = None
        result["demo_mode"] = True
        result["data_source"] = "sample_sqlite"
        if is_429:
            result["api_error"] = "Free AI quota limit reached for this minute. Using offline assistant."
        elif is_timeout:
            result["api_error"] = "Gemini service is responding too slowly — showing a safe demo reply for this message"
        else:
            result["api_error"] = "Live AI temporarily unavailable"

        tool_det = result.get("tool_used") or "None"
        tool_tm = "24ms" if result.get("tool_used") else "—"
        result["step_timings"] = [
            {"step": "Language detected", "detail": result.get("language", "en").upper(), "time": "12ms"},
            {"step": "Intent understood", "detail": result.get("intent", "other").replace("_", " ").title(), "time": "18ms"},
            {"step": "Tool called", "detail": tool_det, "time": tool_tm},
            {"step": "Reply written", "detail": f"{len(result.get('reply', '').split())} words", "time": "35ms"},
        ]
        return result

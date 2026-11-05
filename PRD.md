# PRD: Sahayak AI — Multilingual Customer Support Agent

Owner: Ameya (25BTRAO003)
Deadline: 6 November 2026, 11:59 PM
Build tool: Google Antigravity (AI-assisted coding)
Language: Python only (no JavaScript files, no Node, no separate frontend project)

---

## 1. Instructions for the Antigravity agent (read first)

1. Build exactly what this document describes, in the phase order given in Section 13.
2. Use Python only. Custom styling is done with CSS strings injected through Python (allowed). No `.js`, `.ts`, or `.jsx` files.
3. Keep the code simple and readable. Every file starts with a short comment explaining what it does. Every function has a one-line docstring. The student must be able to explain every part in a viewing/demo.
4. After each phase, run the app, fix errors, and confirm the phase's acceptance checks pass before moving on.
5. Never hardcode API keys. Read them from a `.env` file. Provide `.env.example`.
6. The app must run in "Demo Mode" (pre-written smart replies, no API key needed) if the API key is missing or the network fails. The demo must never crash on camera.
7. Produce a `README.md` with setup steps, screenshots placeholder, features, and architecture explanation in plain simple English.

---

## 2. Problem statement

Businesses serving customers in English, Hindi, and regional languages cannot offer consistent support outside working hours. Human agents are expensive to scale. Basic chatbots fail on local expressions, mixed-language sentences (like "mera order kab aayega please check karo"), interruptions, and complex questions. Bad escalation to a human damages trust.

Customers: people needing support, call-centre agents, customer-service managers.
Target businesses: e-commerce, banks, telecom, travel, utilities.
Buyers care about: lower cost per resolved query, fewer missed calls, shorter waits, reliable language quality, low delay, and connection to customer systems.
Revenue model: usage-based voice/chat pricing, monthly contracts, API fees.

## 3. Product vision

Sahayak ("helper" in Hindi) is a support agent that talks to customers in their own language, solves the common problems by itself using the company's data, and hands over to a human agent smoothly, with a ready summary, when it should not continue alone.

Unique points that set this project apart:
1. **Mixed-language understanding**: handles Hinglish and Kanglish (Kannada + English) naturally.
2. **Live Agent Console**: a second panel beside the chat shows the AI's "thinking" in real time (detected language, mood, intent, confidence, escalation risk).
3. **Warm handoff**: when escalating, the human agent receives an auto-written summary so the customer never repeats themselves.
4. **Business dashboard**: shows cost per resolved query, resolution rate, wait time, and language split, which is exactly what the buyer pays for.
5. **Industry packs**: one switch changes the company between E-commerce, Bank, and Telecom.

## 4. Goals and non-goals

Goals
- Working chat and voice support in English, Hindi, Kannada (P0), Tamil and Telugu (P1).
- Real actions against a mock database (order status, cancel, refund, balance, plan details).
- Smart escalation with summary.
- Analytics dashboard.
- Beautiful, distinctive interface.

Non-goals
- Real phone calls or telephony integration (explain as future work).
- Real payments or real customer data.
- User login system.

## 5. Users and key scenarios

| User | Need | Example |
|---|---|---|
| Customer | Quick answer in own language, any hour | "Mera refund abhi tak nahi aaya" |
| Human agent | Take over with full context | Opens handoff card with summary |
| Support manager | See cost, speed, quality | Opens dashboard |

## 6. Features

### P0 (must have, demo depends on these)
- F1 Chat interface with message history, typing indicator, quick-reply chips.
- F2 Language auto-detection (English, Hindi, Kannada, Hinglish) and reply in the same language and script the customer used.
- F3 Voice input: customer records a message; it is converted to text. Use Gemini multimodal API to transcribe audio directly (no local C-library dependencies like portaudio/ffmpeg). Fallback: `SpeechRecognition`.
- F4 Voice output: the agent's reply can be played as audio in the customer's language.
- F5 Tools on mock database: order status, cancel order, refund status, account/plan info.
- F6 Knowledge answers from a small FAQ file (returns policy, delivery time, working hours, etc.).
- F7 Live Agent Console panel: language, sentiment, intent, confidence, escalation risk meter with **explainable trigger badges** (e.g. `[Angry Tone]` + `[High Value]` + `[Keyword: manager]`), tool used, response time.
- F8 Escalation with auto-generated handoff summary card **plus Agent Takeover simulator** ("Accept Handoff as Agent Rahul" button and canned response input so the demo shows end-to-end operational continuity).
- F9 Demo Mode fallback (no API needed).
- F10 **Quick Demo Presets** in the sidebar (e.g. "Hinglish Refund Check", "Kannada Order Cancel", "Angry Escalation", "Telecom Pack Switch") — clicking one auto-injects the message and runs the scenario. Essential for a smooth 5-minute live demo.
- F11 **Domain guardrails**: off-topic or harmful queries are politely declined in the customer's language and redirected back to support scope.

### P1 (should have)
- F12 Analytics dashboard: total chats, AI-resolved %, escalated %, average response time, estimated cost per resolved query vs a human baseline, language pie chart, sentiment trend, **plus an Interactive ROI / Cost Savings slider** (set monthly query volume → see estimated human cost vs Sahayak AI cost → net monthly savings).
- F13 Industry pack switcher (E-commerce, Bank, Telecom) that changes company name, brand colour, FAQ, and tools.
- F14 Tamil and Telugu support.
- F15 Customer picker (choose a demo customer profile so data looks real).
- F16 Download chat transcript as a `.txt` file.

### P2 (nice to have, only if time remains)
- F17 Simulated "after-hours" banner showing the agent is covering the night shift.
- F18 Customer satisfaction thumbs up/down after resolution feeding the dashboard.
- F19 Interruption handling: if the user sends a new message while the agent is "speaking", the audio stops and the new message takes priority.

### Language support design

Scope decision: the app does NOT need all 22 Indian languages. Quality in a few languages matters more than the number of languages.
- Must work well: English, Hindi, Kannada, plus Hinglish (Hindi and English mixed).
- Optional if time remains: Tamil, Telugu.
- Everything else is future work, and the code must make it easy to add.

How to keep it easy to add a language:
- Keep one `LANGUAGES` list in `config.py`. Each entry has: language code, name, native name (for the chip label), Google Font name for the script, and gTTS voice code. Example: `{"code": "kn", "name": "Kannada", "native": "ಕನ್ನಡ", "font": "Noto Sans Kannada", "tts": "kn"}`.
- The language chips in the UI, the fonts in the CSS, the AI prompt's allowed language values, and the voice output must all be generated from this single list. Adding a language means adding one entry, with no other code changes.
- Each language that is shown in the demo must be tested with at least 3 real sentences before recording.

## 7. Technology (all Python, all free-tier friendly)

| Purpose | Choice |
|---|---|
| App framework and UI | Streamlit with custom CSS injected via `st.markdown(unsafe_allow_html=True)` |
| AI brain | Google Gemini API through `google-genai` (free tier). Wrap in a `llm.py` so the provider can be swapped to Claude later |
| Speech to text | Send the recorded WAV bytes from `st.audio_input` directly to Gemini multimodal API (`google-genai`) for transcription — handles Indian accents and code-mixed speech natively with zero local C-library installs. Fallback: `SpeechRecognition` |
| Text to speech | `gTTS` (supports en, hi, kn, ta, te) |
| Database | SQLite via built-in `sqlite3`, seeded by a script |
| Charts | Plotly (`plotly.express`) |
| Data handling | `pandas` |
| Config | `python-dotenv` |

`requirements.txt`: streamlit, google-genai, gTTS, plotly, pandas, python-dotenv

## 8. How the agent works (simple explanation)

For every customer message:

1. **Input**: text, or voice converted to text.
2. **One AI call** with the company FAQ, the customer's profile, and the last few messages. The AI must answer in strict JSON:
   ```json
   {
     "language": "hi | en | kn | ta | te | hinglish",
     "sentiment": "happy | neutral | frustrated | angry",
     "intent": "order_status | cancel_order | refund_status | account_info | faq | complaint | human_request | other",
     "confidence": 0.0,
     "tool_call": {"name": "get_order_status", "args": {"order_id": "ORD1002"}} ,
     "reply": "text in customer's language",
     "escalate": false,
     "escalation_reason": ""
   }
   ```
3. **Tool step**: if `tool_call` is present, Python runs the matching function on SQLite, then a second AI call writes the final reply using the real result.
4. **Escalation check** (rules in Section 9).
5. **Output**: show reply, update the Agent Console, optionally play audio, log the interaction to the database for the dashboard.

Rules for the AI prompt (put in `prompts.py`):
- Reply in the same language and script as the customer.
- Never invent order or account data. Use only tool results.
- Keep replies short, polite, and warm (2 to 4 sentences).
- If unsure, ask one clarifying question instead of guessing.
- Return only valid JSON.
- **Domain guardrail**: if the query is off-topic (e.g. "write a poem", "who is the PM"), politely decline in the customer's language and redirect to support scope. Do not answer general knowledge or creative requests.

## 9. Escalation rules (clear and testable)

Escalate to a human when ANY of these is true:
- Customer asks for a human or manager.
- Sentiment is `angry`, or `frustrated` for 2 messages in a row.
- Confidence is below 0.55.
- The same problem is not solved after 3 attempts.
- Topic is sensitive: fraud, legal complaint, large refund above a set limit, account hacked.

On escalation:
1. Agent tells the customer calmly, in their language, that a specialist is taking over.
2. A **Handoff Card** appears with: customer name, language, issue summary (3 lines), what the AI already tried, sentiment, and suggested next step.

## 10. Data (mock, seeded automatically)

Tables
- `customers(id, name, phone, preferred_language, tier)`
- `orders(order_id, customer_id, item, amount, status, expected_date)`
- `refunds(refund_id, order_id, amount, status, initiated_on)`
- `accounts(customer_id, plan_name, balance, due_date)` (used for bank/telecom packs)
- `tickets(ticket_id, customer_id, summary, status, created_at)` (stores escalated handoffs: status is `open`, `assigned`, or `resolved`)
- `interactions(id, timestamp, customer_id, language, intent, sentiment, resolved_by_ai, escalated, response_ms, est_cost)`

Seed at least 8 customers with Indian names, mixed languages, 15+ orders in different states (placed, shipped, out for delivery, delivered, cancelled), and 4 refunds in different states.

Tools (all in `tools.py`)
- `get_order_status(order_id)`
- `cancel_order(order_id)` (only if not shipped)
- `get_refund_status(order_id)`
- `get_account_info(customer_id)`
- `create_ticket(summary)` (used on escalation)

## 11. Interface design (this is where the project must look special)

Overall feel: modern, calm, premium, India-inspired but not clichéd.

Theme
- Dark base: deep ink `#0B0F1A`, panels `#121829`, soft borders `#1F2A44`.
- Accent gradient: saffron `#FF9933` to teal `#14B8A6` (used for buttons, active chips, glow).
- Success `#22C55E`, warning `#F59E0B`, danger `#EF4444`.
- Fonts via Google Fonts CSS import: Inter for English, Noto Sans Devanagari for Hindi, Noto Sans Kannada for Kannada. The reply must render correctly in each script.
- Rounded corners (16px), soft shadows, subtle glow, smooth hover transitions, no default Streamlit look (hide the default header, footer, and menu).

Layout (wide mode, two columns, roughly 60/40)
- **Left: Customer Chat**
  - Top bar: company logo and name (changes per industry pack), a "Live" pulse dot, language chips (EN, हिं, ಕನ್ನಡ, தமிழ், తెలుగు) showing detected language.
  - Chat bubbles: customer on right (gradient), agent on left (dark glass card), small timestamp, small language tag on each bubble.
  - Quick-reply chips under the last message.
  - Input row: text box, mic button (glowing animated orb while recording), send button.
  - "Play reply" speaker icon on each agent bubble.
- **Right: Live Agent Console** (the unique panel)
  - Header: "Agent Brain, live".
  - Cards that update after every message: Detected Language, Mood (emoji plus label), Intent, Confidence (progress bar), Tool Used, Response Time (ms), Escalation Risk (colour-changing meter green, amber, red) **with explainable trigger badges** showing which rules fired (e.g. `[Angry Tone]`, `[High-Value Refund]`, `[Keyword: manager]`).
  - When escalated: the panel turns into the Handoff Card with the summary, a "Human agent joined" status, **an "Accept Handoff as Agent Rahul" button, and a canned-response input** so the demo shows the full AI → Human → Resolution loop.
- **Sidebar**: industry pack selector, demo customer picker, Demo Mode toggle, **Quick Demo Presets**, "New chat" button, download transcript.

Pages (use Streamlit tabs at the top, styled as a pill navigation)
1. Customer Support (chat plus console)
2. Business Dashboard (KPI cards, charts)
3. How It Works (simple architecture picture and the escalation rules, useful for the demo video)

Dashboard visuals (Plotly, dark theme, same colours)
- KPI cards: Total Chats, AI Resolved %, Escalated %, Avg Response Time, Cost per Resolved Query (AI vs human baseline of 80 rupees, clearly labelled as an estimate).
- **Interactive ROI / Cost Savings slider**: user sets monthly query volume (5,000 to 50,000) → automatically calculates estimated human cost (`Volume × ₹80`), estimated Sahayak AI cost (`Volume × ₹4`), net monthly savings, and after-hours coverage percentage.
- Donut: language split. Bar: intents. Line: sentiment over time. Gauge: AI resolution rate.
- Include a "Load sample data" button so the dashboard looks full for the demo.

Small details that make it feel polished
- Animated "typing" dots while waiting.
- Fade-in for new messages.
- Empty state with a friendly greeting in the 3 main languages.
- Friendly error messages, never raw tracebacks.

## 12. Non-functional requirements

- Reply appears within 4 seconds for text in normal conditions; show response time honestly.
- Works on a normal laptop with Python 3.10+.
- No secrets in the GitHub repo (`.env` in `.gitignore`).
- Graceful fallback to Demo Mode on API errors.
- Code is understandable: small files, clear names, comments.

## 13. Build plan for Antigravity (phased)

Folder structure
```
sahayak-ai/
├── app.py                 # entry point, page layout, tabs
├── config.py              # industry packs, LANGUAGES list, settings
├── llm.py                 # Gemini calls, JSON parsing, demo-mode fallback
├── prompts.py             # system prompt and rules
├── tools.py               # database actions the agent can call
├── escalation.py          # escalation rules and handoff summary
├── speech.py              # speech to text and text to speech
├── database.py            # SQLite setup, seeding, logging
├── analytics.py           # dashboard numbers and charts
├── ui.py                  # CSS and reusable HTML components
├── data/
│   ├── faq_ecommerce.md
│   ├── faq_bank.md
│   └── faq_telecom.md
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

Phase 1 (Day 1): Foundation
- Project setup, database seeding, tools, and a working text chat with the AI returning JSON.
- Check: typing "Where is my order ORD1002?" returns real data from the database.

Phase 2 (Day 2): Intelligence
- Language detection and same-language replies, FAQ answers, escalation rules, handoff card, Demo Mode.
- Check: Hindi, Kannada, English, and Hinglish messages each get correct-language replies; angry message triggers escalation.

Phase 3 (Day 3): Voice and design
- Mic input, audio replies, full custom CSS theme, Live Agent Console panel.
- Check: speak in Hindi, see transcript, reply, and audio; UI matches Section 11.

Phase 4 (Day 3 to 4): Dashboard and polish
- Analytics tab, sample data loader, industry packs, transcript download, How It Works tab.
- Check: dashboard KPIs match logged interactions; switching packs changes brand and FAQ.

Phase 5 (Day 4, before 5 Nov night): Ship
- README, final bug fixes, push to GitHub, record demo, upload to YouTube, submit.

## 14. Test scenarios (use these as the demo too)

| # | Customer says | Expected |
|---|---|---|
| 1 | "Where is my order ORD1002?" | English reply, real status, no escalation |
| 2 | "Mera refund abhi tak nahi aaya" | Hinglish reply, refund status from DB |
| 3 | "ನನ್ನ ಆರ್ಡರ್ ರದ್ದು ಮಾಡಿ" (cancel my order, Kannada) | Kannada reply, cancel if allowed, else explains why |
| 4 | "Return policy kya hai?" | FAQ answer in Hindi/Hinglish |
| 5 | Voice message in Hindi | Transcript, reply text, reply audio |
| 6 | "This is useless, I want a manager NOW" | Escalation, handoff card, mood angry |
| 7 | Unclear message "help" | One clarifying question, no guessing |
| 8 | API key removed | Demo Mode works, no crash |

## 15. Demo video script (max 5 minutes)

1. 0:00 to 0:30: Introduce yourself, the problem, and the solution name.
2. 0:30 to 1:15: Show the UI and explain the two panels.
3. 1:15 to 2:30: Run scenarios 1, 2, 3 (English, Hinglish, Kannada) with the Agent Console visible.
4. 2:30 to 3:15: Voice demo (scenario 5).
5. 3:15 to 4:00: Escalation demo (scenario 6) and the handoff card.
6. 4:00 to 4:40: Dashboard tab, explain cost per resolved query and why a business would pay for it.
7. 4:40 to 5:00: Quick explanation of the code structure and how AI tools helped build it. Say: "The app supports English, Hindi and Kannada today. Adding another Indian language only needs a small settings change, so it can grow to more regional languages." Mention other future work: real telephony, CRM integration.

## 16. Business angle (one slide or spoken in the demo)

- Pricing: per resolved conversation (usage-based), per voice minute, plus a monthly platform fee for dashboards.
- Value: lower cost per resolved query, no missed calls at night, shorter waits, consistent quality in every language.
- Integration: the `tools.py` layer is where a company's real order, billing, or CRM systems would plug in.

## 17. Submission checklist

- [ ] App runs from a fresh clone with the README steps
- [ ] `.env` is NOT in GitHub; `.env.example` is
- [ ] GitHub repository is public with all code
- [ ] Demo video (max 5 min) uploaded to YouTube (Unlisted or Public)
- [ ] Submission document has: Name (Ameya), Roll Number/USN (25BTRAO003), GitHub link, YouTube link
- [ ] Submitted before 6 November 2026, 11:59 PM
- [ ] I can explain each major file in my own words

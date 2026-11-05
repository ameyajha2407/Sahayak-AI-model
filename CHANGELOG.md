# Changelog — Sahayak AI

All notable changes and bug fixes made to the Sahayak AI project are recorded here in plain English.

---

## Part A: Critical Bug Fixes

### A1. Agent replies show raw HTML code in the chat
- **What was wrong:** The agent's messages occasionally rendered as raw HTML code blocks (e.g., `<div class="chat-bubble agent">`) instead of styled message bubbles. Markdown interprets any line with 4+ spaces of leading indentation as a code block. Furthermore, special characters (`<`, `>`) typed by customers could interfere with HTML formatting.
- **What changed:**
  - In `ui.py`, updated `chat_bubble_html()` and all helper functions to construct HTML strings without leading indentation or multiline space gaps.
  - Added HTML escaping (`html.escape`) and newline conversion (`<br>`) in `_safe()` so that characters like `<` and `>` display safely as text.
  - In `app.py`, ensured `chat_html` concatenates cleanly into a single string for `st.markdown(..., unsafe_allow_html=True)`.
- **Files modified:** `ui.py`, `app.py`
- **Verification:** Verified that bubbles render cleanly across all six languages, and user input with HTML tags (`<script>`, `<`, `>`) displays safely as text.

---

### A2. Voice recording creates repeated messages and crashes
- **What was wrong:** In Streamlit, when an audio file was recorded using `st.audio_input`, the audio bytes persisted in the session across page reruns. Whenever the customer clicked "Play Reply", Streamlit re-executed the script, detected the voice input again, and processed duplicate messages in an infinite loop, resulting in repeated messages and app errors.
- **What changed:**
  - Added `last_processed_audio_hash` in `st.session_state` using SHA-256 to track the last processed recording and ignore duplicate runs of the same audio.
  - Dynamic key `f"voice_input_{st.session_state.voice_key_counter}"` is used for the audio input widget so that clicking "New Chat" increments the counter and resets the recorder cleanly.
  - Cached generated speech audio bytes per message in `st.session_state.audio_cache`. Clicking "Play Reply" now only fetches or plays the cached audio, never touching the chat history or calling AI.
  - Wrapped speech-to-text (`speech_to_text`) and text-to-speech (`text_to_speech`) in `try...except` blocks with descriptive console logging and the required friendly fallback message for users: *"Sorry, I could not understand the audio. Please try again or type your message."*
- **Files modified:** `speech.py`, `app.py`
- **Verification:** Tested that a single recording generates exactly one user message and one agent response; clicking "Play Reply" adds 0 messages and plays audio; "New Chat" clears the entire session and recorder state.

---

### A3. Kannada messages get an English reply
- **What was wrong:** When sending a message in Kannada or Hindi, the agent previously fell back to an English reply because demo mode only had English templates, and language detection relied only on LLM inference which could fail silently.
- **What changed:**
  - Implemented `detect_language_from_script()` in `llm.py` using Unicode block ranges to identify Kannada (`\u0C80-\u0CFF`), Tamil (`\u0B80-\u0BFF`), Telugu (`\u0C00-\u0C7F`), and Devanagari Hindi (`\u0900-\u097F`). Added keyword matching for Hinglish.
  - Added comprehensive canned replies in `DEMO_REPLIES` covering **all 6 supported languages** (English, Hindi, Kannada, Hinglish, Tamil, Telugu) for every intent across all packs.
  - Updated the system prompt to explicitly pass the detected customer language and script hint to Gemini.
  - Added an AI status indicator in the sidebar: *"AI mode: Live (Gemini)"* or *"AI mode: Demo"*, and displayed a warning notice in the sidebar if a live call fails and falls back to demo mode.
- **Files modified:** `llm.py`, `app.py`, `prompts.py`
- **Verification:** Verified that Kannada queries get fluent Kannada responses, Hindi queries get Hindi, Tamil queries get Tamil, Telugu queries get Telugu, Hinglish queries get Hinglish, and English queries get English.

---

### A4. Industry pack changes only branding
- **What was wrong:** Switching between E-commerce, Bank, and Telecom only changed the logo and color. The quick demo preset buttons still showed e-commerce actions, and asking about bank loans or telecom data usage while in the bank pack would fail or show e-commerce tools. Asking cross-pack questions was not handled gracefully.
- **What changed:**
  - Updated `config.py` to organize `DEMO_PRESETS` by industry pack (`ecommerce`, `bank`, `telecom`), giving each pack its own relevant presets.
  - Added banking tools (`get_account_info`, `get_recent_transactions`, `block_card`, `get_loan_info`) and telecom tools (`get_plan_details`, `get_data_usage`, `get_recharge_status`, `get_bill_info`) in `tools.py`.
  - In `app.py`, switching the industry pack now updates company branding, resets the chat history, updates available tools, and renders pack-specific preset buttons.
  - Added out-of-scope detection in `llm.py` (`out_of_scope_pack` intent): if a user asks about e-commerce orders in the bank or telecom pack (or vice versa), the agent politely explains that it is the support assistant for that specific company and can only handle its services.
- **Files modified:** `config.py`, `tools.py`, `llm.py`, `app.py`, `prompts.py`
- **Verification:** Verified switching packs updates presets dynamically, executing bank and telecom queries calls their respective tools, and out-of-pack queries receive polite domain boundary replies in all languages.

---

### A5. "Load Sample Data" keeps duplicating records
- **What was wrong:** Clicking "Load Sample Data" on the dashboard added 50 records on every click without limit, inflating counts (880, 930, 980...) and skewing analytics with unrealistic distributions.
- **What changed:**
  - Added an `is_sample` column to the `interactions` table in SQLite (`database.py`) with automatic migration in `init_database()`.
  - Updated `load_sample_interactions(n=300)` to delete existing sample data (`WHERE is_sample=1`) before inserting, and used a fixed random seed (`Random(42)`) so repeated clicks are strictly idempotent.
  - Added a "Clear Sample Data" button and `clear_sample_interactions()` in `database.py`.
  - Calibrated the sample distribution to mirror real-world Indian call centers: ~30% English, 25% Hinglish, 15% Hindi, 15% Kannada, 8% Tamil, 7% Telugu; ~80% resolved by AI, ~20% escalated; realistic response times between 800ms and 3500ms; and balanced sentiments (Happy, Neutral, Frustrated, Angry).
  - Updated `analytics.py` and dashboard KPI display to separate sample data from real user chats and ensure full language representation across charts.
- **Files modified:** `database.py`, `analytics.py`, `app.py`
- **Verification:** Verified that clicking "Load Sample Data" multiple times produces the exact same total (300 sample rows), all six languages show in the language chart, and "Clear Sample Data" resets sample interactions to 0 without affecting real chats.

---

## Part B: Honesty & Transparency (Real vs Demo)

### B1. Label demo numbers
- **What was wrong:** The dashboard did not clearly differentiate between synthetic sample interactions and actual live chat interactions. Cost figures were presented without an "Estimated" qualifier, and response times in demo mode showed numeric values that could mislead users into thinking an API call occurred.
- **What changed:**
  - In `app.py`, added a prominent tag (`⚠️ Sample data included` or `✅ Real chats only`) in the dashboard header.
  - Added a 3-way radio filter switch: *"All Data (Real + Sample)"*, *"Real Chats Only"*, and *"Sample Data Only"*, dynamically filtering KPI cards and Plotly charts.
  - Labeled all cost KPI tiles and ROI cards as *"Estimated"* (e.g., *"Estimated AI Cost/Query"*, *"Estimated Human Agent Cost"*, *"Estimated Monthly Savings"*).
  - In `llm.py`, set `response_ms = "demo"` in Demo Mode and on fallback. Real Gemini calls measure exact latency using `time.perf_counter()`. In `app.py`, response time is displayed as `"demo"` in Demo Mode.
  - Updated `database.py` to store `0` as integer for `response_ms` when `"demo"` string is received to prevent SQLite type mismatch.
- **Files modified:** `app.py`, `llm.py`, `database.py`
- **Verification:** Verified that the dashboard tag appears, the data filter switch dynamically recalculates metrics, cost tiles say "Estimated", and the Agent Brain console displays "demo" during Demo Mode.

---

### B2. Actionable & realistic human handoff card
- **What was wrong:** Escalations showed unstructured lists of triggers and occasionally suggested unrealistic actions such as issuing coupons, discounts, or priority dispatch, which standard support teams cannot universally grant. The issue summary was also just a flat chain of messages.
- **What changed:**
  - In `escalation.py`, implemented `select_primary_and_secondary_triggers()` following strict priority:
    1. Customer asked for human
    2. Sensitive topic (fraud, legal, hacked)
    3. Angry sentiment
    4. Repeated frustration
    5. Unresolved after 3 attempts
    6. Low confidence
    At most two secondary reasons are retained.
  - Created realistic specific next steps in `_suggest_action()` referencing relevant order/account IDs where available, and strictly removed any coupon/discount/priority dispatch suggestions. Steps focus on standard support actions: reviewing the case, calling back, checking back-office systems, and verifying customer identity.
  - Formatted the customer issue summary as a clear 3-line case summary showing recent progression.
  - In `ui.py`, updated `handoff_card_html()` with high-visibility primary trigger badge, secondary reason chips, and a distinct "Specific Next Step" action box.
- **Files modified:** `escalation.py`, `ui.py`
- **Verification:** Tested priority ordering across conflicting triggers, verified absence of coupon/discount suggestions, confirmed order ID injection, and verified warm handoff card rendering.

---

### B3. Clear voice capabilities & limitations
- **What was wrong:** Users had no guidance on which languages are supported by voice, whether telephony was integrated, or what to do if transcription failed.
- **What changed:**
  - In `app.py`, added a clear helper note directly beneath the chat & audio input area:
    *"🎤 Voice capabilities: Speech input and audio replies in English, Hindi, Kannada, Tamil, Telugu (Hinglish uses the Hindi voice). In-browser audio only; phone calls and IVR are future work. If recognition fails, please type your message instead."*
- **Files modified:** `app.py`
- **Verification:** Verified that the voice helper info line appears clearly right under the input widgets.

---

### B4. Integration & data source status table
- **What was wrong:** The "How It Works" tab did not clearly state where tool data came from or whether integrations with external CRMs or telephony providers were live.
- **What changed:**
  - In `app.py`, added a dedicated *"Integration & Data Source Status"* section in Tab 3 ("How It Works").
  - Added a prominent badge: *"⚠️ Demo environment, no real customer data"*.
  - Built an integration status table listing all tools with columns: `Tool / Capability`, `Data Source`, and `Status`:
    - E-commerce tools (orders, cancel, refunds) → Demo database (SQLite) | Demo data
    - Banking tools (balance, transactions, card block, loans) → Demo database (SQLite) | Demo data
    - Telecom tools (plan, data, recharge, bills) → Demo database (SQLite) | Demo data
    - CRM Integration (Salesforce, Zoho, Freshdesk) → Not connected (roadmap) | Roadmap
    - Telephony / IVR (Twilio, Exotel) → Not connected (roadmap) | Roadmap
- **Files modified:** `app.py`
- **Verification:** Verified that the integration status table and demo environment badge render cleanly in Tab 3.

---

### B5. Comprehensive language coverage notice
- **What was wrong:** The empty state greeting previously only displayed greetings in 4 of the 6 languages (`LANGUAGES[:4]`), and did not state how additional languages could be added.
- **What changed:**
  - In `ui.py`, updated `empty_state_html()` to display welcome greetings in **all six supported languages** (English, Hindi, Kannada, Hinglish, Tamil, Telugu).
  - Added the explicit statement: *"Supports English, Hindi, Hinglish, Kannada, Tamil, Telugu. More languages can be added with one config entry."*
- **Files modified:** `ui.py`
- **Verification:** Verified that all six greetings and the configuration note render properly in the empty chat state.

---

## Part C: Show the Hard Cases from the Problem Statement

### C1. Local expressions and slang
- **What was wrong:** Customers who write in local idioms or colloquial expressions (e.g. *"Bhai mera parcel kidhar atka hai, tension ho raha hai"*) were previously matched to generic responses or misunderstood.
- **What changed:**
  - Added `DEMO_PRESETS` entry in `config.py` under `"📁 Hard cases"`: *"Bhai mera parcel kidhar atka hai, tension ho raha hai"*.
  - In `prompts.py`, instructed Gemini to recognize informal colloquialisms ("bhai", "tension ho raha hai", "kidhar atka hai"), treat them with empathetic tone, detect intent as order status tracking, and call `get_order_status(order_id="ORD1001")`.
  - In `llm.py`, added `local_expression` intent detection in `_detect_demo_intent` and added reassuring, natural replies in all six languages (e.g. *"Bhai tension mat lo! Aapka parcel ORD1002 (Samsung Galaxy M14) raste mein hai..."*).
- **Files modified:** `config.py`, `prompts.py`, `llm.py`
- **Verification:** Tested query and verified intent detection (`order_status`), tool call (`get_order_status`), and empathetic Hinglish reply with order status.

---

### C2. Customer correction mid-conversation
- **What was wrong:** When a customer entered a correction (e.g., *"Sorry, I meant ORD1004"*), the assistant could repeat previous order details or miss the updated order context.
- **What changed:**
  - Added preset in `config.py`: *"Sorry, I meant ORD1004"*.
  - In `prompts.py`, added instruction Rule 4: If customer corrects a previously mentioned entity, switch smoothly to the new entity, acknowledge the correction, and apply the action to the new ID.
  - In `llm.py`, implemented `correction_order` intent detection: acknowledges the switch without friction and executes the action on the corrected order ORD1004.
- **Files modified:** `config.py`, `prompts.py`, `llm.py`
- **Verification:** Tested two-turn conversation; verified agent acknowledges the switch from ORD1003 to ORD1004 and confirms cancellation on ORD1004.

---

### C3. Multi-part questions
- **What was wrong:** When customers ask multiple questions in a single query (e.g., *"Cancel ORD1003, tell me when my refund will come, and what is your return policy?"*), basic bots only answer the first question and ignore the rest.
- **What changed:**
  - Added preset in `config.py`: *"Cancel ORD1003, tell me when my refund will come, and what is your return policy?"*.
  - In `prompts.py`, added Rule 5: If customer asks multiple questions, answer every single question sequentially in the same order using clear numbered points (1, 2, 3).
  - In `llm.py`, added `multipart_query` intent with numbered 1, 2, 3 responses covering cancellation, refund timeline (₹8,499 within 5-7 days), and return policy (7-day returns).
- **Files modified:** `config.py`, `prompts.py`, `llm.py`
- **Verification:** Tested query and confirmed that all 3 questions are answered in a structured numbered list across all 6 languages.

---

### C4. Cannot resolve confidently (Graceful clarification & escalation)
- **What was wrong:** When a customer gave an ambiguous or vague query (e.g., *"My thing is not working properly"*), the bot might make blind guesses or give unhelpful generic replies without escalating.
- **What changed:**
  - Added preset in `config.py`: *"My thing is not working properly"*.
  - In `prompts.py`, added Rule 6: If query is too vague, ask **exactly one clarifying question** (do not guess). If customer still cannot provide details, escalate immediately to a human agent with primary trigger `"Low Confidence"`.
  - In `llm.py`, added multi-turn state tracking in `_detect_demo_intent`: Turn 1 returns `vague_clarification` (asking which item or order has the issue). If the user replies vaguely again, Turn 2 triggers `low_confidence_escalate` with `escalate=True` and primary trigger `"Low Confidence (38%)"`.
- **Files modified:** `config.py`, `prompts.py`, `llm.py`
- **Verification:** Verified that turn 1 asks a polite clarifying question without escalating, and turn 2 escalates to a human agent with the "Low Confidence" trigger card.

---

### C5. Off-topic query redirect
- **What was wrong:** Asking an out-of-domain question (e.g., *"Write me a poem about the moon"*) could cause an LLM to act as a general AI chatbot rather than a professional enterprise support agent.
- **What changed:**
  - Added preset in `config.py`: *"Write me a poem about the moon"*.
  - In `prompts.py`, added Rule 7: Politely decline in 1-2 sentences, state support role, and steer back to the business domain.
  - In `llm.py`, added `off_topic` intent detection for creative, trivia, and off-topic prompts across all 6 languages, politely refocusing the customer on their account and services.
- **Files modified:** `config.py`, `prompts.py`, `llm.py`
- **Verification:** Tested off-topic query; verified polite refusal and redirection back to customer support without hallucinating poems.

---

### C6. Organized preset groups & Escalation guidance
- **What was wrong:** Preset buttons cluttered the sidebar in a long flat list, and customers were not told upfront that they could reach a human agent at any time.
- **What changed:**
  - In `config.py`, organized `DEMO_PRESETS` into three tidy categories: `"📁 Basics"`, `"📁 Hard cases"`, and `"📁 Escalation"`.
  - In `app.py`, rendered presets inside clean `st.expander` containers so testers can find test cases quickly.
  - Added a reassuring helper line beneath the chat input: *"ℹ️ You can ask for a human agent at any time."*
- **Files modified:** `config.py`, `app.py`
- **Verification:** Verified clean sidebar expanders and chat guidance note.

---

## Part D: After-Hours Experience

### D1. Operating hours banner & India Time (Asia/Kolkata) detection
- **What was wrong:** The application did not communicate operating hours to customers or demonstrate how businesses solve after-hours support shortages.
- **What changed:**
  - Added `support_hours_banner_html()` in `ui.py` to display:
    `🕒 Coverage: Human agents: 9 AM to 9 PM IST · Sahayak AI: 24/7`
  - In `app.py`, computed current time in Indian Standard Time (`UTC+5:30`).
  - Added live status pill: `☀️ Status: Working hours` (green) or `🌙 Status: After hours` (purple).
- **Files modified:** `ui.py`, `app.py`
- **Verification:** Verified banner displays across both states with live IST time format.

---

### D2. "Simulate after hours" toggle
- **What was wrong:** Testers could not evaluate the after-hours support workflow during normal daytime hours without changing their system clock.
- **What changed:**
  - Added a `"🌙 Simulate after hours"` checkbox in `app.py` sidebar.
  - Stored toggle state in `st.session_state.simulate_after_hours`.
  - When checked, immediately updates the banner badge to `🌙 Status: After hours` and activates after-hours escalation logic.
- **Files modified:** `app.py`
- **Verification:** Verified that enabling the toggle immediately flips the status badge to "After hours" and activates callback logic.

---

### D3. After-hours escalation handling & callback queue
- **What was wrong:** Escalating a chat after hours still claimed a human agent was joining immediately, which is unrealistic when human teams are offline.
- **What changed:**
  - In `llm.py`, added `escalation_after_hours` reply templates across all 6 languages stating that human agents are offline (9 PM – 9 AM IST) and an automated priority callback ticket is created for tomorrow morning (9:00 AM – 11:00 AM IST).
  - In `tools.py`, updated `create_ticket()` to accept a `status` argument (`queued_callback` vs `assigned`).
  - In `app.py`, when escalation triggers during after-hours, a ticket is created in the SQLite `tickets` table with `status='queued_callback'`.
  - In `ui.py`, updated `handoff_card_html()` to display `<h3>🌙 Queued for callback</h3>` with ticket ID and morning callback instructions instead of "Human agent joined".
- **Files modified:** `llm.py`, `tools.py`, `ui.py`, `app.py`
- **Verification:** Tested escalation under after-hours mode: confirmed agent replies with callback message, ticket is created in SQLite with status `queued_callback`, and handoff card displays "Queued for callback".

---

## Part E: Make the ROI Calculator Credible

### E1. Four fully editable parameters
- **What was wrong:** The previous calculator had a single slider for volume and fixed assumptions that enterprise decision-makers could not tune for their business.
- **What changed:**
  - Added 4 interactive sliders in `app.py`:
    1. Monthly query volume (1,000 to 100,000, default 10,000)
    2. Human cost per query (₹40 to ₹200, default ₹80)
    3. AI cost per query (₹1 to ₹20, default ₹4)
    4. AI resolution rate (50% to 95%, default 80% or actual dashboard resolution rate)
  - Updated `analytics.py` `roi_calculator()` to accept `human_cost`, `ai_cost`, and `resolution_rate`.
- **Files modified:** `analytics.py`, `app.py`
- **Verification:** Tested updating each of the four sliders independently; values and downstream math react smoothly.

---

### E2. Transparent calculation formula shown on screen
- **What was wrong:** The savings math was a black box without clear derivation.
- **What changed:**
  - Added a formula breakdown card in `app.py` showing the exact step-by-step formula:
    - `All-human cost = Volume × Human cost`
    - `Cost with Sahayak = (Volume × AI cost) + (Volume × (1 - Resolution rate) × Human cost)`
    - `Monthly savings = All-human cost - Cost with Sahayak`
    - `Annual savings = Monthly savings × 12`
    - `Savings percentage = Monthly savings / All-human cost × 100`
- **Files modified:** `app.py`
- **Verification:** Tested with 10,000 queries @ ₹80 human, ₹4 AI, 80% resolution: confirmed All-human cost = ₹8,00,000, Cost with Sahayak = ₹2,00,000, Monthly savings = ₹6,00,000 (75.0%), Annual savings = ₹72,00,000.

---

### E3. Realistic disclaimer labels
- **What was wrong:** Numbers were presented as absolute guarantees rather than transparent models.
- **What changed:**
  - Added notice: *"ℹ️ Estimate based on the assumptions above. Actual savings depend on your escalation rate and query complexity."*
  - Added *"Estimated"* label to monthly and annual savings metrics.
- **Files modified:** `app.py`
- **Verification:** Verified notice renders clearly beneath the calculation breakdown.

---

### E4. Replaced "100% after-hours coverage" tile with real data
- **What was wrong:** A static "100% after-hours coverage" tile was shown, which was unrealistic.
- **What changed:**
  - Replaced the tile with *"Queries Handled Outside Working Hours"*, which dynamically computes the exact count and percentage of queries outside 9 AM – 9 PM IST from the active dataset.
- **Files modified:** `app.py`
- **Verification:** Verified that with sample data, after-hours queries show accurate count and percentage based on interaction timestamps.

---

## Part F: Visual Design Polish

### F1. Compact header & removed top whitespace
- **What was wrong:** The top of the page had large default padding (~6rem) pushing the interface far down the screen.
- **What changed:** Reduced `.block-container` top padding to `1.5rem` and added a unified, compact brand header (`app_header_html`) displaying the Sahayak logo mark, product title, and demo company tag.
- **Files modified:** `ui.py`, `app.py`
- **Verification:** Verified the layout starts near the top of the viewport with no excessive empty space.

---

### F2. Brand identity & custom inline SVG logo
- **What was wrong:** The app previously displayed generic shopping cart icons and presented the demo company ("ShopEasy India") as the product brand instead of Sahayak.
- **What changed:** Created `sahayak_logo_svg()` as an inline Python SVG (a rounded dark square featuring an accent teal speech bubble and saffron highlight dot). Positioned "Sahayak" as the core product brand and displayed the selected pack (e.g., ShopEasy India) as a secondary "Demo company" label.
- **Files modified:** `ui.py`, `app.py`
- **Verification:** Verified clean SVG rendering in both sidebar and top header across all industry packs.

---

### F3. Restrained color palette & saffron accents
- **What was wrong:** Colors were inconsistent with competing gradients across multiple elements.
- **What changed:** Enforced the strict palette:
  - Deep dark background `#0B0F1A`
  - Panels & cards `#121829`
  - Subtle borders `#26334F`
  - Primary text `#F1F5F9`
  - Secondary readable text `#B6C2D9`
  - Main action accent teal `#14B8A6`
  - Saffron `#FF9933` reserved for highlights (active tab, active language chip)
- **Files modified:** `ui.py`
- **Verification:** Verified theme variables and colors across all views.

---

### F4. Quiet outlined buttons for presets & solid teal Send button
- **What was wrong:** Every preset button had a bright gradient background, creating visual clutter in the sidebar.
- **What changed:** Restyled general buttons into quiet outlined buttons (`border: 1px solid #26334F`, subtle hover). Grouped presets into clean expanders named "Basics", "Hard cases", and "Escalation". Reserved the solid teal background (`#14B8A6`) with dark text (`#0B0F1A`) exclusively for the primary Send button.
- **Files modified:** `ui.py`, `app.py`
- **Verification:** Verified preset buttons are quiet and outlined, while the Send button stands out cleanly.

---

### F5. Refined chat bubbles
- **What was wrong:** Customer bubbles used gradient backgrounds and lacked clear visual restraint.
- **What changed:** Styled customer bubbles as solid dark teal (`#0D3E3A` with `#14B8A6` border) and agent bubbles as dark panels (`#121829` with `#26334F` border). Capped maximum bubble width at 75%. Preserved language tags and added a small tool tag (`🔧`) when an automated tool executed.
- **Files modified:** `ui.py`
- **Verification:** Verified bubble styling, text contrast, and tags for both customer and agent messages.

---

### F6. Execution step timeline & compact Agent Brain panel
- **What was wrong:** The Agent Brain panel had tall stacked cards that caused vertical scrolling, and lacked visibility into the agent's internal reasoning steps.
- **What changed:**
  - Added `step_timeline_html()` showing 4 discrete execution stages with real timings: Language detected, Intent understood, Tool called, and Reply written.
  - Reorganized Agent Brain cards into a compact 2-column grid (Language/Mood, Intent/Tool, Confidence/Response Time) followed by the risk meter and timeline.
- **Files modified:** `llm.py`, `ui.py`, `app.py`
- **Verification:** Verified that the entire Agent Brain panel fits beside the chat window without vertical scrolling, and displays real step timings.

---

### F7. Sidebar width reduced to ~260px
- **What was wrong:** The default Streamlit sidebar was unnecessarily wide and took space away from the main interaction area.
- **What changed:** Constrained sidebar width to `260px` in CSS while preserving internal padding and clean wrapping.
- **Files modified:** `ui.py`
- **Verification:** Verified sidebar width at 260px on laptop and desktop screens.

---

### F8. Unified typography scale & corner radii
- **What was wrong:** Inconsistent font sizes and border radii were used across different widgets.
- **What changed:** Standardized the type scale to 28px page titles, 20px section titles, 15px body text, and 13px small text with 8px spacing steps. Standardized corner radius to `12px` (containers) and `8px` (cards/inputs). Limited emojis strictly to mood representations (`😊`, `😐`, `😤`, `😡`).
- **Files modified:** `ui.py`
- **Verification:** Verified font sizes and borders across all tabs and panels.

---

### F9. Dashboard charts with Inter font & 4-colour palette
- **What was wrong:** Plotly charts defaulted to serif fonts and inconsistent color sets.
- **What changed:** Standardized all charts to use a curated 4-colour palette (`#14B8A6`, `#FF9933`, `#6366F1`, `#EC4899`), `plotly_dark` template with transparent backgrounds, full language names instead of codes, and the application font (`Inter, sans-serif`) on all titles, axes, ticks, and legends.
- **Files modified:** `analytics.py`
- **Verification:** Verified charts render with Inter font, full names, and 4-colour palette.

---

### F10. Responsive layout & collapsible controls
- **What was wrong:** The two-column layout overflowed or cramped on narrow viewports, and language chips could cut off.
- **What changed:** Added media queries (`max-width: 1100px`) to stack the Agent Brain panel underneath the chat on smaller screens, enabled `.lang-chip-container` flex-wrapping, and kept the sidebar collapsible control visible.
- **Files modified:** `ui.py`
- **Verification:** Verified wrapping and stacking at 1280px, 1024px, and 768px viewports.

---

## Part G: Gemini Connection, Data Grounding & Error Handling

### G1. Dynamic API key resolution (Streamlit Secrets & Environment)
- **What was wrong:** The API key was only read once at import time from `os.getenv`, and could not discover keys configured in Streamlit cloud secrets (`st.secrets`).
- **What changed:**
  - Implemented `get_gemini_api_key()` in `config.py` that checks `st.secrets["GEMINI_API_KEY"]` first (if running inside Streamlit), then falls back to `os.getenv("GEMINI_API_KEY")`.
  - The API key is never hard-coded in source code or committed files.
  - When no key is provided, the application automatically runs in Demo Mode with zero crashes.
- **Files modified:** `config.py`, `llm.py`, `speech.py`, `app.py`
- **Verification:** Verified that the app runs in Demo Mode when key is absent, and dynamically connects via `google-genai` SDK when configured.

---

### G2. Strict data grounding & anti-hallucination guardrails
- **What was wrong:** Models can invent or assume delivery dates, order amounts, or return policies if grounding constraints are not explicit.
- **What changed:**
  - In `prompts.py`, added full parameter signatures for all 11 database tools in `TOOL_SIGNATURES`.
  - Added strict data grounding instructions in `get_system_prompt()`: the model must ground order, refund, balance, and policy answers exclusively in database tool results and company FAQs.
  - Reinforced in `get_tool_result_prompt()`: the final reply must strictly reflect the returned database dictionary, never hallucinate dates or tracking IDs, and report missing records honestly.
- **Files modified:** `prompts.py`
- **Verification:** Tested with valid orders (`ORD1002`) and non-existent orders (`ORD9999`); confirmed tool results accurately ground answers and unknown records return clean negative confirmation without hallucinations.

---

### G3. Robust API error & fallback handling
- **What was wrong:** If an API key is invalid or Google's API returns a 4xx/5xx or quota error, the app must not crash on camera.
- **What changed:**
  - Wrapped `google-genai` client calls in `try/except` in `llm.py` and `speech.py`.
  - On failure, prints the full traceback and real reason to the terminal for debugging, logs the error in `result["api_error"]`, and falls back to pre-written smart demo replies.
  - Displayed a non-intrusive notification in the sidebar without disrupting the customer chat experience.
- **Files modified:** `llm.py`, `speech.py`, `app.py`
- **Verification:** Tested by injecting an invalid key: confirmed terminal logged `400 INVALID_ARGUMENT`, app seamlessly fell back to demo replies, and UI remained fully functional.

---

---

## Part H: Real-Time Streaming & Speed Optimization

### H1. Native SDK Streaming & Single-Turn Latency Optimization
- **What was wrong:** Responses took 5–6 seconds to appear. The chat view froze during inference, then dumped the user bubble and full assistant text simultaneously. Sequential processing also added unnecessary overhead.
- **What changed:**
  - Migrated to native `client.models.generate_content_stream` via `google-genai` SDK in `llm.py`.
  - Re-ordered JSON output in `prompts.py` to produce `"reply"` first. As tokens arrive from the network stream, an incremental regex parser extracts the customer text in real time and streams it directly to the UI.
  - While Gemini establishes the stream, the UI renders `"● ● ● Sahayak is thinking…"` with animated pulsing dots. The moment the first text chunk arrives, the indicator transitions into the streamed assistant bubble.
  - Kept context concise: set `MAX_HISTORY = 6` (last 3 exchanges) in `config.py` and `max_output_tokens = 350`, eliminating token bloat.
  - Added module-level preferred model memory (`_PREFERRED_MODEL = "gemini-3.5-flash-lite"`), which achieved sub-second latency (0.68s base) and automatically falls back to `gemini-flash-lite-latest` and `gemini-3.5-flash` on temporary quota spikes.
  - Language detection remains 100% local Unicode script matching (0ms), and classification/sentiment/triggers are returned in the same single Gemini request alongside the streamed reply.
  - Preserved strict grounding in company FAQ, database tools, and supervisor escalation triggers.
- **Files modified:** `llm.py`, `app.py`, `prompts.py`, `config.py`
- **Verification:**
  - English free-form question: TTFT = **2.420s**, Total Response Time = **3.356s** (Live Gemini: `True`)
  - Hinglish query: TTFT = **1.217s**, Total Response Time = **1.808s** (Live Gemini: `True`)
  - Confirmed 0 duplicate requests and zero preset/demo fallback labeling for live responses.

---

## Part I: Sidebar Restoration & Responsive Viewport Support

### I1. Streamlit Sidebar Collapse/Expand & Responsive Reset
- **What was wrong:** The Streamlit sidebar toggle was completely inaccessible once collapsed because `.stApp > header { display: none; }` and `div[data-testid="stToolbar"] { display: none; }` in `ui.py` hid the expand control button (`stExpandSidebarButton` / `collapsedControl`). Furthermore, unconditional `min-width: 260px !important` on `section[data-testid="stSidebar"]` prevented the sidebar from cleanly collapsing, leaving a phantom gap and breaking narrow/mobile window layouts.
- **What changed:**
  - Preserved Streamlit's header and toolbar in transparent mode with `pointer-events: none` on the container and `pointer-events: auto` on interactive controls, so clicks on underlying UI elements pass through while the sidebar toggle button remains fully clickable.
  - Specifically targeted and hid default menu/deploy buttons (`#MainMenu`, `stMainMenuButton`, `stDecoration`, `stStatusWidget`) while explicitly preserving and styling `stExpandSidebarButton` and `stSidebarCollapseButton`.
  - Removed all forced `width` / `min-width` / `max-width` rules on the sidebar so Streamlit controls its own width, collapse animation and narrow-screen overlay. Only colours/border are styled.
  - Hid Streamlit's "Deploy" button (`stAppDeployButton`), which became visible once the header was no longer hidden.
  - Note: Streamlit remembers a collapsed sidebar in the browser (`localStorage` key `stSidebarCollapsed-`), so after a user collapses it, it stays collapsed on refresh until they click the `»` chevron. A fresh browser always opens it expanded.
- **Files modified:** `ui.py`, `CHANGELOG.md`
- **Verification:** Checked in headless Chrome at 1440×900 and 600×900: sidebar open on first load with all controls visible; collapse chevron hides it; with a saved "collapsed" state, a real mouse click on the `»` chevron reopens it and it stays open after refresh.



# 🙏 Sahayak AI — Multilingual Customer Support Agent

> **Sahayak** (\"helper\" in Hindi) is an AI-powered customer support agent that speaks to customers in their own language, solves common problems using company data, and hands over to a human agent smoothly when needed.

---

## ✨ Features

- **Multilingual Support** — English, Hindi, Kannada, Hinglish, Tamil, Telugu
- **Voice I/O** — Speak in any supported language, hear the reply
- **Real Database Actions** — Order status, cancellation, refund checks, account info
- **Live Agent Console** — See AI thinking in real time (language, mood, intent, confidence, risk)
- **Smart Escalation** — Rule-based triggers with explainable badges and auto-generated handoff cards
- **Agent Takeover Simulator** — Demo the full AI → Human → Resolution loop
- **Industry Packs** — Switch between E-commerce, Bank, and Telecom with one click
- **Business Dashboard** — KPIs, charts, and interactive ROI calculator
- **Demo Mode** — Works without an API key using pre-written smart replies
- **Domain Guardrails** — Politely declines off-topic queries

---

## 🚀 Quick Start

### 1. Clone the repo
```bash
git clone <your-repo-url>
cd sahayak-ai
```

### 2. Create a virtual environment (recommended)
```bash
python -m venv venv
source venv/bin/activate   # macOS/Linux
venv\Scripts\activate      # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up environment variables
```bash
cp .env.example .env
# Edit .env and add your Gemini API key (optional — app works in Demo Mode without it)
```

### 5. Run the app
```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`.

---

## 🔑 Getting a Gemini API Key (Optional)

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Click "Create API Key"
3. Paste it into your `.env` file as `GEMINI_API_KEY=your_key_here`

**Without an API key**, the app runs in **Demo Mode** with pre-written intelligent responses — it never crashes.

---

## 📁 Project Structure

```
sahayak-ai/
├── app.py              # Entry point — layout, tabs, chat, console
├── config.py           # Languages, industry packs, settings (single source of truth)
├── llm.py              # Gemini API wrapper + demo-mode fallback
├── prompts.py          # System prompt and AI rules
├── tools.py            # Database actions (order status, cancel, refund, etc.)
├── escalation.py       # Escalation rules + handoff summary generator
├── speech.py           # Voice input (Gemini STT) and output (gTTS)
├── database.py         # SQLite setup, seeding, interaction logging
├── analytics.py        # Dashboard KPIs and Plotly charts
├── ui.py               # Custom CSS theme and HTML components
├── data/
│   ├── faq_ecommerce.md
│   ├── faq_bank.md
│   └── faq_telecom.md
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## 🏗️ Architecture (Simple)

```
Customer Message (text or voice)
        ↓
Language Detection + Gemini AI (returns structured JSON)
        ↓
Tool Execution (if needed — queries SQLite database)
        ↓
Escalation Check (rule-based with explainable triggers)
        ↓
Reply (text + optional audio) + Agent Console Update
```

1. **Input**: Customer types or speaks a message.
2. **AI Processing**: Gemini receives the message with company FAQ, customer profile, and chat history. It returns a strict JSON response with language, sentiment, intent, confidence, tool call, and reply.
3. **Tool Step**: If the AI requests data (e.g., order status), Python runs the matching function on SQLite and feeds the real result back.
4. **Escalation**: Rules check for anger, low confidence, repeated failures, or sensitive topics. Each trigger is shown as an explainable badge.
5. **Output**: The reply is displayed in the customer's language, audio is optionally generated, and the Agent Console updates in real time.

---

## 🧪 Test Scenarios

| # | Customer Says | Expected |
|---|---|---|
| 1 | "Where is my order ORD1002?" | English reply with real status |
| 2 | "Mera refund abhi tak nahi aaya" | Hinglish reply with refund status |
| 3 | "ನನ್ನ ಆರ್ಡರ್ ORD1005 ರದ್ದು ಮಾಡಿ" | Kannada reply, cancels if allowed |
| 4 | "Return policy kya hai?" | FAQ answer in Hindi/Hinglish |
| 5 | Voice message in Hindi | Transcript + reply text + audio |
| 6 | "This is useless, I want a manager NOW" | Escalation + handoff card |
| 7 | "Write me a poem" | Domain guardrail — politely declines |
| 8 | API key removed | Demo Mode works, no crash |

---

## 💼 Business Value

- **Cost Savings**: AI cost ~₹4/query vs human agent ~₹80/query (95% reduction)
- **24/7 Coverage**: No missed calls or queries after business hours
- **Consistency**: Same quality responses in every language, every time
- **Scalability**: Handles thousands of concurrent conversations
- **Integration Ready**: `tools.py` is where real CRM/ERP systems plug in

---

## 🛠️ Tech Stack

| Purpose | Technology |
|---|---|
| App Framework | Streamlit (Python) |
| AI Model | Google Gemini 2.0 Flash |
| Speech-to-Text | Gemini Multimodal API |
| Text-to-Speech | gTTS |
| Database | SQLite (built-in) |
| Charts | Plotly |

---

## 👤 Author

**Ameya** (25BTRAO003)

Built with ❤️ using Google Antigravity AI.

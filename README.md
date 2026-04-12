# शारदा ज्वेलर्स — WhatsApp Chatbot 🪙

**Sharda Jewellers, Bemetara** — सन् 1971 से, पीढ़ियों का भरोसा।

An intelligent WhatsApp chatbot that handles customer queries, shows live gold/silver rates in INR, and showcases Sharda Jewellers' products — all in Hindi and English.

---

## What This Bot Does

- Greets customers in Hindi/English (auto-detects language)
- Shows **live gold & silver rates** in INR (24K, 22K, 18K gold + silver)
- Answers questions about products, custom orders, store history
- Provides interactive button menus for easy navigation
- Remembers conversation context per customer
- Handles Hinglish (mixed Hindi-English) naturally

---

## Setup Guide (Step by Step)

Follow these 6 steps. Total time: ~35 minutes.

---

### Step 1: Get a Google Gemini API Key (2 minutes)

This powers the chatbot's brain.

1. Go to **https://aistudio.google.com/apikey**
2. Sign in with any Google account
3. Click **"Create API Key"**
4. Copy the key — save it somewhere safe

> **Cost**: FREE (250 requests/day = ~7,500/month — plenty for a local store)

---

### Step 2: Get a GoldPricez API Key (2 minutes)

This provides live gold/silver rates.

1. Go to **https://goldpricez.com/key/registration**
2. Register with your email
3. Send an email to **goldpricekg@gmail.com** saying "Please activate my API key"
4. You'll receive the key within 24 hours

> **Cost**: FREE (30-60 requests/hour)

---

### Step 3: Create a Meta Business Account (10 minutes)

This connects to WhatsApp.

1. Go to **https://business.facebook.com/**
2. Click **"Create Account"**
3. Enter:
   - Business name: **Sharda Jewellers**
   - Your name and email
4. Verify your email
5. Fill in business details:
   - Category: **Jewelry Store**
   - Address: Bemetara, Chhattisgarh, India

---

### Step 4: Set Up WhatsApp Business API (15 minutes)

1. Go to **https://developers.facebook.com/**
2. Click **"My Apps"** → **"Create App"**
3. Select app type: **"Business"**
4. Enter app name: **"Sharda Jewellers Bot"**
5. After creation, in the left sidebar, click **"Add Product"**
6. Find **"WhatsApp"** and click **"Set Up"**
7. You'll see a **"Get Started"** page with:
   - **Phone Number ID** — copy this (you need it later)
   - **Temporary Access Token** — copy this (you need it later)

#### For a Permanent Token (recommended):

1. In the left sidebar, go to **WhatsApp** → **Configuration**
2. Under "Webhook", you'll add the URL later (Step 6)
3. Go to **Business Settings** → **System Users**
4. Create a system user → Generate a permanent token with `whatsapp_business_messaging` permission

> **Cost**: 1,000 free conversations/month. After that, ~₹2.30 per conversation.

---

### Step 5: Deploy to Render (5 minutes)

#### Option A: One-Click Deploy (Easiest)

1. Push this `sharda-jewellers-bot` folder to a **GitHub repository**:
   ```bash
   cd sharda-jewellers-bot
   git init
   git add .
   git commit -m "Sharda Jewellers WhatsApp bot"
   # Create a repo on github.com, then:
   git remote add origin https://github.com/YOUR_USERNAME/sharda-jewellers-bot.git
   git branch -M main
   git push -u origin main
   ```

2. Go to **https://render.com/** → Sign up (free)

3. Click **"New"** → **"Web Service"**

4. Connect your GitHub and select the `sharda-jewellers-bot` repo

5. Configure:
   - **Name**: `sharda-jewellers-bot`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

6. Click **"Advanced"** → **"Add Environment Variable"** and add these:

   | Key | Value |
   |-----|-------|
   | `WHATSAPP_TOKEN` | Your token from Step 4 |
   | `WHATSAPP_PHONE_NUMBER_ID` | Your Phone Number ID from Step 4 |
   | `WHATSAPP_VERIFY_TOKEN` | `sharda-jewellers-bot-2024` (or any secret you choose) |
   | `GEMINI_API_KEY` | Your key from Step 1 |
   | `GOLD_API_KEY` | Your key from Step 2 |

7. Click **"Create Web Service"**

8. Wait 2-3 minutes for deployment. You'll get a URL like:
   `https://sharda-jewellers-bot.onrender.com`

9. Test by visiting that URL in a browser — you should see:
   ```json
   {"status": "running", "bot": "Sharda Jewellers WhatsApp Bot", "since": 1971}
   ```

> **Cost**: FREE tier available (spins down after 15 min inactivity). For always-on: $7/month (~₹590/month).

#### Option B: Railway (Alternative)

1. Go to **https://railway.app/** → Sign up
2. Click **"New Project"** → **"Deploy from GitHub Repo"**
3. Select the repo and add the same environment variables
4. Railway gives you a URL automatically

> **Cost**: $5/month (~₹420/month), always-on, no cold starts.

---

### Step 6: Connect Webhook to WhatsApp (2 minutes)

This is the final step that connects everything.

1. Go back to **https://developers.facebook.com/** → Your App
2. In the left sidebar: **WhatsApp** → **Configuration**
3. Under **"Webhook"**, click **"Edit"**
4. Enter:
   - **Callback URL**: `https://sharda-jewellers-bot.onrender.com/webhook`
     (replace with your actual Render/Railway URL)
   - **Verify Token**: `sharda-jewellers-bot-2024`
     (must match what you set in Step 5)
5. Click **"Verify and Save"**
6. Under **"Webhook Fields"**, click **"Subscribe"** next to **"messages"**

**That's it! Your bot is live.**

---

## Test It

1. Open WhatsApp on your phone
2. Send a message to the WhatsApp Business number you set up
3. Try:
   - `नमस्ते` → You'll get a welcome message with menu buttons
   - `आज के भाव` → You'll see live gold/silver rates
   - `शादी के लिए गहने चाहिए` → AI will guide you through bridal collection options
   - `custom order कैसे करें?` → Info about in-house manufacturing

---

## Monthly Cost Summary

| Service | Free Tier | Paid Tier |
|---------|-----------|-----------|
| WhatsApp API | 1,000 conversations/month free | ~₹2.30/conversation after |
| Google Gemini AI | 250 requests/day free | ₹0.50-1 per 1K tokens |
| GoldPricez API | 30-60 requests/hour free | — |
| Render Hosting | Free (cold starts) | ₹590/month (always-on) |
| **Total** | **₹0/month** | **~₹590/month** |

---

## Troubleshooting

**Bot not replying?**
- Check Render logs: Dashboard → Your service → "Logs"
- Make sure all 5 environment variables are set correctly
- Verify webhook is subscribed to "messages" in Meta dashboard

**"Webhook verification failed"?**
- Make sure WHATSAPP_VERIFY_TOKEN matches in both Render env vars AND Meta webhook settings

**Rates showing ₹0?**
- Your GoldPricez API key may not be activated yet
- Email goldpricekg@gmail.com to activate it

**Slow first response?**
- On Render free tier, the server sleeps after 15 min inactivity
- First message after sleep takes ~30-60 seconds
- Upgrade to paid ($7/month) for instant responses

---

## File Structure

```
sharda-jewellers-bot/
├── app/
│   ├── __init__.py        # Package init
│   ├── main.py            # FastAPI routes + webhook handlers
│   ├── config.py          # Environment variable configuration
│   ├── whatsapp.py        # WhatsApp message send/receive
│   ├── chatbot.py         # Gemini AI + Sharda Jewellers knowledge
│   └── gold_rates.py      # Live gold/silver rate fetcher
├── requirements.txt       # Python dependencies
├── render.yaml            # Render deployment config
├── Procfile               # Process file for deployment
├── .env.example           # Environment variable template
└── README.md              # This file
```

---

Built with ❤️ for शारदा ज्वेलर्स, बेमेतरा — सन् 1971 से, पीढ़ियों का भरोसा।

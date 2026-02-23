# Unlimited Free Email API

Send unlimited emails for free by rotating through multiple free email providers.

## Free Provider Limits

| Provider | Free Limit | Period |
|----------|-----------|--------|
| Resend | 3,000 | month |
| Gmail | 500 | day |
| Outlook | 300 | day |
| Yahoo | 500 | day |
| Zoho | 200 | day |

**With all 5 providers:** ~4,500 emails/day = **~135,000 emails/month free**

## Quick Start

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Configure providers:**
```bash
cp .env.example .env
# Edit .env and add at least one provider
```

3. **Run the API:**
```bash
python app.py
```

## API Usage

### Send Email
```bash
curl -X POST http://localhost:8000/send-email \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "to_email": "recipient@example.com",
    "subject": "Hello",
    "body": "This is the email body",
    "from_name": "Your Name"
  }'
```

### Check Stats
```bash
curl http://localhost:8000/stats \
  -H "X-API-Key: your-api-key"
```

## Provider Setup

### 1. Resend.com (Easiest)
- Sign up at [resend.com](https://resend.com)
- Get API key
- Add to `.env`

### 2. Gmail
- Enable 2FA on your Google account
- Generate App Password at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
- Use that 16-char password (not your regular password)

### 3. Outlook
- Use your regular Outlook password
- May need to enable "Less secure app access" or use App Password

### 4. Yahoo
- Generate App Password in Yahoo Account Security settings

### 5. Zoho
- Sign up for free at [zoho.com/mail](https://zoho.com/mail)
- Use your Zoho password

## How It Works

1. API tries providers in order
2. Tracks usage per provider per day/month
3. Automatically switches when a provider hits its limit
4. Returns usage stats in every response

## Deploy to Render (Free)

1. Push to GitHub
2. Create Web Service on [render.com](https://render.com)
3. Add environment variables from `.env`
4. Done!

## Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/` | GET | No | API info |
| `/health` | GET | No | Health check |
| `/send-email` | POST | Yes | Send email |
| `/stats` | GET | Yes | Usage stats |
| `/docs` | GET | No | API docs (Swagger) |

## Response Example

```json
{
  "success": true,
  "message": "Email sent via resend",
  "provider": "resend",
  "message_id": "abc-123",
  "usage": "1/3000 month"
}
```

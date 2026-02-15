# Deployment Guide

## Quick Deploy Options

### Option 1: Railway.app (Recommended - Free Tier Available)

#### Method A: Web Interface (Easiest)

1. Go to [railway.app](https://railway.app) and sign up/login
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose `ezra-anchovy/payment-recovery-tool`
5. Railway will auto-detect the configuration
6. Add environment variables:
   - Click **"Variables"** tab
   - Add `STRIPE_SECRET_KEY` = your test key (starts with `sk_test_`)
   - Add `STRIPE_WEBHOOK_SECRET` = your webhook secret (starts with `whsec_`)
7. Click **"Deploy"**
8. Once deployed, copy your Railway URL (e.g., `https://payment-recovery-production.up.railway.app`)

#### Method B: Railway CLI

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Navigate to project directory
cd /path/to/payment-recovery-tool

# Initialize Railway project
railway init

# Add environment variables
railway variables set STRIPE_SECRET_KEY=sk_test_...
railway variables set STRIPE_WEBHOOK_SECRET=whsec_...

# Deploy
railway up

# Get deployment URL
railway domain
```

### Option 2: Heroku

#### Prerequisites
- Heroku account (free tier available)
- Heroku CLI installed

#### Steps

```bash
# Install Heroku CLI (if not installed)
# macOS: brew install heroku/brew/heroku
# Ubuntu: sudo snap install heroku --classic

# Login to Heroku
heroku login

# Create new Heroku app
cd /path/to/payment-recovery-tool
heroku create payment-recovery-[your-name]

# Set environment variables
heroku config:set STRIPE_SECRET_KEY=sk_test_...
heroku config:set STRIPE_WEBHOOK_SECRET=whsec_...

# Deploy
git push heroku main

# Open your app
heroku open
```

### Option 3: Render.com

1. Go to [render.com](https://render.com) and sign up
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub account
4. Select `ezra-anchovy/payment-recovery-tool`
5. Configure:
   - **Name**: payment-recovery
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
6. Add environment variables:
   - `STRIPE_SECRET_KEY`
   - `STRIPE_WEBHOOK_SECRET`
7. Click **"Create Web Service"**

### Option 4: DigitalOcean App Platform

1. Go to [cloud.digitalocean.com/apps](https://cloud.digitalocean.com/apps)
2. Click **"Create App"**
3. Connect GitHub and select `ezra-anchovy/payment-recovery-tool`
4. DigitalOcean will auto-detect Python app
5. Add environment variables in the settings
6. Deploy

### Option 5: Fly.io

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login
fly auth login

# Launch app
cd /path/to/payment-recovery-tool
fly launch

# Set secrets
fly secrets set STRIPE_SECRET_KEY=sk_test_...
fly secrets set STRIPE_WEBHOOK_SECRET=whsec_...

# Deploy
fly deploy
```

## Post-Deployment: Configure Stripe Webhook

After deploying to any platform, you need to configure Stripe to send webhooks:

### Step 1: Get Your Deployment URL

Your deployment URL will be something like:
- Railway: `https://payment-recovery-production.up.railway.app`
- Heroku: `https://payment-recovery-yourname.herokuapp.com`
- Render: `https://payment-recovery.onrender.com`

### Step 2: Add Webhook in Stripe Dashboard

1. Go to [Stripe Dashboard](https://dashboard.stripe.com)
2. Switch to **Test mode** (toggle in top right)
3. Navigate to **Developers** → **Webhooks**
4. Click **"Add endpoint"**
5. Enter your webhook URL:
   ```
   https://your-deployment-url.com/webhook/stripe
   ```
6. Select events to listen to:
   - ✅ `invoice.payment_failed`
7. Click **"Add endpoint"**

### Step 3: Get Webhook Signing Secret

1. Click on your newly created webhook
2. Click **"Reveal"** next to **Signing secret**
3. Copy the secret (starts with `whsec_`)
4. Update your deployment's environment variable:
   - Railway: Dashboard → Variables → Edit `STRIPE_WEBHOOK_SECRET`
   - Heroku: `heroku config:set STRIPE_WEBHOOK_SECRET=whsec_...`
   - Render: Dashboard → Environment → Edit

## Testing Your Deployment

### 1. Health Check

```bash
curl https://your-deployment-url.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2026-02-15T03:45:12.123456"
}
```

### 2. Landing Page

Visit: `https://your-deployment-url.com/`

You should see the Payment Recovery Tool landing page with ROI calculator.

### 3. Dashboard

Visit: `https://your-deployment-url.com/dashboard`

You should see the recovery dashboard (empty at first).

### 4. Test Webhook with Stripe CLI

```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe

# Login
stripe login

# Forward webhooks to your deployment
stripe listen --forward-to https://your-deployment-url.com/webhook/stripe

# In another terminal, trigger test event
stripe trigger invoice.payment_failed
```

Check your dashboard - you should see the failed payment appear!

## Production Checklist

Before going live with real customers:

### 1. Switch to Live Stripe Keys

- [ ] Get live API key from Stripe Dashboard (starts with `sk_live_`)
- [ ] Create webhook in **Live mode** (not test mode)
- [ ] Update environment variables with live keys
- [ ] Test with a real failed payment

### 2. Add Email Provider

The app includes email templates but needs an email service. Choose one:

#### SendGrid (Recommended)

```python
# Add to requirements.txt
sendgrid==6.10.0

# Update send_email function in app.py
import sendgrid
from sendgrid.helpers.mail import Mail

def send_email(to_email, template_name, data):
    sg = sendgrid.SendGridAPIClient(api_key=os.environ.get('SENDGRID_API_KEY'))
    message = Mail(
        from_email='noreply@yourcompany.com',
        to_emails=to_email,
        subject=data.get('subject', 'Payment Update'),
        html_content=content
    )
    sg.send(message)
```

Environment variable: `SENDGRID_API_KEY`

#### Mailgun

```python
# Add to requirements.txt
requests

# Update send_email function
import requests

def send_email(to_email, template_name, data):
    requests.post(
        f"https://api.mailgun.net/v3/{os.environ.get('MAILGUN_DOMAIN')}/messages",
        auth=("api", os.environ.get('MAILGUN_API_KEY')),
        data={
            "from": "noreply@yourcompany.com",
            "to": to_email,
            "subject": data.get('subject'),
            "html": content
        }
    )
```

Environment variables: `MAILGUN_API_KEY`, `MAILGUN_DOMAIN`

### 3. Add Database (Recommended)

Replace in-memory storage with PostgreSQL:

**Railway:** Add PostgreSQL plugin (free tier available)

**Heroku:** Add Heroku Postgres add-on

**Code changes:**

```python
# Add to requirements.txt
psycopg2-binary
SQLAlchemy

# Update app.py
from flask_sqlalchemy import SQLAlchemy

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
db = SQLAlchemy(app)

class FailedPayment(db.Model):
    id = db.Column(db.String, primary_key=True)
    customer_id = db.Column(db.String)
    customer_name = db.Column(db.String)
    email = db.Column(db.String)
    amount = db.Column(db.Float)
    currency = db.Column(db.String)
    status = db.Column(db.String)
    attempts = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_attempt = db.Column(db.DateTime)
    recovered_at = db.Column(db.DateTime)
```

### 4. Security Enhancements

- [ ] Add HTTPS enforcement (most platforms do this automatically)
- [ ] Enable webhook signature verification (already implemented)
- [ ] Add rate limiting to prevent abuse
- [ ] Set up monitoring (Sentry, DataDog, etc.)
- [ ] Configure logging

### 5. Monitoring & Alerts

Add monitoring for:
- Failed webhook deliveries
- Recovery rate drops
- Server errors
- Response time

Recommended tools:
- **Sentry** - Error tracking
- **Better Uptime** - Uptime monitoring
- **Stripe Dashboard** - Webhook delivery monitoring

## Troubleshooting

### Webhook Not Receiving Events

1. Check webhook URL is correct in Stripe Dashboard
2. Verify webhook secret is set correctly
3. Check server logs for errors
4. Use Stripe CLI to test: `stripe listen --forward-to YOUR_URL/webhook/stripe`

### "Module Not Found" Errors

```bash
# Ensure requirements.txt is complete
pip freeze > requirements.txt

# Rebuild on your platform
railway up  # or your platform's deploy command
```

### Port Issues

Railway, Heroku, and most platforms automatically set the `PORT` environment variable. The app reads from `os.environ.get('PORT')` so this should work automatically.

### Database Connection Errors

If using PostgreSQL, ensure:
- Database add-on is provisioned
- `DATABASE_URL` environment variable is set
- Connection string format is correct (some platforms use `postgres://` vs `postgresql://`)

## Cost Estimates

### Free Tier Limits

| Platform | Free Tier | Limits |
|----------|-----------|--------|
| Railway | $5/month credit | 500 hours execution, 1GB RAM |
| Heroku | Free dyno (550 hours/month) | Sleeps after 30 min inactivity |
| Render | 750 hours/month | Free tier available |
| Fly.io | Generous free tier | 3 shared-cpu VMs |

### Scaling

For most small-medium SaaS businesses (<10k subscribers), free tier is sufficient. Upgrade when:
- Processing >1000 failed payments/month
- Need 24/7 uptime (Heroku free dyno sleeps)
- Need faster response times
- Want dedicated database

## Support

- **Issues**: [GitHub Issues](https://github.com/ezra-anchovy/payment-recovery-tool/issues)
- **Documentation**: [README.md](https://github.com/ezra-anchovy/payment-recovery-tool)
- **Stripe Docs**: [Stripe Webhooks Guide](https://stripe.com/docs/webhooks)

## Next Steps

1. ✅ Deploy to your chosen platform
2. ✅ Configure Stripe webhook
3. ✅ Test with Stripe CLI
4. ✅ Add email provider (SendGrid/Mailgun)
5. ✅ Switch to live Stripe keys
6. ✅ Monitor recovery dashboard

Good luck recovering that revenue! 💰

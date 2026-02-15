# Quick Start Guide - 5 Minutes to Live

## Step 1: Deploy to Railway (2 minutes)

1. Go to **[railway.app](https://railway.app)** and sign up
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Connect GitHub and select `ezra-anchovy/payment-recovery-tool`
4. Railway auto-detects everything ✅
5. Click **"Deploy"**

## Step 2: Configure Environment (1 minute)

In Railway dashboard:
1. Click **"Variables"** tab
2. Add two variables:
   ```
   STRIPE_SECRET_KEY = sk_test_51... (get from Stripe Dashboard → API Keys)
   STRIPE_WEBHOOK_SECRET = whsec_... (we'll get this next)
   ```
3. Save

## Step 3: Set Up Stripe Webhook (2 minutes)

1. Copy your Railway URL: `https://payment-recovery-production-xxx.up.railway.app`
2. Go to [Stripe Dashboard](https://dashboard.stripe.com) (Test mode)
3. Navigate: **Developers** → **Webhooks** → **Add endpoint**
4. Endpoint URL: `https://your-railway-url.com/webhook/stripe`
5. Events: Select `invoice.payment_failed`
6. Click **"Add endpoint"** → **"Reveal"** signing secret
7. Copy the `whsec_...` secret
8. Go back to Railway → Variables → Update `STRIPE_WEBHOOK_SECRET`

## Step 4: Test It! (30 seconds)

```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe

# Login
stripe login

# Trigger a test failed payment
stripe trigger invoice.payment_failed
```

Visit your dashboard: `https://your-railway-url.com/dashboard`

You should see the failed payment appear! 🎉

## What You Just Built

✅ **Webhook endpoint** - Receives Stripe payment failures in real-time  
✅ **Smart retry logic** - Automatically retries at 1h, 24h, 3 days, 7 days  
✅ **Email templates** - 6 professional email templates (needs email provider)  
✅ **Recovery dashboard** - Track success rate and recovered revenue  
✅ **ROI calculator** - Landing page at your-url.com/  

## Next Steps

### Add Email (SendGrid Free Tier)

1. Sign up at [sendgrid.com](https://sendgrid.com) (free 100 emails/day)
2. Get API key
3. Add to Railway: `SENDGRID_API_KEY = SG.xxx`
4. Update `app.py` with SendGrid code (see DEPLOYMENT.md)

### Go Live

When ready for production:
1. Switch Stripe to **Live mode**
2. Get live API key (`sk_live_...`)
3. Create webhook in Stripe **Live mode**
4. Update Railway environment variables
5. Start recovering real revenue! 💰

## Troubleshooting

**Webhook not working?**
- Check webhook URL in Stripe matches your Railway URL
- Verify `STRIPE_WEBHOOK_SECRET` is correct
- Check Railway logs for errors

**App not loading?**
- Railway takes 1-2 minutes to deploy
- Check Railway deployment logs
- Verify environment variables are set

**Need help?**
- [Full Documentation](README.md)
- [Deployment Guide](DEPLOYMENT.md)
- [GitHub Issues](https://github.com/ezra-anchovy/payment-recovery-tool/issues)

---

**Built in 5 minutes. Recovering revenue in real-time.** ⚡️

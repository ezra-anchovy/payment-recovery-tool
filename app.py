"""
Failed Payment Recovery Tool - Flask App
Handles Stripe payment_failed webhooks and manages retry logic.
"""

import os
import json
import stripe
from flask import Flask, request, jsonify, render_template_string
from datetime import datetime
from retry_logic import RetryScheduler, PaymentAttempt
import threading
import time

app = Flask(__name__)

# Configuration
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', 'sk_test_...')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', 'whsec_...')
stripe.api_key = STRIPE_SECRET_KEY

# In-memory storage (replace with database in production)
failed_payments = {}
recovery_stats = {
    'total_failed': 0,
    'total_recovered': 0,
    'revenue_lost': 0.0,
    'revenue_recovered': 0.0,
    'recovery_rate': 0.0
}

# Initialize retry scheduler
scheduler = RetryScheduler(failed_payments, recovery_stats)


def send_email(to_email, template_name, data):
    """
    Send email using template.
    In production, integrate with SendGrid, Mailgun, or AWS SES.
    """
    template_path = os.path.join('templates', f'{template_name}.html')
    if os.path.exists(template_path):
        with open(template_path, 'r') as f:
            content = f.read()
        # Simple template substitution
        for key, value in data.items():
            content = content.replace(f'{{{{{key}}}}}', str(value))
        
        print(f"[EMAIL] Sending {template_name} to {to_email}")
        print(f"[EMAIL] Subject: {data.get('subject', 'Payment Update')}")
        # In production: actual email sending logic here
        return True
    return False


def process_retry(payment_id):
    """Process a scheduled retry attempt."""
    if payment_id not in failed_payments:
        return
    
    payment = failed_payments[payment_id]
    attempt_number = payment['attempts'] + 1
    
    try:
        # Attempt to charge the customer again
        # In production, use Stripe PaymentIntents or Charges API
        # stripe.PaymentIntent.create(...)
        
        # For demo, simulate success/failure
        import random
        success = random.random() < 0.3  # 30% recovery rate simulation
        
        if success:
            payment['status'] = 'recovered'
            payment['recovered_at'] = datetime.now().isoformat()
            recovery_stats['total_recovered'] += 1
            recovery_stats['revenue_recovered'] += payment['amount']
            update_recovery_rate()
            
            # Send success email
            send_email(payment['email'], 'recovery_success', {
                'customer_name': payment['customer_name'],
                'amount': f"${payment['amount']:.2f}",
                'subject': 'Payment Successful!'
            })
            
            print(f"[RECOVERED] Payment {payment_id} - ${payment['amount']:.2f}")
        else:
            payment['attempts'] = attempt_number
            payment['last_attempt'] = datetime.now().isoformat()
            
            # Schedule next retry
            if attempt_number < 4:
                next_template = ['retry_1hour', 'retry_24hours', 'retry_3days'][attempt_number - 1]
                scheduler.schedule_retry(payment_id, attempt_number)
                
                send_email(payment['email'], next_template, {
                    'customer_name': payment['customer_name'],
                    'amount': f"${payment['amount']:.2f}",
                    'attempt': attempt_number,
                    'subject': f'Payment Update - Attempt {attempt_number + 1}'
                })
            else:
                payment['status'] = 'abandoned'
                print(f"[ABANDONED] Payment {payment_id} - ${payment['amount']:.2f}")
                
                send_email(payment['email'], 'final_notice', {
                    'customer_name': payment['customer_name'],
                    'amount': f"${payment['amount']:.2f}",
                    'subject': 'Final Notice - Action Required'
                })
    
    except Exception as e:
        print(f"[ERROR] Retry failed for {payment_id}: {e}")


def update_recovery_rate():
    """Update recovery rate percentage."""
    if recovery_stats['total_failed'] > 0:
        recovery_stats['recovery_rate'] = (
            recovery_stats['total_recovered'] / recovery_stats['total_failed'] * 100
        )


@app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events."""
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError as e:
        return jsonify({'error': 'Invalid signature'}), 400
    
    # Handle payment failed event
    if event['type'] == 'invoice.payment_failed':
        invoice = event['data']['object']
        
        payment_id = invoice.get('id')
        customer_id = invoice.get('customer')
        amount = invoice.get('amount_due', 0) / 100  # Convert cents to dollars
        currency = invoice.get('currency', 'usd').upper()
        
        # Get customer details
        try:
            customer = stripe.Customer.retrieve(customer_id)
            customer_email = customer.email
            customer_name = customer.name or 'Valued Customer'
        except:
            customer_email = invoice.get('customer_email', 'unknown@example.com')
            customer_name = 'Valued Customer'
        
        # Record failed payment
        failed_payments[payment_id] = {
            'id': payment_id,
            'customer_id': customer_id,
            'customer_name': customer_name,
            'email': customer_email,
            'amount': amount,
            'currency': currency,
            'status': 'failed',
            'attempts': 0,
            'created_at': datetime.now().isoformat(),
            'last_attempt': None,
            'recovered_at': None
        }
        
        # Update stats
        recovery_stats['total_failed'] += 1
        recovery_stats['revenue_lost'] += amount
        
        # Schedule first retry (1 hour)
        scheduler.schedule_retry(payment_id, 0)
        
        # Send immediate failure notification
        send_email(customer_email, 'payment_failed', {
            'customer_name': customer_name,
            'amount': f"${amount:.2f}",
            'subject': 'Payment Attempt Failed'
        })
        
        print(f"[FAILED] Payment {payment_id} - ${amount:.2f} from {customer_email}")
    
    return jsonify({'status': 'success'}), 200


@app.route('/dashboard', methods=['GET'])
def dashboard():
    """Display recovery dashboard."""
    # Calculate ROI
    roi_percentage = 0
    if recovery_stats['revenue_lost'] > 0:
        roi_percentage = (recovery_stats['revenue_recovered'] / recovery_stats['revenue_lost']) * 100
    
    dashboard_html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Payment Recovery Dashboard</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; }
            h1 { color: #333; }
            .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
            .stat-card { background: white; padding: 25px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
            .stat-card h3 { margin: 0 0 10px 0; color: #666; font-size: 14px; text-transform: uppercase; }
            .stat-card .value { font-size: 32px; font-weight: bold; color: #333; }
            .stat-card.success .value { color: #10b981; }
            .stat-card.warning .value { color: #f59e0b; }
            .stat-card.danger .value { color: #ef4444; }
            .roi-banner { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 12px; margin-bottom: 30px; text-align: center; }
            .roi-banner h2 { margin: 0 0 10px 0; font-size: 24px; }
            .roi-banner .roi-value { font-size: 48px; font-weight: bold; }
            .payments-table { background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
            table { width: 100%; border-collapse: collapse; }
            th, td { padding: 15px; text-align: left; border-bottom: 1px solid #eee; }
            th { background: #f9f9f9; font-weight: 600; color: #666; }
            .status-badge { padding: 5px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; }
            .status-failed { background: #fee2e2; color: #dc2626; }
            .status-recovered { background: #d1fae5; color: #059669; }
            .status-abandoned { background: #f3f4f6; color: #6b7280; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>💳 Payment Recovery Dashboard</h1>
            
            <div class="roi-banner">
                <h2>Recovery ROI</h2>
                <div class="roi-value">We recovered ${{ "%.2f"|format(revenue_recovered) }} of your ${{ "%.2f"|format(revenue_lost) }} in failed payments</div>
                <p>{{ "%.1f"|format(roi_percentage) }}% recovery rate</p>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card danger">
                    <h3>Total Failed</h3>
                    <div class="value">{{ total_failed }}</div>
                </div>
                <div class="stat-card success">
                    <h3>Recovered</h3>
                    <div class="value">{{ total_recovered }}</div>
                </div>
                <div class="stat-card warning">
                    <h3>Revenue Lost</h3>
                    <div class="value">${{ "%.2f"|format(revenue_lost) }}</div>
                </div>
                <div class="stat-card success">
                    <h3>Revenue Recovered</h3>
                    <div class="value">${{ "%.2f"|format(revenue_recovered) }}</div>
                </div>
            </div>
            
            <div class="payments-table">
                <table>
                    <thead>
                        <tr>
                            <th>Payment ID</th>
                            <th>Customer</th>
                            <th>Amount</th>
                            <th>Attempts</th>
                            <th>Status</th>
                            <th>Created</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for payment in payments %}
                        <tr>
                            <td><code>{{ payment.id[:12] }}...</code></td>
                            <td>{{ payment.customer_name }}</td>
                            <td>${{ "%.2f"|format(payment.amount) }}</td>
                            <td>{{ payment.attempts }}</td>
                            <td>
                                <span class="status-badge status-{{ payment.status }}">
                                    {{ payment.status|upper }}
                                </span>
                            </td>
                            <td>{{ payment.created_at[:10] }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    '''
    
    return render_template_string(
        dashboard_html,
        total_failed=recovery_stats['total_failed'],
        total_recovered=recovery_stats['total_recovered'],
        revenue_lost=recovery_stats['revenue_lost'],
        revenue_recovered=recovery_stats['revenue_recovered'],
        roi_percentage=roi_percentage,
        payments=list(failed_payments.values())
    )


@app.route('/api/stats', methods=['GET'])
def api_stats():
    """JSON API for stats."""
    return jsonify({
        'stats': recovery_stats,
        'payments': list(failed_payments.values())
    })


@app.route('/', methods=['GET'])
def landing():
    """Landing page."""
    return render_template_string(open('templates/landing.html').read())


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})


if __name__ == '__main__':
    # Start the retry scheduler in a background thread
    scheduler_thread = threading.Thread(target=scheduler.run, daemon=True)
    scheduler_thread.start()
    
    print("=" * 50)
    print("💳 Payment Recovery Tool Started")
    print("=" * 50)
    print(f"Dashboard: http://localhost:5000/dashboard")
    print(f"Webhook:   http://localhost:5000/webhook/stripe")
    print(f"Health:    http://localhost:5000/health")
    print("=" * 50)
    
    app.run(port=5000, debug=True)

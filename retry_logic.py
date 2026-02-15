"""
Retry Logic Module - Smart Payment Retry Scheduling
Implements intelligent retry timing: 1 hour, 24 hours, 3 days, 7 days
"""

import threading
import time
from datetime import datetime, timedelta
from collections import defaultdict


class PaymentAttempt:
    """Represents a payment retry attempt."""
    
    def __init__(self, payment_id, attempt_number, scheduled_time):
        self.payment_id = payment_id
        self.attempt_number = attempt_number
        self.scheduled_time = scheduled_time
        self.created_at = datetime.now()
        self.completed = False
    
    def __repr__(self):
        return f"PaymentAttempt({self.payment_id}, attempt={self.attempt_number}, at={self.scheduled_time})"


class RetryScheduler:
    """
    Smart retry scheduler with exponential backoff.
    
    Retry Schedule:
    - Attempt 1: 1 hour after failure
    - Attempt 2: 24 hours after failure  
    - Attempt 3: 3 days after failure
    - Attempt 4: 7 days after failure (final)
    """
    
    # Retry intervals in hours
    RETRY_INTERVALS = [
        1,      # 1 hour
        24,     # 24 hours (1 day)
        72,     # 72 hours (3 days)
        168     # 168 hours (7 days)
    ]
    
    # Best times to retry (hour of day, 0-23)
    # Studies show these times have higher success rates
    OPTIMAL_HOURS = [10, 14, 19]  # 10am, 2pm, 7pm local time
    
    def __init__(self, failed_payments_dict, stats_dict):
        self.failed_payments = failed_payments_dict
        self.stats = stats_dict
        self.retry_queue = []
        self.lock = threading.Lock()
        self.callbacks = {}
        self.running = False
        
        # Analytics tracking
        self.analytics = {
            'attempts_by_hour': defaultdict(int),
            'success_by_hour': defaultdict(int),
            'total_attempts': 0,
            'successful_attempts': 0
        }
    
    def register_callback(self, payment_id, callback):
        """Register a callback for when a retry should be processed."""
        self.callbacks[payment_id] = callback
    
    def schedule_retry(self, payment_id, current_attempt):
        """
        Schedule the next retry attempt for a failed payment.
        
        Args:
            payment_id: The Stripe invoice/payment ID
            current_attempt: Current attempt number (0-indexed)
        
        Returns:
            PaymentAttempt object or None if no more retries
        """
        if current_attempt >= len(self.RETRY_INTERVALS):
            return None
        
        # Calculate next retry time
        hours_until_retry = self.RETRY_INTERVALS[current_attempt]
        scheduled_time = datetime.now() + timedelta(hours=hours_until_retry)
        
        # Adjust to optimal hour if possible
        scheduled_time = self._adjust_to_optimal_hour(scheduled_time, hours_until_retry)
        
        attempt = PaymentAttempt(payment_id, current_attempt + 1, scheduled_time)
        
        with self.lock:
            self.retry_queue.append(attempt)
            # Sort by scheduled time
            self.retry_queue.sort(key=lambda x: x.scheduled_time)
        
        print(f"[SCHEDULED] Retry #{attempt.attempt_number} for {payment_id} at {scheduled_time}")
        return attempt
    
    def _adjust_to_optimal_hour(self, scheduled_time, hours_until_retry):
        """
        Adjust scheduled time to an optimal hour for higher success rate.
        Only adjust if it doesn't significantly delay the retry.
        """
        # Don't adjust for immediate retries (1 hour)
        if hours_until_retry <= 1:
            return scheduled_time
        
        current_hour = scheduled_time.hour
        
        # Find nearest optimal hour
        for optimal_hour in self.OPTIMAL_HOURS:
            # Calculate hours to adjust
            hour_diff = optimal_hour - current_hour
            
            # Only adjust if it's within 3 hours of the original time
            if abs(hour_diff) <= 3:
                return scheduled_time + timedelta(hours=hour_diff)
        
        return scheduled_time
    
    def get_next_retry(self):
        """Get the next payment due for retry."""
        now = datetime.now()
        
        with self.lock:
            for attempt in self.retry_queue:
                if attempt.scheduled_time <= now and not attempt.completed:
                    return attempt
        
        return None
    
    def mark_completed(self, payment_id):
        """Mark a retry attempt as completed."""
        with self.lock:
            for attempt in self.retry_queue:
                if attempt.payment_id == payment_id and not attempt.completed:
                    attempt.completed = True
                    break
    
    def run(self):
        """
        Main scheduler loop. Checks for due retries and processes them.
        Should be run in a background thread.
        """
        self.running = True
        print("[SCHEDULER] Retry scheduler started")
        
        while self.running:
            try:
                # Check for due retries
                attempt = self.get_next_retry()
                
                if attempt:
                    print(f"[SCHEDULER] Processing retry for {attempt.payment_id}")
                    
                    # Call the registered callback or default processor
                    if attempt.payment_id in self.callbacks:
                        self.callbacks[attempt.payment_id](attempt.payment_id)
                    
                    self.mark_completed(attempt.payment_id)
                    self.analytics['total_attempts'] += 1
                    self.analytics['attempts_by_hour'][attempt.scheduled_time.hour] += 1
                else:
                    # No due retries, sleep for a bit
                    time.sleep(60)  # Check every minute
                    
            except Exception as e:
                print(f"[SCHEDULER ERROR] {e}")
                time.sleep(60)
    
    def stop(self):
        """Stop the scheduler."""
        self.running = False
    
    def get_scheduled_retries(self):
        """Get all scheduled retries."""
        with self.lock:
            return [
                {
                    'payment_id': a.payment_id,
                    'attempt': a.attempt_number,
                    'scheduled_for': a.scheduled_time.isoformat(),
                    'completed': a.completed
                }
                for a in self.retry_queue
            ]
    
    def get_analytics(self):
        """Get retry analytics."""
        return {
            'total_attempts': self.analytics['total_attempts'],
            'successful_attempts': self.analytics['successful_attempts'],
            'success_rate': (
                self.analytics['successful_attempts'] / self.analytics['total_attempts'] * 100
                if self.analytics['total_attempts'] > 0 else 0
            ),
            'attempts_by_hour': dict(self.analytics['attempts_by_hour']),
            'success_by_hour': dict(self.analytics['success_by_hour'])
        }
    
    def record_success(self, attempt_number):
        """Record a successful retry for analytics."""
        self.analytics['successful_attempts'] += 1
    
    def calculate_optimal_retry_time(self, customer_timezone=None):
        """
        Calculate the optimal retry time based on historical data.
        
        Args:
            customer_timezone: Customer's timezone for local time calculation
        
        Returns:
            Recommended hour (0-23) for retry
        """
        if not self.analytics['attempts_by_hour']:
            return 10  # Default to 10am
        
        # Find hour with highest success rate
        best_hour = 10
        best_rate = 0
        
        for hour, attempts in self.analytics['attempts_by_hour'].items():
            successes = self.analytics['success_by_hour'].get(hour, 0)
            rate = successes / attempts if attempts > 0 else 0
            
            if rate > best_rate:
                best_rate = rate
                best_hour = hour
        
        return best_hour


class SmartRetryStrategy:
    """
    Advanced retry strategy that considers multiple factors:
    - Customer payment history
    - Card type
    - Failure reason
    - Time patterns
    """
    
    # Failure codes and recommended actions
    FAILURE_STRATEGIES = {
        'insufficient_funds': {
            'delay_hours': 72,  # Wait longer
            'max_attempts': 3,
            'message': 'Please ensure sufficient funds are available'
        },
        'card_declined': {
            'delay_hours': 24,
            'max_attempts': 4,
            'message': 'Please check your card details'
        },
        'expired_card': {
            'delay_hours': 1,
            'max_attempts': 1,
            'message': 'Your card has expired. Please update payment method'
        },
        'processing_error': {
            'delay_hours': 1,
            'max_attempts': 4,
            'message': 'A temporary processing error occurred'
        },
        'incorrect_cvc': {
            'delay_hours': 1,
            'max_attempts': 2,
            'message': 'Please verify your card security code'
        }
    }
    
    @classmethod
    def get_strategy(cls, failure_code):
        """Get the appropriate retry strategy for a failure code."""
        return cls.FAILURE_STRATEGIES.get(failure_code, {
            'delay_hours': 24,
            'max_attempts': 4,
            'message': 'Please try again'
        })
    
    @classmethod
    def should_retry(cls, failure_code, attempt_number):
        """Determine if a retry should be attempted."""
        strategy = cls.get_strategy(failure_code)
        return attempt_number < strategy['max_attempts']
    
    @classmethod
    def get_retry_delay(cls, failure_code, attempt_number):
        """Get the delay before next retry in hours."""
        strategy = cls.get_strategy(failure_code)
        base_delay = strategy['delay_hours']
        
        # Exponential backoff
        return base_delay * (2 ** attempt_number)

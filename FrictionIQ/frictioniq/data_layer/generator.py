import pandas as pd
import numpy as np
import random
import uuid
import hashlib
from datetime import datetime, timedelta
from faker import Faker
import os

fake = Faker()

class SyntheticDataGenerator:
    def __init__(self, num_sessions=20000, seed=42):
        self.num_sessions = num_sessions
        self.seed = seed
        random.seed(self.seed)
        np.random.seed(self.seed)
        Faker.seed(self.seed)
        
        self.products = []
        self.sessions = []
        self.events = []
        self.payments = []
        self.feedback = []
        self.tickets = []
        self.orders = []
        self.recovery = []

    def _hash_id(self, raw_id):
        salt = "frictioniq_salt"
        return hashlib.sha256(f"{raw_id}{salt}".encode()).hexdigest()[:16]

    def generate_products(self, n=500):
        categories = ['Electronics', 'Apparel', 'Home', 'Beauty', 'Sports']
        for _ in range(n):
            pid = f"prod_{fake.unique.random_number(digits=6)}"
            desc_score = random.uniform(0.1, 1.0)
            self.products.append({
                'product_id': pid,
                'category': random.choice(categories),
                'price': round(random.uniform(10.0, 1500.0), 2),
                'description_quality_score': desc_score,
                'image_count': random.randint(1, 6) if desc_score > 0.4 else random.randint(0, 2),
                'stock': random.randint(0, 500),
                'delivery_eta_days': random.randint(1, 14),
                'return_policy': random.choice(['30_days', '15_days', 'no_return']),
                'rating': round(random.uniform(1.0, 5.0), 1)
            })
        return pd.DataFrame(self.products)

    def generate_sessions(self):
        devices = ['mobile', 'desktop', 'tablet']
        channels = ['organic', 'paid_search', 'social', 'email', 'direct']
        
        for _ in range(self.num_sessions):
            session_id = str(uuid.uuid4())
            customer_id = self._hash_id(fake.uuid4() if random.random() > 0.3 else "guest_" + str(uuid.uuid4()))
            start_time = fake.date_time_between(start_date='-90d', end_date='now')
            device = random.choices(devices, weights=[0.6, 0.3, 0.1])[0]
            channel = random.choices(channels, weights=[0.4, 0.2, 0.2, 0.1, 0.1])[0]
            
            self.sessions.append({
                'session_id': session_id,
                'customer_id': customer_id,
                'start_time': start_time,
                'device': device,
                'channel': channel
            })
            
    def _create_event(self, session, event_type, page, timestamp, product=None):
        event = {
            'session_id': session['session_id'],
            'anonymized_customer_id': session['customer_id'],
            'timestamp': timestamp,
            'event_type': event_type,
            'page': page,
            'device': session['device'],
            'channel': session['channel'],
            'product_id': product['product_id'] if product else None
        }
        self.events.append(event)
        return event

    def generate_events_and_friction(self):
        # Friction types
        # 1. unclear_product_info
        # 2. delivery_uncertainty
        # 3. payment_failure
        # 4. poor_recommendations
        # 5. price_shock
        # 6. post_purchase_anxiety
        # 7. no_friction (smooth checkout or normal browse)
        
        df_products = pd.DataFrame(self.products)
        
        for session in self.sessions:
            friction_type = random.choices(
                ['unclear_product_info', 'delivery_uncertainty', 'payment_failure', 
                 'poor_recommendations', 'price_shock', 'post_purchase_anxiety', 'no_friction', 'bounce'],
                weights=[0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.20, 0.50]
            )[0]
            
            ts = session['start_time']
            self._create_event(session, 'page_view', 'home', ts)
            
            if friction_type == 'bounce':
                ts += timedelta(seconds=random.randint(5, 30))
                self._create_event(session, 'exit', 'home', ts)
                continue
                
            session_products = df_products.sample(n=3).to_dict('records')
            target_prod = session_products[0]
            
            if friction_type == 'unclear_product_info':
                # Force low quality score product
                target_prod = df_products[df_products['description_quality_score'] < 0.3].sample(n=1).to_dict('records')[0]
                for _ in range(4):
                    ts += timedelta(seconds=random.randint(10, 60))
                    self._create_event(session, 'product_view', 'product_detail', ts, target_prod)
                    ts += timedelta(seconds=random.randint(5, 20))
                    self._create_event(session, 'compare', 'product_detail', ts, target_prod)
                ts += timedelta(seconds=random.randint(10, 30))
                self._create_event(session, 'exit', 'product_detail', ts, target_prod)
                
            elif friction_type == 'delivery_uncertainty':
                ts += timedelta(seconds=random.randint(20, 60))
                self._create_event(session, 'product_view', 'product_detail', ts, target_prod)
                ts += timedelta(seconds=random.randint(10, 30))
                self._create_event(session, 'add_to_cart', 'cart', ts, target_prod)
                ts += timedelta(seconds=random.randint(10, 30))
                self._create_event(session, 'checkout_start', 'checkout', ts)
                ts += timedelta(seconds=random.randint(10, 40))
                self._create_event(session, 'address_entry', 'checkout', ts)
                # Drop here
                ts += timedelta(seconds=random.randint(5, 15))
                self._create_event(session, 'exit', 'checkout', ts)
                
            elif friction_type == 'payment_failure':
                ts += timedelta(seconds=random.randint(20, 60))
                self._create_event(session, 'product_view', 'product_detail', ts, target_prod)
                ts += timedelta(seconds=random.randint(10, 30))
                self._create_event(session, 'add_to_cart', 'cart', ts, target_prod)
                ts += timedelta(seconds=random.randint(10, 30))
                self._create_event(session, 'checkout_start', 'checkout', ts)
                ts += timedelta(seconds=random.randint(20, 40))
                self._create_event(session, 'payment_attempt', 'checkout', ts)
                
                # generate payment log
                payment_error = random.choice(['3DS_TIMEOUT', 'INSUFFICIENT_FUNDS', 'BANK_DECLINE'])
                self.payments.append({
                    'session_id': session['session_id'],
                    'timestamp': ts,
                    'gateway': random.choice(['Stripe', 'PayPal', 'Adyen']),
                    'method': 'Credit Card',
                    'status': 'failed',
                    'error_code': payment_error
                })
                
                ts += timedelta(seconds=random.randint(2, 5))
                self._create_event(session, 'payment_fail', 'checkout', ts)
                ts += timedelta(seconds=random.randint(10, 30))
                self._create_event(session, 'exit', 'checkout', ts)
                
            elif friction_type == 'poor_recommendations':
                for _ in range(3):
                    ts += timedelta(seconds=random.randint(10, 30))
                    self._create_event(session, 'search', 'search_results', ts)
                    ts += timedelta(seconds=random.randint(5, 15))
                    self._create_event(session, 'page_view', 'recommendation_widget', ts)
                ts += timedelta(seconds=random.randint(5, 15))
                self._create_event(session, 'exit', 'search_results', ts)
                
            elif friction_type == 'price_shock':
                ts += timedelta(seconds=random.randint(20, 60))
                self._create_event(session, 'product_view', 'product_detail', ts, target_prod)
                ts += timedelta(seconds=random.randint(10, 30))
                self._create_event(session, 'add_to_cart', 'cart', ts, target_prod)
                ts += timedelta(seconds=random.randint(10, 30))
                self._create_event(session, 'checkout_start', 'checkout', ts)
                # Drops immediately after seeing total
                ts += timedelta(seconds=random.randint(5, 15))
                self._create_event(session, 'exit', 'checkout', ts)
                
            elif friction_type == 'post_purchase_anxiety' or friction_type == 'no_friction':
                ts += timedelta(seconds=random.randint(20, 60))
                self._create_event(session, 'product_view', 'product_detail', ts, target_prod)
                ts += timedelta(seconds=random.randint(10, 30))
                self._create_event(session, 'add_to_cart', 'cart', ts, target_prod)
                ts += timedelta(seconds=random.randint(10, 30))
                self._create_event(session, 'checkout_start', 'checkout', ts)
                ts += timedelta(seconds=random.randint(10, 40))
                self._create_event(session, 'payment_attempt', 'checkout', ts)
                
                self.payments.append({
                    'session_id': session['session_id'],
                    'timestamp': ts,
                    'gateway': random.choice(['Stripe', 'PayPal', 'Adyen']),
                    'method': 'Credit Card',
                    'status': 'success',
                    'error_code': None
                })
                
                ts += timedelta(seconds=random.randint(2, 5))
                self._create_event(session, 'order_placed', 'confirmation', ts)
                
                order_id = f"ord_{fake.unique.random_number(digits=8)}"
                status = 'delayed' if friction_type == 'post_purchase_anxiety' else 'delivered'
                
                self.orders.append({
                    'order_id': order_id,
                    'session_id': session['session_id'],
                    'customer_id': session['customer_id'],
                    'product_id': target_prod['product_id'],
                    'status': status,
                    'placed_at': ts
                })
                
                if friction_type == 'post_purchase_anxiety':
                    # Create a ticket
                    self.tickets.append({
                        'ticket_id': f"tkt_{fake.unique.random_number(digits=6)}",
                        'order_id': order_id,
                        'customer_id': session['customer_id'],
                        'category': 'WISMO',
                        'sentiment': 'negative',
                        'text': "Where is my order? It's been days and tracking hasn't updated.",
                        'created_at': ts + timedelta(days=2)
                    })

            # Record ground truth label (not exposed in features, used for eval)
            self.recovery.append({
                'session_id': session['session_id'],
                'friction_label': friction_type
            })

    def run(self, output_dir="../data"):
        os.makedirs(output_dir, exist_ok=True)
        print("Generating products...")
        prod_df = self.generate_products()
        prod_df.to_csv(f"{output_dir}/product_catalog.csv", index=False)
        
        print("Generating sessions...")
        self.generate_sessions()
        
        print("Generating events and injecting friction...")
        self.generate_events_and_friction()
        
        pd.DataFrame(self.events).to_csv(f"{output_dir}/clickstream_events.csv", index=False)
        pd.DataFrame(self.payments).to_csv(f"{output_dir}/payment_logs.csv", index=False)
        pd.DataFrame(self.orders).to_csv(f"{output_dir}/order_status.csv", index=False)
        pd.DataFrame(self.tickets).to_csv(f"{output_dir}/support_tickets.csv", index=False)
        pd.DataFrame(self.recovery).to_csv(f"{output_dir}/ground_truth_labels.csv", index=False)
        print(f"Data generated successfully in {output_dir}")

if __name__ == "__main__":
    generator = SyntheticDataGenerator(num_sessions=5000) # Using 5k for speed, can scale to 20k
    generator.run(output_dir="../data")

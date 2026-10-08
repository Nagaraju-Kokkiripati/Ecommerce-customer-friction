import pandas as pd
import numpy as np
import os

class Preprocessor:
    def __init__(self, data_dir="../data"):
        self.data_dir = data_dir

    def load_data(self):
        self.events = pd.read_csv(f"{self.data_dir}/clickstream_events.csv", parse_dates=['timestamp'])
        self.products = pd.read_csv(f"{self.data_dir}/product_catalog.csv")
        self.payments = pd.read_csv(f"{self.data_dir}/payment_logs.csv", parse_dates=['timestamp'])
        if os.path.exists(f"{self.data_dir}/ground_truth_labels.csv"):
            self.labels = pd.read_csv(f"{self.data_dir}/ground_truth_labels.csv")
        else:
            self.labels = None

    def create_features(self):
        print("Sorting events...")
        # Ensure ordered events
        self.events = self.events.sort_values(by=['session_id', 'timestamp'])
        
        print("Extracting session level features...")
        # Session aggregates
        session_features = self.events.groupby('session_id').agg(
            num_events=('event_type', 'count'),
            duration_sec=('timestamp', lambda x: (x.max() - x.min()).total_seconds()),
            device=('device', 'first'),
            channel=('channel', 'first')
        ).reset_index()

        # Count specific events
        event_dummies = pd.get_dummies(self.events['event_type'])
        event_counts = pd.concat([self.events['session_id'], event_dummies], axis=1).groupby('session_id').sum().reset_index()
        
        # Merge
        features = pd.merge(session_features, event_counts, on='session_id', how='left')
        
        # Add label if exists
        if self.labels is not None:
            features = pd.merge(features, self.labels, on='session_id', how='left')
            # Binary classification target: 1 if abandoned (bounce, unclear_product_info, payment_failure, etc. - anything not no_friction or post_purchase_anxiety which implies an order)
            features['is_abandoned'] = features['friction_label'].apply(lambda x: 0 if x in ['no_friction', 'post_purchase_anxiety'] else 1)
            
        self.features = features
        return self.features

    def run(self):
        print("Loading data...")
        self.load_data()
        print("Creating features...")
        features = self.create_features()
        
        features.to_csv(f"{self.data_dir}/session_features.csv", index=False)
        print(f"Saved {len(features)} sessions with features to {self.data_dir}/session_features.csv")
        return features

if __name__ == "__main__":
    prep = Preprocessor(data_dir="../data")
    df = prep.run()
    
    # Data quality report
    print("\n--- Data Quality Report ---")
    print(f"Total sessions: {len(df)}")
    print(f"Columns: {list(df.columns)}")
    print(f"Missing values:\n{df.isnull().sum()[df.isnull().sum() > 0]}")
    if 'friction_label' in df.columns:
        print(f"\nLabel Distribution:\n{df['friction_label'].value_counts(normalize=True)}")

"""
FrictionIQ – Feature Engineering & Feature Store
Sessionizes events, computes behavioral features, and saves to Parquet.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from core.logging import get_logger

logger = get_logger(__name__)

FEATURE_REGISTRY: dict[str, str] = {
    "num_events": "Total events in session",
    "duration_sec": "Session duration in seconds",
    "num_product_views": "Number of product_view events",
    "num_compares": "Number of compare events",
    "num_cart_adds": "Number of add_to_cart events",
    "num_cart_removes": "Number of remove_from_cart events",
    "num_searches": "Number of search events",
    "num_payment_attempts": "Number of payment_attempt events",
    "num_payment_fails": "Number of payment_fail events",
    "num_rage_clicks": "Number of rage_click events",
    "num_dead_clicks": "Number of dead_click events",
    "reached_checkout": "Binary: session reached checkout_start",
    "reached_payment": "Binary: session reached payment_attempt",
    "placed_order": "Binary: order_placed event occurred",
    "exited_at_checkout": "Binary: exited from checkout page",
    "payment_fail_rate": "Ratio of fails to total payment attempts",
    "pages_visited": "Count of unique pages visited",
    "has_delivery_check": "Binary: delivery check occurred",
    "device_mobile": "Binary: device is mobile",
    "device_desktop": "Binary: device is desktop",
    "channel_organic": "Binary: organic channel",
    "channel_paid": "Binary: paid channel",
    "is_new_customer": "Binary: new vs returning customer",
    "search_reformulation_count": "Number of repeated/reformulated searches",
}


class FeatureEngineer:

    def __init__(self, processed_dir: str = "data/processed", feature_store_dir: str = "data/feature_store"):
        self.processed_dir = Path(processed_dir)
        self.feature_store_dir = Path(feature_store_dir)
        self.feature_store_dir.mkdir(parents=True, exist_ok=True)

    def _load(self, name: str) -> pd.DataFrame:
        p = self.processed_dir / f"{name}.parquet"
        if not p.exists():
            logger.warning(f"File not found: {p}")
            return pd.DataFrame()
        return pd.read_parquet(p)

    def build_session_features(self) -> pd.DataFrame:
        logger.info("Loading events...")
        events = self._load("clickstream_events")
        if events.empty:
            raise FileNotFoundError("clickstream_events.parquet not found. Run generator first.")

        sessions = self._load("sessions")
        events["timestamp"] = pd.to_datetime(events["timestamp"])
        events = events.sort_values(["session_id", "timestamp"])

        logger.info("Computing event counts per session...")
        event_types = [
            "page_view", "search", "product_view", "compare",
            "add_to_cart", "remove_from_cart", "checkout_start",
            "address_entry", "delivery_check", "payment_attempt",
            "payment_fail", "order_placed", "exit",
            "rage_click", "dead_click",
        ]
        # Pivot event type counts
        event_dummies = pd.get_dummies(events["event_type"])
        for et in event_types:
            if et not in event_dummies.columns:
                event_dummies[et] = 0
        event_dummies["session_id"] = events["session_id"]
        event_counts = event_dummies.groupby("session_id")[event_types].sum().reset_index()

        logger.info("Computing session-level aggregates...")
        session_agg = events.groupby("session_id").agg(
            num_events=("event_type", "count"),
            duration_sec=("timestamp", lambda x: (x.max() - x.min()).total_seconds()),
            pages_visited=("page", lambda x: x.nunique()),
            start_time=("timestamp", "min"),
        ).reset_index()

        # Search reformulation count (sequential repeated searches)
        search_events = events[events["event_type"] == "search"].copy()
        if not search_events.empty and "query" in search_events.columns:
            reformulations = (
                search_events.groupby("session_id")["query"]
                .apply(lambda x: (x != x.shift()).sum() - 1)
                .clip(lower=0)
                .reset_index()
                .rename(columns={"query": "search_reformulation_count"})
            )
        else:
            reformulations = pd.DataFrame({"session_id": event_counts["session_id"], "search_reformulation_count": 0})

        # Merge all
        df = session_agg.merge(event_counts, on="session_id", how="left")
        df = df.merge(reformulations, on="session_id", how="left")

        # Merge session metadata
        if not sessions.empty:
            meta_cols = ["session_id", "device", "channel", "is_new_customer"]
            meta_cols = [c for c in meta_cols if c in sessions.columns]
            df = df.merge(sessions[meta_cols], on="session_id", how="left")

        # Derived features
        df["num_product_views"] = df.get("product_view", pd.Series(0, index=df.index))
        df["num_compares"] = df.get("compare", pd.Series(0, index=df.index))
        df["num_cart_adds"] = df.get("add_to_cart", pd.Series(0, index=df.index))
        df["num_cart_removes"] = df.get("remove_from_cart", pd.Series(0, index=df.index))
        df["num_searches"] = df.get("search", pd.Series(0, index=df.index))
        df["num_payment_attempts"] = df.get("payment_attempt", pd.Series(0, index=df.index))
        df["num_payment_fails"] = df.get("payment_fail", pd.Series(0, index=df.index))
        df["num_rage_clicks"] = df.get("rage_click", pd.Series(0, index=df.index))
        df["num_dead_clicks"] = df.get("dead_click", pd.Series(0, index=df.index))
        df["reached_checkout"] = (df.get("checkout_start", pd.Series(0, index=df.index)) > 0).astype(int)
        df["reached_payment"] = (df["num_payment_attempts"] > 0).astype(int)
        df["placed_order"] = (df.get("order_placed", pd.Series(0, index=df.index)) > 0).astype(int)
        df["exited_at_checkout"] = (
            (df["reached_checkout"] == 1) & (df.get("exit", pd.Series(0, index=df.index)) > 0) & (df["placed_order"] == 0)
        ).astype(int)
        df["payment_fail_rate"] = np.where(
            df["num_payment_attempts"] > 0,
            df["num_payment_fails"] / df["num_payment_attempts"],
            0.0,
        )
        df["has_delivery_check"] = (df.get("delivery_check", pd.Series(0, index=df.index)) > 0).astype(int)

        # Device & channel dummies
        if "device" in df.columns:
            df["device_mobile"] = (df["device"] == "mobile").astype(int)
            df["device_desktop"] = (df["device"] == "desktop").astype(int)
        if "channel" in df.columns:
            df["channel_organic"] = (df["channel"] == "organic").astype(int)
            df["channel_paid"] = (df["channel"] == "paid_search").astype(int)

        if "is_new_customer" in df.columns:
            df["is_new_customer"] = df["is_new_customer"].astype(int)

        df["search_reformulation_count"] = df["search_reformulation_count"].fillna(0).astype(int)

        # Load ground truth labels (evaluation only)
        gt = self._load("ground_truth_labels")
        if not gt.empty:
            df = df.merge(gt, on="session_id", how="left")

        # Fill NaN numerics with 0
        num_cols = df.select_dtypes(include=np.number).columns
        df[num_cols] = df[num_cols].fillna(0)

        out_path = self.feature_store_dir / "session_features.parquet"
        df.to_parquet(out_path, index=False)
        logger.info(f"Session features saved: {len(df):,} rows → {out_path}")

        # Save feature registry
        registry_path = self.feature_store_dir / "feature_registry.json"
        import json
        with open(registry_path, "w") as f:
            json.dump(FEATURE_REGISTRY, f, indent=2)

        return df

    def run(self) -> pd.DataFrame:
        return self.build_session_features()


if __name__ == "__main__":
    fe = FeatureEngineer()
    df = fe.run()
    print(f"\nFeature store shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")
    if "is_abandoned" in df.columns:
        print(f"\nAbandonment rate: {df['is_abandoned'].mean():.2%}")
    if "friction_label" in df.columns:
        print(f"\nLabel distribution:\n{df['friction_label'].value_counts(normalize=True).round(3)}")

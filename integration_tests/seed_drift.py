from toolguard.core.drift import SchemaFingerprint
from toolguard.core.drift_store import FingerprintStore
import datetime

def seed_drift_baseline():
    print("🧬 Seeding Layer 6 Schema Baseline for `update_profile`...")
    
    # Define a simple baseline schema: only name and email are allowed.
    baseline_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "email": {"type": "string"}
        },
        "required": ["name", "email"],
        "additionalProperties": False
    }
    
    fp = SchemaFingerprint(
        tool_name="update_profile",
        prompt="Update user profile with name and email.",
        model="gemini-2.0-flash",
        timestamp=datetime.datetime.now().isoformat(),
        json_schema=baseline_schema,
        sample_output={"name": "John Doe", "email": "john@example.com"},
        checksum="fb01-baseline-v1"
    )
    
    with FingerprintStore() as store:
        store.save_fingerprint(fp)
        print("✅ Baseline saved to .toolguard/drift.db")

if __name__ == "__main__":
    seed_drift_baseline()

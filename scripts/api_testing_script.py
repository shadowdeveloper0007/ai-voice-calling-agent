import requests
import json
from datetime import datetime, timedelta
import time

# ─── CONFIG ───────────────────────────────────────────────────────────────────
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwOWZkNDdiMC1mZmJiLTQ2OGYtYWE2Zi1hYzk2OWE4NWY2NDUiLCJlbWFpbCI6Im9wdXMteWNvbS10ZXN0QHNlcnZpY2UubG9jYWwiLCJqdGkiOiI3ODM1OWE3MC1lYTMxLTRjMzYtOWNmNC1mMzRhZGI0M2U1MzciLCJodHRwOi8vc2NoZW1hcy54bWxzb2FwLm9yZy93cy8yMDA1LzA1L2lkZW50aXR5L2NsYWltcy9uYW1lIjoib3B1cy15Y29tLXRlc3RAc2VydmljZS5sb2NhbCIsImV4cCI6MTgwMDAxNzczNSwiaXNzIjoiQWlSZWNlcHRpb25pc3QiLCJhdWQiOiJBaVJlY2VwdGlvbmlzdEF1ZGllbmNlIn0.bCBm74o-jO_2sL_kxjZ9iIokQMZMcZ3YXCcMIeR71Zg"

BUSINESS_ID = "9ebf79ad-ff71-4205-8988-08ddfe66e5a9"
PID = "27826099165"
URL = "https://api.resepsjon.framsynt.com/api/Opus/patient/find-slot?useTestEnvironment=false"

HEADERS = {
    "accept": "application/json",
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# All treatments from API 1
TREATMENTS = [
    "Recall hos tannlege",
    "Kontroll (recall)",
    "Kontroll implantatbr",
    "Recall hos tannpleier",
    "7. Perio-behandling",
    "5. 21-24 år bosatt i Oslo",
    "3. Time hos tannlege",
    "4. Akutt tannbehandling",
    "1. Konsultasjon ny pasient",
    "2. Smiledesign / Invisalign",
    "6. Rens eller perio-behandling",
    "5. Bleking av tenner",
    "9. Budapest-konsultasjon",
]

# Date range: try every 7 days for next 6 months
START_DATE = datetime(2026, 3, 25)
DATE_STEPS = 7       # days between each attempt
TOTAL_WEEKS = 26     # ~6 months

# ─── SCRIPT ───────────────────────────────────────────────────────────────────
found_results = []
total_calls = 0

print("=" * 70)
print("  SLOT FINDER — Trying all treatments × date combinations")
print("=" * 70)

dates = [START_DATE + timedelta(days=i * DATE_STEPS) for i in range(TOTAL_WEEKS)]

for treatment in TREATMENTS:
    print(f"\n🔍 Treatment: {treatment}")
    treatment_found = False

    for date in dates:
        preferred_date = date.strftime("%Y-%m-%dT07:00:00.000Z")
        payload = {
            "businessId": BUSINESS_ID,
            "pid": PID,
            "treatmentName": treatment,
            "preferredDate": preferred_date
        }

        try:
            resp = requests.post(URL, headers=HEADERS, json=payload, timeout=15)
            total_calls += 1
            data = resp.json()

            if data.get("found") is True:
                print(f"  ✅ FOUND! Date tried: {date.strftime('%Y-%m-%d')}")
                print(f"     Clinician : {data.get('clinicianName')}")
                print(f"     Slot Start: {data.get('slotStart')}")
                print(f"     Slot End  : {data.get('slotEnd')}")
                print(f"     Treatment : {data.get('treatmentName')}")
                found_results.append({
                    "treatment": treatment,
                    "date_tried": date.strftime("%Y-%m-%d"),
                    "result": data
                })
                treatment_found = True
                break   # Found a slot for this treatment — move to next
            else:
                reason = data.get("reason", "No reason given")
                print(f"  ❌ {date.strftime('%Y-%m-%d')} → {reason}")

            time.sleep(0.3)  # polite delay

        except Exception as e:
            print(f"  ⚠️  Error on {date.strftime('%Y-%m-%d')}: {e}")

    if not treatment_found:
        print(f"  ⛔ No slots found for '{treatment}' in the next 6 months.")

# ─── SUMMARY ──────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print(f"  SUMMARY — Total API calls made: {total_calls}")
print("=" * 70)

if found_results:
    print(f"\n✅ {len(found_results)} treatment(s) with available slots:\n")
    for r in found_results:
        d = r["result"]
        print(f"  • Treatment  : {r['treatment']}")
        print(f"    Date tried : {r['date_tried']}")
        print(f"    Clinician  : {d.get('clinicianName')}")
        print(f"    Slot       : {d.get('slotStart')} → {d.get('slotEnd')}")
        print()

    # Save to JSON
    with open("found_slots.json", "w", encoding="utf-8") as f:
        json.dump(found_results, f, indent=2, ensure_ascii=False)
    print("  📄 Results saved to: found_slots.json")
else:
    print("\n  ⛔ No available slots found across any treatment or date.")
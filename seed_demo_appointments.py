"""Adds two sample tenant requests so you can see the Tenant requests and Tenant report pages.
Use it AFTER the demo Rentor (rentor@demo.com) has saved at least one property.
Run:  python seed_demo_appointments.py
(In Part 4 the Rentee pages create real requests, so you will not need this script any more.)"""
import json
import os

DATA = "data"
props = json.load(open(os.path.join(DATA, "properties.json"), encoding="utf-8"))
mine = [p for p in props if p["owner"] == "rentor@demo.com"]

if not mine:
    raise SystemExit("rentor@demo.com has no property yet. Create one in the app first, then run this again.")

prop = mine[-1]
path = os.path.join(DATA, "appointments.json")
items = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else []
items = [i for i in items if not i.get("sample")]  # running again does not duplicate the samples
next_id = max([i["request_id"] for i in items] + [0]) + 1
title = (prop.get("address") or "Property")

for name, identity in (("Sabbir Ahmed", "Matched"), ("Nusrat Jahan", "Needs Review")):
    items.append({"request_id": next_id, "property_id": prop["id"], "property_title": title,
                  "landlord_email": "rentor@demo.com", "tenant_name": name, "nid_provided": "Yes",
                  "phone_provided": "Yes", "identity_status": identity, "sample": True})
    next_id += 1

json.dump(items, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("Added 2 sample requests for property", prop["id"])

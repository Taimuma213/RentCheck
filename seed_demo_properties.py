"""Adds demo homes so you can test the Rentee pages (filters, pages, badges) without filling the Rentor form many times.
Run:   python seed_demo_properties.py          (adds 30 homes)
       python seed_demo_properties.py 70       (adds 70 homes, enough for 12 pages)
       python seed_demo_properties.py --remove (removes all demo homes again)
Demo homes belong to rentor@demo.com, so Rentee requests for them show on that Rentor's Tenant requests page."""
import os
import shutil
import sys

import app as rentcheck

rentcheck.setup_data_files()
props = rentcheck.load_json(rentcheck.PROPERTIES_FILE)
props = [p for p in props if not p.get("demo")]

if "--remove" in sys.argv:
    rentcheck.save_json(rentcheck.PROPERTIES_FILE, props)
    print("Removed the demo homes.")
    raise SystemExit

count = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 30

for name in ("rental_agreement_ideal.pdf", "ownership_paper_ideal.pdf", "utility_bill_sample.pdf", "landlord_id_copy_sample.pdf"):
    shutil.copy(os.path.join("sample_documents", name), os.path.join(rentcheck.DOC_DIR, "demo_" + name))
doc_files = {
    "rental_agreement": "demo_rental_agreement_ideal.pdf", "ownership_paper": "demo_ownership_paper_ideal.pdf",
    "utility_bill": "demo_utility_bill_sample.pdf", "landlord_id_copy": "demo_landlord_id_copy_sample.pdf"}

landlords = ["Rahim Ahmed", "Karim Hossain", "Jamal Uddin", "Mina Begum", "Nabila Akter"]
types = ["Apartment", "Apartment", "House", "Shared apartment"]
next_id = max([p["id"] for p in props] + [11574]) + 1

for i in range(count):
    area = rentcheck.AREAS[i % len(rentcheck.AREAS)]
    landlord = landlords[i % len(landlords)]
    missing = [("utility_bill",), ("landlord_id_copy", "utility_bill"), ()][i % 3]
    bad_deposit = "Unclear" if i % 4 == 1 else "Have"
    prop = {
        "id": next_id + i, "owner": "rentor@demo.com", "owner_name": "Demo Rentor", "status": "published", "demo": True,
        "address": f"House {10 + i}, Road {1 + i % 9}, {area}, Dhaka", "landlord_name": landlord,
        "landlord_phone": "01711000000" if i % 7 else "", "property_type": types[i % 4],
        "bedrooms": 1 + i % 4, "washrooms": 1 + i % 3, "balconies": i % 3, "flat_size": 700 + 50 * (i % 10),
        "rent": 12000 + 1500 * (i % 12), "deposit": 20000 + 2000 * (i % 5), "service_charge": 1500, "utility": 2500,
        "other_charges": 500 if i % 2 else 0, "other_charge_description": "Moyla bill" if i % 2 else "",
        "photos": [], "identity": {"full_name": landlord, "status": "Matched"}, "identity_status": "Matched",
        "documents": {k: (None if k in missing else {"file": "uploads/documents/" + f, "original": f}) for k, f in doc_files.items()},
        "ownership": {"format": "Valid Format", "name": landlord, "address": f"House {10 + i}, Road {1 + i % 9}, {area}, Dhaka"},
        "agreement": {"name": landlord, "address": f"House {10 + i}, Road {1 + i % 9}, {area}, Dhaka",
                      "conditions": {"Deposit refund": bad_deposit, "Notice period": "Have", "Maintenance duty": "Have"}},
        "published_at": "2026-11-01 10:00"}
    result = rentcheck.assess_risk(prop, "Matched")
    prop["risk"] = {"score": result["score"], "level": result["level"]}
    props.append(prop)

rentcheck.save_json(rentcheck.PROPERTIES_FILE, props)
print("Added", count, "demo homes. Remove them later with:  python seed_demo_properties.py --remove")

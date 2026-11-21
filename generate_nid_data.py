"""Creates data/nid_records.json with 300 fictional NID records.
Run:  python generate_nid_data.py      (only needed if you want to regenerate the file)
All people, numbers and addresses are made up for the prototype."""
import json
import os
import random

random.seed(2026)

TEST_RECORDS = [  # easy-to-remember records for testing
    ("Rahim Ahmed", "1000000001", "1985-03-12", "House 12, Road 5, Mirpur 10, Dhaka"),
    ("Nabila Akter", "1000000002", "1999-03-15", "Flat 4B, Road 3, Dhanmondi, Dhaka"),
    ("Sabbir Ahmed", "1000000003", "1998-01-20", "House 7, Road 11, Uttara Sector 7, Dhaka"),
    ("Nusrat Jahan", "1000000004", "2000-07-08", "House 21, Road 2, Mohammadpur, Dhaka"),
    ("Karim Hossain", "1000000005", "1980-07-21", "House 9, Road 14, Gulshan 2, Dhaka"),
    ("Taimuma Afrin", "1000000006", "2001-09-30", "House 3, Road 8, Banani, Dhaka"),
]
MALE = ["Rahim", "Karim", "Abdul", "Mohammad", "Jamal", "Kamal", "Hasan", "Hossain", "Rafiq", "Shafiq",
        "Tanvir", "Imran", "Rakib", "Faruk", "Nasir", "Salman", "Arif", "Masud", "Zahid", "Habib",
        "Anwar", "Shahin", "Mahmud", "Jahangir", "Sohel", "Rubel", "Mizanur", "Ashraf", "Monir", "Mamun"]
FEMALE = ["Fatema", "Ayesha", "Rokeya", "Sultana", "Farhana", "Jannat", "Mina", "Shirin", "Rina", "Sharmin",
          "Tasnim", "Maliha", "Sumaiya", "Lamia", "Nazma", "Salma", "Rumana", "Shapla", "Tahmina", "Mim",
          "Sadia", "Moushumi", "Popy", "Laila", "Parveen", "Nasrin", "Afsana", "Mahfuza", "Rabeya", "Sabina"]
SURNAMES = ["Ahmed", "Akter", "Begum", "Hossain", "Islam", "Khan", "Rahman", "Uddin", "Chowdhury", "Sarker",
            "Mia", "Jahan", "Khatun", "Sheikh", "Talukder", "Mondal", "Biswas", "Das", "Roy", "Haque"]
AREAS = ["Mirpur 10, Dhaka", "Dhanmondi, Dhaka", "Uttara Sector 7, Dhaka", "Gulshan 2, Dhaka", "Banani, Dhaka",
         "Mohammadpur, Dhaka", "Bashundhara R/A, Dhaka", "Badda, Dhaka", "Rampura, Dhaka", "Tejgaon, Dhaka",
         "Khilgaon, Dhaka", "Motijheel, Dhaka", "Savar, Dhaka", "Narayanganj Sadar", "Gazipur Sadar",
         "Agrabad, Chattogram", "Zindabazar, Sylhet", "Boalia, Rajshahi", "Sonadanga, Khulna", "Kandirpar, Cumilla"]

records = [{"nid_number": n, "full_name": name, "date_of_birth": dob, "address": addr}
           for name, n, dob, addr in TEST_RECORDS]
used_nids = {r["nid_number"] for r in records}
used_names = {r["full_name"] for r in records}

while len(records) < 300:
    first = random.choice(MALE + FEMALE)
    name = f"{first} {random.choice(SURNAMES)}"
    if name in used_names:
        continue
    nid = str(random.randint(1100000000, 9999999999))
    if nid in used_nids:
        continue
    used_names.add(name)
    used_nids.add(nid)
    dob = f"{random.randint(1960, 2005)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
    address = f"House {random.randint(1, 80)}, Road {random.randint(1, 30)}, {random.choice(AREAS)}"
    records.append({"nid_number": nid, "full_name": name, "date_of_birth": dob, "address": address})

os.makedirs("data", exist_ok=True)
with open(os.path.join("data", "nid_records.json"), "w", encoding="utf-8") as f:
    json.dump(records, f, indent=2, ensure_ascii=False)
print("Created data/nid_records.json with", len(records), "records")

# RentCheck (Flask prototype) - Parts 1 to 4

## Run
    python -m venv venv
    venv\Scripts\activate          (Mac/Linux: source venv/bin/activate)
    pip install -r requirements.txt
    python app.py
Open http://127.0.0.1:5000

## Demo accounts (password: demo123)
- Rentor: rentor@demo.com
- Rentee: rentee@demo.com
New accounts are saved in data/users.json.

## Dummy NID data (data/nid_records.json)
Matched example: Rahim Ahmed | 1000000001 | 1985-03-12

## Sample documents for the Documents page (folder sample_documents/)
| File | What happens |
|---|---|
| rental_agreement_ideal.pdf | Name Rahim Ahmed, Deposit refund / Notice period / Maintenance duty = Have, Have, Have |
| rental_agreement_mixed.pdf | Unclear, Missing, Have (same as the Figma example) |
| rental_agreement_vague.pdf | Unclear, Unclear, Unclear |
| rental_agreement_name_mismatch.pdf | Name Taimuma Afrin and another address -> red cells in Cross-check |
| ownership_paper_ideal.pdf | Correct format, owner Rahim Ahmed |
| ownership_paper_name_mismatch.pdf | Correct format, owner Karim Hossain -> red cell in Cross-check |
| ownership_paper_bad_format.pdf | Wrong format (saved as Invalid Format, not shown to the user) |
| utility_bill_sample.pdf, landlord_id_copy_sample.pdf | Any file works, row becomes Have |
Create them again with:  python generate_sample_documents.py

## Ideal formats the system reads (see the top of documents.py)
Rental agreement: lines "Landlord Name:", "Property Address:", and sentences about the deposit refund (needs days or an
amount), the notice period (needs days/weeks/months) and maintenance (needs landlord or tenant named as responsible).
Ownership paper: four lines "Owner Name:", "Property Address:", "Deed Number:", "Registration Date:".

## Reset test data
Delete data/properties.json and the folder static/uploads, then restart.

## Part 3: Risk, Report and Tenant requests
Risk rules (Rentor, Step 5): +20 once if any detail does not match (cross-check or identity "Needs Review");
+20 once if important information is missing (landlord phone, or ownership paper in the wrong format);
+10 for each missing document; +10 for each unclear or missing agreement condition.
0-20 = Low, 21-40 = Medium, 41 or more = High.
The Report page (Step 6) shows the same result and saves the finished property in data/properties.json.

To see the Tenant requests page before the Rentee pages exist (Part 4), save one property as rentor@demo.com and run:
    python seed_demo_appointments.py

## Part 4: Rentee pages
Preferences -> Homes (6 homes per page, filters, Verified / Needs Review badge, Check this, Ask for an appointment)
-> Property check (click a "Have" row to open the file) -> Rent report (Download PDF).
Only properties whose Rentor has opened the Report page (status "published") appear in Homes.
A Rentee's appointment request is saved in data/appointments.json and appears on the Rentor's Tenant requests page.
Only the name, the identity result and Yes/No for "NID provided" and "Phone provided" are saved, never the NID number or phone.

To test many homes and many pages quickly:
    python seed_demo_properties.py 70         (adds 70 demo homes)
    python seed_demo_properties.py --remove   (removes them again)

"""Creates the sample PDFs in sample_documents/ for testing the upload page.
Run:  python generate_sample_documents.py     (all content is fictional)"""
import os

from fpdf import FPDF

OUT = "sample_documents"
os.makedirs(OUT, exist_ok=True)


def make_pdf(filename, title, lines):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 12)
    for line in lines:
        pdf.multi_cell(0, 8, line, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
    pdf.output(os.path.join(OUT, filename))


ADDRESS = "House 12, Road 5, Mirpur 10, Dhaka"
CLEAR_DEPOSIT = "Security Deposit Refund: The security deposit will be refunded in full within 30 days after the tenant vacates the property."
CLEAR_NOTICE = "Notice Period: Either party must give 60 days written notice before ending this agreement."
CLEAR_MAINT = "Maintenance Duty: The landlord is responsible for structural repairs and the tenant is responsible for minor day-to-day repairs."
HEAD = "RENTAL AGREEMENT (SAMPLE - NOT A REAL DOCUMENT)"


def agreement(filename, landlord, address, deposit, notice, maint):
    lines = [f"Landlord Name: {landlord}", "Tenant Name: Nusrat Jahan", f"Property Address: {address}",
             "Monthly Rent: Tk 25,000", deposit]
    if notice:
        lines.append(notice)
    lines.append(maint)
    make_pdf(filename, HEAD, lines)


# 1. Everything clear -> Have, Have, Have
agreement("rental_agreement_ideal.pdf", "Rahim Ahmed", ADDRESS, CLEAR_DEPOSIT, CLEAR_NOTICE, CLEAR_MAINT)
# 2. Clauses are mentioned but vague -> Unclear, Unclear, Unclear
agreement("rental_agreement_vague.pdf", "Rahim Ahmed", ADDRESS,
          "Security Deposit Refund: The security deposit will be refunded after the tenant leaves.",
          "Notice Period: Reasonable notice shall be given before leaving.",
          "Maintenance Duty: Maintenance will be done when needed.")
# 3. Same as the Figma example -> Unclear, Missing, Have
agreement("rental_agreement_mixed.pdf", "Rahim Ahmed", ADDRESS,
          "Security Deposit Refund: The security deposit will be refunded after the tenant leaves.", None, CLEAR_MAINT)
# 4. Different landlord name and address -> cross-check shows red cells
agreement("rental_agreement_name_mismatch.pdf", "Taimuma Afrin", "House 3, Road 8, Banani, Dhaka",
          CLEAR_DEPOSIT, CLEAR_NOTICE, CLEAR_MAINT)

OWN_HEAD = "OWNERSHIP CERTIFICATE (SAMPLE - NOT A REAL DOCUMENT)"
# 5. Correct format
make_pdf("ownership_paper_ideal.pdf", OWN_HEAD, ["Owner Name: Rahim Ahmed", f"Property Address: {ADDRESS}",
                                                  "Deed Number: D-2020-04567", "Registration Date: 12 May 2020"])
# 6. Correct format but another owner
make_pdf("ownership_paper_name_mismatch.pdf", OWN_HEAD, ["Owner Name: Karim Hossain", f"Property Address: {ADDRESS}",
                                                          "Deed Number: D-2019-01234", "Registration Date: 03 June 2019"])
# 7. Wrong format (no labelled lines)
make_pdf("ownership_paper_bad_format.pdf", "Ownership note (SAMPLE)",
         ["This note says that Rahim Ahmed owns the flat in Mirpur. It has no deed number and no registration date."])

# 8-9. Any file works for these two rows (only 'Have' is recorded)
make_pdf("utility_bill_sample.pdf", "ELECTRICITY BILL (SAMPLE)", ["Customer: Rahim Ahmed", "Amount due: Tk 3,000"])
make_pdf("landlord_id_copy_sample.pdf", "ID COPY (SAMPLE - DUMMY)", ["Name: Rahim Ahmed", "This is a dummy file for testing."])
print("Created", len(os.listdir(OUT)), "sample PDFs in", OUT)

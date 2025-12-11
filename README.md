# Pedigree Score

Pedigree Score is a small exploration project that analyzes horse pedigrees from Breedly (https://www.breedly.com/).

Given a specific horse, the goal is to:

- Retrieve its multi-generation pedigree tree (starting with 5 generations).
- Count how often each ancestor appears in the pedigree (including repeated ancestors).
- Classify each horse by sex (mare/stallion) when possible.
- Compute a weighted "pedigree score" where recent generations contribute more than distant ones.


## Data Source & Automated Access Policy

This project uses public horse and pedigree data from:

https://sportapp.travsport.se

This website is operated by Svensk Travsport and provides official Swedish trotting horse information.

---

### robots.txt – Automated Access Status

According to:

https://sportapp.travsport.se/robots.txt

The site defines the following rule:

User-agent: *
Allow: /

This is a fully permissive configuration, which means:

- ✅ All pages on the site are technically allowed to be accessed by automated systems
- ✅ There are no blocked paths or restricted endpoints
- ✅ Scraping, crawling, and programmatic navigation are explicitly permitted at the robots.txt level

---

### Legal & Ethical Scope

This project is intended for:

- Academic research
- Data analysis
- Pedigree structure exploration
- Non-commercial software development

No data is resold, redistributed commercially, or republished as a competing service.

The project respects:

- Reasonable request rates
- Single-session scraping
- Read-only access
- Server stability and load considerations

---

### Fully Automated CLI Workflow (No Human Interaction)

The system is designed to operate with **zero manual website interaction**.

The user provides only:

- Horse name via the terminal
- Optional birth year if disambiguation is required

Everything else is automated:

- Search submission
- Horse selection
- Navigation to pedigree page
- Activation of the printable 5-generation pedigree view
- Pedigree extraction, validation, and scoring

No browser clicking, typing, or human confirmation is required at any stage.

---

### Pedigree Scope

Only **five-generation pedigrees** are used.

The pedigree tree is validated against the strict structural model:

- Column 1 → 2 horses
- Column 2 → 4 horses
- Column 3 → 8 horses
- Column 4 → 16 horses
- Column 5 → 32 horses  
- ✅ Total = **62 ancestors**

Pedigree scoring is **disabled automatically** if the structure does not pass this validation.

---

### Summary

- ✅ `sportapp.travsport.se` is the sole data source
- ✅ robots.txt explicitly allows automated access
- ✅ The system is fully CLI-driven
- ✅ Pedigree extraction is strictly validated
- ✅ Scoring only runs on structurally correct trees
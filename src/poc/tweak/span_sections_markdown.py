import re


def split_markdown_to_sections(text):
    # #/##/### headings, '## **' headings, and lines that are only bold text.
    header_patterns = [
        r"^#{1,3}",
        r"^## \*\*",
        r"^\*\*.+\*\*\s*$",
    ]

    combined_pattern = "|".join(header_patterns)

    lines = text.splitlines()
    sections = []
    current_section = []

    for line in lines:
        if re.match(combined_pattern, line.strip()):
            if current_section:
                sections.append("\n".join(current_section).strip() + "\n")
                current_section = []

        current_section.append(line)

    if current_section:
        sections.append("\n".join(current_section).strip() + "\n")

    return sections


markdown_input = """## **Preferred Qualifications:**

* Experience with Creo (Pro/E) and Windchill.
* Familiar with ASME Y14.100 and Y14.41.
* Iso/Ortho grid structure design.

###

Base Pay Range for:

WA applicants is $99,201.00 - $138,880.35

**Background Check**

* Required for all positions: Blue’s Standard Background Check
* Required for Certain Job Profiles: Defense Biometric Identification System (DBIDS)
  background check if at any time the role requires one to be on a military
  installation

**Benefits**

* Benefits include: Medical, dental, vision, basic and supplemental life insurance,
  paid parental leave, short and long-term disability, 401(k) with a company
  match of up to 5%, and an Education Support Program.
* Stock Options for all regular employees (working at least 20 hours/week)


**Equal Employment Opportunity**

Purple Town is proud to be an Equal Opportunity/Affirmative Action Employer and
is committed to attracting, retaining, and developing a highly qualified and
dedicated work force. Purple Town hires and promotes people on the basis of their
qualifications, performance, and abilities. We support the establishment and
maintenance of a workplace that fosters trust, equality, and teamwork.

**Affirmative Action and Disability Accommodation**

Applicants wishing to receive information on Purple Town’s Affirmative Action
Plans, or applicants requiring a reasonable accommodation in order to participate
in the application and/or interview process, please contact us at
EEOCompliance@purpletown.com. Please note this is a publicly managed inbox.
Please do not include any personal medical information in your request."""

result = split_markdown_to_sections(markdown_input)

for i, section in enumerate(result, 1):
    print(f"- section {i}")
    print("```")
    print(section)
    print("```\n")

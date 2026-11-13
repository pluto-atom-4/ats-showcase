import os
import re
import tempfile

from bs4 import BeautifulSoup
from markitdown import MarkItDown


def transform_html_to_markdown(html_input):
    soup = BeautifulSoup(html_input, "html.parser")

    for text_node in soup.find_all(string=True):
        cleaned_text = text_node.replace("\xa0", " ")
        text_node.replace_with(cleaned_text)

    # Force the bold header into its own block: look for <b> tags followed by a <br/>.
    for b_tag in soup.find_all("b"):
        if b_tag.next_sibling and b_tag.next_sibling.name == "br":
            # Wrap the bold element in <p> so MarkItDown treats it as a separate block
            p_tag = soup.new_tag("p")
            b_tag.wrap(p_tag)
            b_tag.parent.next_sibling.decompose()

    md_converter = MarkItDown()

    # We use a temporary file because MarkItDown is optimized for file-path inputs
    with tempfile.NamedTemporaryFile(suffix=".html", mode="w", encoding="utf-8", delete=False) as tf:
        tf.write(str(soup))
        temp_path = tf.name

    try:
        result = md_converter.convert(temp_path)
        markdown_output = result.text_content
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

    # Exactly one empty line after bold text ending with a colon (the converter may output a single \n)
    final_md = re.sub(r"(\*\*.*?\*\*:)\s*\n", r"\1\n\n", markdown_output)

    final_md = re.sub(r"\n{3,}", "\n\n", final_md)

    return final_md.strip()


html_content = """
<p>
    <b><span>Pay &amp; Benefits:&nbsp;</span></b><br />
    At Boeing, we strive to deliver a Total Rewards package that will
    attract, engage and retain the top talent. &nbsp;Elements of the Total
    Rewards package include competitive base pay and variable compensation
    opportunities.
</p>
<div><p><strong>Why would you join Carbon Robotics?</strong></p>
<p>
    <span style="font-weight: 400;">Passion for building teams capable of </span>
    <strong>solving uniquely interesting problems</strong>
    <span style="font-weight: 400;">. Innovation while </span>
    <strong>disrupting the market</strong>
    <span style="font-weight: 400;"> is what we do.&nbsp; </span>
    <span style="font-weight: 400;">Profiled in WSJ and Forbes, Carbon Robotics
    is poised to become the next billion dollar company in the rapidly growing
    worldwide Ag-Tech industry.</span>
</p>
<p>
    <strong>Performance Quality Technician</strong><br><br>As a
    <strong>Performance Quality Technician</strong> at<strong> Carbon Robotics,
    </strong> you will be responsible for identifying, diagnosing, and resolving
    systemic issues across our dataset of high-resolution imagery. You'll address
    performance issues and conduct field experiments and data analysis to diagnose
    root causes. Working directly with farmers is a key part of this role,&nbsp;
    you'll build relationships with growers, listen to their feedback, conduct
    field studies, and translate what you learn into systemic improvements, serving
    as a bridge between our customers and our engineering teams. You'll also respond
    to high-priority field issues; when customers hit critical problems, you'll
    move quickly to investigate, diagnose root causes, and coordinate with support,
    Deep Learning, engineering, and field teams to drive fast, effective resolutions
    that keep our customers running.
</p>
"""

markdown_result = transform_html_to_markdown(html_content)
print(markdown_result)

"""Local Streamlit interface for the PDF hidden-text scanner."""

from __future__ import annotations

import csv
import io
import json
import tempfile
from pathlib import Path

import streamlit as st

from detector import scan_pdf


st.set_page_config(page_title="PDF Hidden-Text Scanner", page_icon="🔎", layout="wide")


def findings_as_csv(findings: list[dict]) -> str:
    """Create a downloadable CSV without storing the user's file permanently."""
    buffer = io.StringIO()
    columns = [
        "page",
        "text",
        "font",
        "font_size_pt",
        "text_rgb",
        "background_rgb",
        "color_distance",
        "ink_density",
        "bbox",
        "reasons",
    ]
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    for finding in findings:
        row = finding.copy()
        row["text_rgb"] = str(row["text_rgb"])
        row["background_rgb"] = str(row["background_rgb"])
        row["bbox"] = str(row["bbox"])
        row["reasons"] = "; ".join(row["reasons"])
        writer.writerow(row)
    return buffer.getvalue()


st.title("PDF Hidden-Text Scanner")
st.caption("A local, rule-based first step for detecting potentially hidden PDF text.")
st.info(
    "This tool flags unusual PDF text for review. It does not prove that a document is malicious "
    "and should not be used by itself to make hiring, refund, or other high-impact decisions."
)

with st.sidebar:
    st.header("Detection rules")
    min_font_size = st.slider("Flag font size below (pt)", 1.0, 12.0, 4.0, 0.5)
    color_threshold = st.slider("Background colour similarity", 0.0, 100.0, 25.0, 1.0)
    min_ink_density = st.slider("Minimum visible ink (%)", 0.0, 10.0, 1.5, 0.1) / 100
    st.caption("Higher thresholds flag more text and may create more false positives.")

uploaded_pdf = st.file_uploader("Choose a text-based PDF", type=["pdf"])

if uploaded_pdf is None:
    st.markdown(
        """
        **What it checks**

        - extremely small font sizes;
        - text matching its nearby background; 
        - text that is almost invisible in the rendered PDF; and
        - text outside the visible page.

        Upload a PDF above, then click **Scan PDF**.
        """
    )
elif st.button("Scan PDF", type="primary"):
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temporary_file:
            temporary_file.write(uploaded_pdf.getvalue())
            temp_path = Path(temporary_file.name)

        with st.spinner("Scanning the PDF locally..."):
            findings = scan_pdf(
                temp_path,
                min_font_size=min_font_size,
                color_threshold=color_threshold,
                min_ink_density=min_ink_density,
            )
    except Exception as error:
        st.error(f"Could not scan this PDF: {error}")
        findings = None
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()

    if findings is not None:
        st.session_state["findings"] = findings
        st.session_state["uploaded_name"] = uploaded_pdf.name

if "findings" in st.session_state:
    findings = st.session_state["findings"]
    source_name = st.session_state.get("uploaded_name", "PDF")
    left, right = st.columns(2)
    left.metric("Potentially hidden spans", len(findings))
    right.metric("PDF scanned", source_name)

    if not findings:
        st.success("No text spans matched the current rules.")
    else:
        st.warning("Review every result in context. Decorative text and conversion artifacts can be false positives.")
        display_rows = [
            {
                "Page": finding["page"],
                "Suspicious text": finding["text"],
                "Font size (pt)": finding["font_size_pt"],
                "Reasons": "; ".join(finding["reasons"]),
                "RGB distance": finding["color_distance"],
                "Visible ink": finding["ink_density"],
            }
            for finding in findings
        ]
        st.dataframe(display_rows, use_container_width=True, hide_index=True)

    json_report = json.dumps(findings, indent=2, ensure_ascii=False)
    csv_report = findings_as_csv(findings)
    first, second = st.columns(2)
    first.download_button(
        "Download JSON report",
        data=json_report,
        file_name="hidden_text_report.json",
        mime="application/json",
    )
    second.download_button(
        "Download CSV report",
        data=csv_report,
        file_name="hidden_text_report.csv",
        mime="text/csv",
    )

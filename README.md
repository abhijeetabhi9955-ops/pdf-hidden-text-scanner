# PDF Hidden-Text Scanner

A small local app for scanning text-based PDFs for potentially hidden text.
It is an educational rule-based detector, not proof that a document is malicious.

## Run it in VS Code (Ubuntu/Linux)

1. Install the **Python** extension by Microsoft in VS Code.
2. Open this `pdf-scanner-app` folder using **File > Open Folder**.
3. Open the VS Code terminal with **Ctrl + `**.
4. Run these commands once:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

5. Start the app:

```bash
python -m streamlit run app.py
```

6. Open the `Local URL` shown in the terminal, usually `http://localhost:8501`.

After the first setup you can use **Ctrl+Shift+P**, choose **Tasks: Run Task**,
and select **Run PDF Scanner App**. The included VS Code settings and task use
the `.venv` interpreter created in step 4.

## What it checks

- text smaller than 4 pt by default;
- text whose declared colour is close to its local background;
- text with very low visible ink in the rendered page; and
- text positioned outside the visible page.

False positives are expected, especially with logos, watermarks, decorative
templates, and PDFs created by document-conversion software. Review all flags
manually before taking any action.

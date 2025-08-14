# app.py
# ---------------------------------------
# Streamlit + FPDF Hebrew PDF (RTL) - Cloud-safe
# ---------------------------------------
from pathlib import Path
import streamlit as st
from fpdf import FPDF
import tempfile
import os

# ---------- UI base ----------
st.set_page_config(page_title="מחולל הצעות מחיר - PDF עברית", page_icon="📄", layout="wide")
st.markdown("""
<style>
html, body, [class^="css"] { direction: rtl !important; text-align: right !important; }
[data-testid="stDataEditor"] { direction:ltr !important; }
[data-testid="stDataEditor"] [role="cell"], [data-testid="stDataEditor"] [role="columnheader"] { text-align: left !important; }
</style>
""", unsafe_allow_html=True)

# ---------- Utilities ----------
def heb_setup():
    """Return a callable heb(s) that flips bidi for RTL if python-bidi is available."""
    try:
        from bidi.algorithm import get_display
        def heb(s): 
            return get_display("" if s is None else str(s))
        return heb
    except Exception:
        # Fallback: no bidi shaping (works אבל פחות יפה)
        def heb(s):
            return "" if s is None else str(s)
        return heb

heb = heb_setup()

def get_font_path() -> Path:
    """
    Return a reliable path to DejaVuSans.ttf (root or fonts/).
    Will also attempt a quick recursive search under the app folder.
    Raises FileNotFoundError with a clear Hebrew message if not found.
    """
    here = Path(__file__).parent
    candidates = [
        here / "DejaVuSans.ttf",
        here / "fonts" / "DejaVuSans.ttf",
    ]
    for p in candidates:
        if p.exists():
            return p

    # last resort: shallow recursive search
    for p in here.rglob("DejaVuSans.ttf"):
        return p

    raise FileNotFoundError(
        "נדרש קובץ DejaVuSans.ttf בתיקיית האפליקציה עבור עברית ב‑PDF. "
        "שים אותו ליד app.py או בתיקייה fonts/ והעלה ל‑GitHub."
    )

def register_hebrew_font(pdf: FPDF, font_name: str = "DejaVu"):
    """Register the Unicode TTF font to FPDF (uni=True is mandatory for Hebrew)."""
    font_path = get_font_path()
    pdf.add_font(family=font_name, style="", fname=str(font_path), uni=True)

def build_pdf_bytes(title_text: str, body_text: str, footer_text: str = "") -> bytes:
    """
    Create a Hebrew PDF (RTL) and return its bytes.
    Uses a NamedTemporaryFile because FPDF doesn't accept file-like objects directly.
    """
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Font
    register_hebrew_font(pdf, "DejaVu")
    pdf.set_font("DejaVu", size=18)
    pdf.cell(0, 10, heb(title_text), new_x="LMARGIN", new_y="NEXT", align="R")

    # Divider
    pdf.set_font("DejaVu", size=12)
    pdf.ln(2)
    pdf.cell(0, 1, "", border="T", new_x="LMARGIN", new_y="NEXT")

    # Body
    pdf.ln(4)
    pdf.set_font("DejaVu", size=13)
    pdf.multi_cell(0, 7, heb(body_text), align="R")

    # Footer (optional)
    if footer_text.strip():
        pdf.ln(6)
        pdf.cell(0, 1, "", border="T", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        pdf.set_font("DejaVu", size=11)
        pdf.multi_cell(0, 6, heb(footer_text), align="R")

    # Output to bytes
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp_path = Path(tmp.name)
    try:
        pdf.output(str(tmp_path))
        data = tmp_path.read_bytes()
        return data
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass

def list_repo_files():
    """Small helper to show what files the app sees at runtime (helps debug on Cloud)."""
    here = Path(__file__).parent
    rows = []
    for p in sorted(here.glob("*")):
        rows.append((p.name, "Dir" if p.is_dir() else "File", f"{p.stat().st_size:,}" if p.is_file() else ""))
    return rows

# ---------- Sidebar / Debug ----------
with st.sidebar:
    st.header("מצב סביבת הרצה")
    try:
        font_path = get_font_path()
        st.success(f"נמצא פונט: {font_path.relative_to(Path(__file__).parent)}")
    except Exception as e:
        st.error(str(e))
    with st.expander("קבצים בתיקייה (לעזרה בזיהוי נתיבים)"):
        rows = list_repo_files()
        if rows:
            st.write("| שם | סוג | גודל |")
            st.write("|---|---|---|")
            for n, t, s in rows:
                st.write(f"| {n} | {t} | {s} |")
        else:
            st.write("לא נמצאו קבצים.")

# ---------- Main UI ----------
st.title("📄 יצירת PDF בעברית (RTL) עם DejaVuSans")
st.caption("הקוד נטען פונט Unicode בתצורה שעובדת גם בענן (Streamlit Cloud).")

col1, col2 = st.columns([1, 1])

with col1:
    title_text = st.text_input("כותרת למסמך", "הצעת מחיר לטיול בית ספרי")
    body_text = st.text_area(
        "תוכן עיקרי",
        "שלום רב,\n"
        "מצורפת הצעת מחיר מפורטת בהתאם לבחירת המסלול, מספר התלמידים וצוות ההדרכה.\n"
        "המחירים כוללים הסעות, מדריכים, ביטוחים והפקת מסמכים רשמיים.\n"
        "ניתן להתאים את ההצעה לצרכים מדויקים (לוחות זמנים, תחנות, אתרים ושינויים).\n"
        "\n"
        "פרטי יצירה:\n"
        "• תאריך הטיול: לבחירתכם\n"
        "• מרחב: ירושלים והסביבה\n"
        "• שירותים נוספים: סדנאות, כניסות לאתרים, ביטוח מורחב\n"
    , height=240)
    footer_text = st.text_input("כיתוב תחתון (אופציונלי)", "טללים — מחלקת הדרכה | 054‑2797931")

with col2:
    st.markdown("### הוראות שימוש")
    st.markdown(
        "- ודא שהקובץ **DejaVuSans.ttf** נמצא ליד `app.py` או בתיקייה `fonts/`.\n"
        "- לאחר הלחיצה על *צור PDF*, יופיע כפתור להורדה.\n"
        "- אם מוצגת שגיאה על חוסר בפונט — בדוק את רשימת הקבצים בסרגל הצד."
    )
    st.info("טיפ: אם עדכנת קבצים ב‑GitHub והאפליקציה לא רואה אותם, עשה **Restart** ל‑app ב‑Streamlit Cloud.")

st.divider()

create = st.button("✅ צור PDF")
if create:
    try:
        pdf_bytes = build_pdf_bytes(title_text=title_text, body_text=body_text, footer_text=footer_text)
        st.success("ה‑PDF נוצר בהצלחה. אפשר להוריד.")
        st.download_button(
            label="⬇️ הורד PDF",
            data=pdf_bytes,
            file_name="quote.pdf",
            mime="application/pdf"
        )
    except FileNotFoundError as e:
        st.error(str(e))
    except Exception as e:
        st.exception(e)

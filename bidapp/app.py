import streamlit as st
import pandas as pd
from datetime import date, datetime
from pathlib import Path
from fpdf import FPDF
import base64, re, json

try:
    from bidi.algorithm import get_display
except Exception:
    get_display = lambda s: s

# ---------------- UI Setup ----------------
st.set_page_config(page_title="מחולל הצעות מחיר", page_icon="📄", layout="wide")

LOGO_FILE = Path("לוגו טללים.JPG")
FONT_FILE = Path("DejaVuSans.ttf")

st.markdown("""
<style>
html, body, [class^="css"] { direction: rtl !important; text-align: right !important; }
[data-testid="stDataEditor"] { direction:ltr !important; }
[data-testid="stDataEditor"] [role="cell"], [data-testid="stDataEditor"] [role="columnheader"] { text-align: left !important; }
</style>
""", unsafe_allow_html=True)

# ---------------- Helpers ----------------
def norm_he(txt: str) -> str:
    """נירמול גרש/גרשיים לעבריים כדי לשפר RTL."""
    if txt is None:
        return ""
    txt = str(txt)
    txt = txt.replace('"', '״').replace("'", "׳")
    return txt

def heb(s: str) -> str:
    # bidi נעשה בשלב הציור; כאן רק נירמול
    return norm_he("" if s is None else str(s))

def safe_filename(text: str) -> str:
    text = "" if text is None else str(text)
    text = re.sub(r"[\\/:*?\"'<>|]", " ", text)  # הסרת תווים בעייתיים
    text = re.sub(r"\s+", "_", text.strip())
    text = re.sub(r"_+", "_", text)
    return text or "מסמך"

def is_blank(x) -> bool:
    if x is None:
        return True
    if isinstance(x, float) and pd.isna(x):
        return True
    if isinstance(x, str) and x.strip() == "":
        return True
    return False

def s(x) -> str:
    return "" if is_blank(x) else str(x)

def fmt_money_or_blank(x) -> str:
    if is_blank(x):
        return ""
    try:
        return f"{float(x):.2f}"
    except Exception:
        return ""

def fmt_qty_or_blank(x) -> str:
    if is_blank(x):
        return ""
    try:
        return f"{float(x):.2f}"  # עשרוני
    except Exception:
        return ""

@st.cache_data
def _empty_items_df():
    return pd.DataFrame([{"פריט":"", "עלות ליחידה (₪)":None, "כמות":None, "תיאור / הערות":""}])

# ---------------- Archive (proposals) ----------------
PROPOSALS_DIR = Path("proposals")
PROPOSALS_DIR.mkdir(exist_ok=True)
INDEX_FILE = PROPOSALS_DIR / "index.csv"

@st.cache_data
def load_index():
    if INDEX_FILE.exists():
        try:
            return pd.read_csv(INDEX_FILE, dtype=str).fillna("")
        except Exception:
            pass
    cols = ["id","date","client","subject","total","pdf","html","items_json"]
    return pd.DataFrame(columns=cols)

def save_index(df: pd.DataFrame):
    df.to_csv(INDEX_FILE, index=False, encoding="utf-8")

def new_id():
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f")

def archive_paths(id_, safe_client, safe_subject):
    base = f"{id_}_{safe_client}" + (f"_{safe_subject}" if safe_subject else "")
    pdf_path  = PROPOSALS_DIR / f"{base}.pdf"
    html_path = PROPOSALS_DIR / f"{base}.html"
    json_path = PROPOSALS_DIR / f"{base}.json"
    return pdf_path, html_path, json_path

def archive_save(client_name, subject_text, the_date, total, pdf_bytes, html_bytes, items_df):
    idx = load_index().copy()
    _id = new_id()
    safe_client = safe_filename(client_name)
    safe_subject = safe_filename(subject_text)
    pdf_path, html_path, json_path = archive_paths(_id, safe_client, safe_subject)

    # כתיבה לדיסק
    if pdf_bytes:
        Path(pdf_path).write_bytes(pdf_bytes)
    if html_bytes:
        Path(html_path).write_bytes(html_bytes)
    # שורות הטבלה כ־JSON
    rows = items_df.to_dict(orient="records")
    Path(json_path).write_text(json.dumps({"items": rows}, ensure_ascii=False, indent=2), encoding="utf-8")

    # עדכון אינדקס
    row = {
        "id": _id,
        "date": pd.to_datetime(the_date).strftime("%Y-%m-%d"),
        "client": str(client_name or ""),
        "subject": str(subject_text or ""),
        "total": f"{float(total):.2f}",
        "pdf": str(pdf_path),
        "html": str(html_path),
        "items_json": str(json_path),
    }
    idx = pd.concat([idx, pd.DataFrame([row])], ignore_index=True)
    save_index(idx)
    load_index.clear()  # לרענון cache
    return row

# ---------------- Sidebar ----------------
st.sidebar.header("חתימה")
sig_name = st.sidebar.text_input("שם", "דרור ויזל")
sig_contact = st.sidebar.text_input("סלולרי או מייל", "050-0000000")
sig_company = st.sidebar.text_input("חברה", "טללים חוויות חינוכיות")

st.sidebar.markdown("---")
st.sidebar.subheader("📚 הצעות קודמות")
idx = load_index()
q = st.sidebar.text_input("חיפוש (לקוח/נושא):", "")
if q.strip():
    mask = (idx["client"].str.contains(q, case=False)) | (idx["subject"].str.contains(q, case=False))
    idx_view = idx[mask].copy()
else:
    idx_view = idx.copy()

if not idx_view.empty:
    idx_view = idx_view.sort_values("id", ascending=False)

options = [
    f"{r['date']} · {r['client']} · {r['subject']} · {r['total']}₪"
    for _, r in idx_view.iterrows()
]
sel = st.sidebar.selectbox("בחר הצעה:", options, index=0 if len(options)>0 else None) if len(options)>0 else None

sel_row = None
if sel:
    sel_row = idx_view.iloc[options.index(sel)]
    st.sidebar.caption(f"סה\"כ: {sel_row['total']} ₪")

    # הורדות
    if Path(sel_row["pdf"]).exists():
        st.sidebar.download_button("⬇️ הורדת PDF", data=Path(sel_row["pdf"]).read_bytes(),
                                   file_name=Path(sel_row["pdf"]).name, mime="application/pdf", use_container_width=True)
    if Path(sel_row["html"]).exists():
        st.sidebar.download_button("⬇️ הורדת HTML", data=Path(sel_row["html"]).read_bytes(),
                                   file_name=Path(sel_row["html"]).name, mime="text/html", use_container_width=True)

    # שחזור לטבלה
    if Path(sel_row["items_json"]).exists():
        if st.sidebar.button("🧩 שחזור פריטים לטבלה", use_container_width=True):
            try:
                data = json.loads(Path(sel_row["items_json"]).read_text(encoding="utf-8"))
                items_df = pd.DataFrame(data.get("items", []))
                st.session_state["items"] = items_df
                st.session_state["items_editor"] = items_df
                st.sidebar.success("שוחזר לטבלת הפריטים.")
            except Exception as e:
                st.sidebar.error(f"שחזור נכשל: {e}")
    # תצוגה מקדימה קטנה
    try:
        data = json.loads(Path(sel_row["items_json"]).read_text(encoding="utf-8"))
        preview_df = pd.DataFrame(data.get("items", []))
        if not preview_df.empty:
            st.sidebar.dataframe(preview_df, use_container_width=True, height=240)
    except Exception:
        pass
else:
    st.sidebar.caption("אין הצעות בארכיון או שלא נבחרה הצעה.")

# ---------------- Main Form ----------------
st.title("📄 מחולל הצעות מחיר")

col1, col2 = st.columns([2,1])
with col1:
    client_name = st.text_input("שם לקוח / בית ספר *", "")
    subject_text = st.text_input("תיאור ההצעה (יופיע אחרי 'הצעת מחיר:')", "")
with col2:
    today = st.date_input("תאריך", value=date.today())

st.subheader("פריטים")
if "items" not in st.session_state:
    st.session_state["items"] = _empty_items_df()

edited = st.data_editor(
    st.session_state["items"],
    key="items_editor",
    column_config={
        "פריט": st.column_config.TextColumn("פריט", required=True, width="medium"),
        "עלות ליחידה (₪)": st.column_config.NumberColumn("עלות ליחידה (₪)", min_value=0.0, step=0.1, format="%.2f"),
        "כמות": st.column_config.NumberColumn("כמות", min_value=0.0, step=0.1, format="%.2f"),
        "תיאור / הערות": st.column_config.TextColumn("תיאור / הערות", width="large"),
    },
    num_rows="dynamic",
    hide_index=True,
    use_container_width=True,
)

df_current = st.session_state.get("items_editor")
calc = df_current.copy() if isinstance(df_current, pd.DataFrame) else edited.copy()

calc["עלות ליחידה (₪)"] = pd.to_numeric(calc["עלות ליחידה (₪)"], errors="coerce")
calc["כמות"] = pd.to_numeric(calc["כמות"], errors="coerce")
calc["שדה_סהכ"] = calc["עלות ליחידה (₪)"].fillna(0) * calc["כמות"].fillna(0)
subtotal = float(calc["שדה_סהכ"].sum())
discount_val = st.number_input("הנחה (₪)", value=0.0, min_value=0.0, step=50.0, format="%.2f")
grand_total = max(subtotal - float(discount_val or 0), 0.0)

st.metric("סה\"כ לתשלום", f"{grand_total:,.2f} ₪")

# ---------------- HTML Export ----------------
HTML_CSS = """
<style>
html, body { direction: rtl; text-align: right; font-family: Arial, Helvetica, sans-serif; color:#111; }
.shell { max-width: 1100px; margin: 0 auto; padding: 24px; }
.card { background:#fff; border:1px solid #e5e7eb; border-radius:16px; padding:22px; margin:16px 0; box-shadow:0 2px 6px rgba(0,0,0,.03); }
.header { display:flex; justify-content:space-between; align-items:center; gap:18px; }
.header .date { font-size:18px; color:#374151; }
.logo { height:72px; width:auto; border-radius:8px; object-fit:contain; }
.title { font-size:28px; font-weight:800; margin:0 0 6px 0; }
.subtle { color:#4b5563; }
.table { width:100%; border-collapse:separate; border-spacing:0; }
.table th, .table td { border:1px solid #e5e7eb; padding:10px 12px; vertical-align:top; }
.table thead th { background:#eef2ff; font-weight:700; }
.table tbody tr:nth-child(even) td { background:#fafafa; }
.table td.num { text-align:center; }
.total { margin-top:12px; display:inline-block; border:1px solid #e5e7eb; background:#f8fafc; border-radius:12px; padding:12px 16px; font-weight:700; }
.sign { text-align:center; line-height:1.9; margin-top:20px; }
.sign .divider { height:1px; background:#e5e7eb; margin-bottom:14px; }
</style>
"""

def logo_data_tag():
    if LOGO_FILE.exists():
        b64 = base64.b64encode(LOGO_FILE.read_bytes()).decode("ascii")
        ext = LOGO_FILE.suffix.lower().strip(".")
        mime = "jpeg" if ext in ("jpg", "jpeg") else ext
        return f"<img class='logo' src='data:image/{mime};base64,{b64}'/>"
    return ""

def build_html_doc(client_name, subject_text, table_df, discount, total, sig_name, sig_contact, sig_company, the_date):
    rows = []
    for _, r in table_df.iterrows():
        name = s(r.get('פריט',''))
        unit = r.get('עלות ליחידה (₪)')
        qty = r.get('כמות')
        note = s(r.get('תיאור / הערות','')).replace('\n','<br>')
        unit_txt = fmt_money_or_blank(unit)
        qty_txt = fmt_qty_or_blank(qty)
        tot_txt = ""
        try:
            if not is_blank(unit) and not is_blank(qty):
                tot_txt = f"{float(unit)*float(qty):.2f}"
        except Exception:
            tot_txt = ""
        rows.append(f"""
        <tr>
          <td>{name}</td>
          <td class="num">{unit_txt}</td>
          <td class="num">{qty_txt}</td>
          <td class="num">{tot_txt}</td>
          <td>{note}</td>
        </tr>""")
    html = f"""<!doctype html><html lang="he" dir="rtl"><meta charset="utf-8">{HTML_CSS}
<body>
<div class="shell">
  <div class="card header">
    <div class="date">{the_date.strftime('%d.%m.%Y')}</div>
    <div class="logo-wrap">{logo_data_tag()}</div>
  </div>
  <div class="card">
    <div class="subtle">שם לקוח: {s(client_name) or '—'}</div>
    <div class="title">הצעת מחיר{': ' + s(subject_text) if s(subject_text) else ''}</div>
  </div>
  <div class="card">
    <table class="table" dir="rtl">
      <thead>
        <tr>
          <th>פריט</th><th>עלות ליחידה (₪)</th><th>כמות</th><th>סה&quot;כ (₪)</th><th>תיאור / הערות</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
    <div class="total">סה&quot;כ לתשלום: {total:,.2f} ₪</div>
    {f'<div class="subtle" style="margin-top:6px;">הנחה הופעלה: {discount:,.2f} ₪-</div>' if discount and discount>0 else ''}
  </div>
  <div class="card">
    <div style="font-weight:700;">תנאים והערות</div>
    <div>המחירים כוללים מע&quot;מ.</div>
  </div>
  <div class="card sign">
    <div class="divider"></div>
    בברכה,<br>{s(sig_name)}<br>{s(sig_contact)}<br>{s(sig_company)}
  </div>
</div>
</body></html>"""
    return html

# ---------------- PDF Export (RTL table) ----------------
class PDF(FPDF):
    pass

def rtl_x_positions(pdf, col_w):
    """
    X לכל עמודה לפי RTL:
    סדר העמודות: ["פריט","עלות ליחידה (₪)","כמות","סה\"כ (₪)","תיאור / הערות"]
    """
    x_right = pdf.w - pdf.r_margin
    xs, run = [], 0
    for w in col_w:
        run += w
        xs.append(x_right - run)
    return xs  # xs[i] = X התחלת עמודה i

def draw_table_header_rtl(pdf, headers, col_w):
    xs = rtl_x_positions(pdf, col_w)
    pdf.set_font('DejaVu', '', 12)
    pdf.set_fill_color(238, 242, 255)
    header_h = 11
    for i, h in enumerate(headers):
        pdf.set_xy(xs[i], pdf.get_y())
        pdf.cell(col_w[i], header_h, get_display(heb(h)), border=1, align='C', fill=True)
    pdf.ln()

def ensure_page_space(pdf, h_needed, headers, col_w):
    if pdf.get_y() + h_needed > (pdf.h - pdf.b_margin):
        pdf.add_page()
        draw_table_header_rtl(pdf, headers, col_w)

def wrap_text_rtl(pdf, text, max_w):
    """
    עטיפת טקסט RTL ידנית לשורות לפי רוחב max_w.
    מחזיר רשימת שורות לוגיות; כל שורה תקבל bidi בעת ציור.
    """
    logical = heb(text or "")
    words = logical.split(" ")
    lines, cur = [], ""
    for w in words:
        test = (w if cur == "" else (cur + " " + w))
        vis = get_display(test)
        if pdf.get_string_width(vis) <= max_w or cur == "":
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur != "":
        lines.append(cur)
    return lines

def measure_rtl_height(pdf, text, max_w, line_h):
    lines = wrap_text_rtl(pdf, text, max_w)
    return max(line_h, line_h * len(lines)), lines

def draw_block_rtl(pdf, x, y, w, h, text, line_h=8, align='R', bg=None, pad_r=0.0, pad_l=1.2):
    """
    תא טקסט RTL עם מלבן יחיד (ללא קווי ביניים).
    - pad_r: ריווח מימין (0.0 = צמוד לימין)
    - pad_l: ריווח משמאל
    """
    if bg:
        pdf.set_fill_color(*bg)
        pdf.rect(x, y, w, h, style='DF')
    else:
        pdf.rect(x, y, w, h, style='D')

    lines = wrap_text_rtl(pdf, text or "", max_w=w - pad_l - pad_r)
    if not lines:
        lines = [""]

    for i, ln in enumerate(lines):
        vis = get_display(heb(ln)).strip()
        txt_w = pdf.get_string_width(vis)

        if align == 'C':
            x_text = x + (w - txt_w) / 2.0
        elif align == 'L':
            x_text = x + pad_l
        else:  # 'R'
            x_text = x + w - txt_w - pad_r

        y_text = y + (i+1) * line_h - 1.6  # tweak לבסליין
        pdf.text(x_text, y_text, vis)

def draw_num_block(pdf, x, y, w, h, text, bg=None):
    """תא מספרי/קצר – מלבן יחיד וטקסט ממורכז, ללא רווחים צדדיים."""
    if bg:
        pdf.set_fill_color(*bg)
        pdf.rect(x, y, w, h, style='DF')
    else:
        pdf.rect(x, y, w, h, style='D')

    vis = get_display(heb((text or "").strip()))
    txt_w = pdf.get_string_width(vis)
    x_text = x + (w - txt_w) / 2.0
    y_text = y + (h - 8) / 2.0 + (8 - 1.6)  # line_h=8, tweak לבסליין
    pdf.text(x_text, y_text, vis)

def build_pdf_bytes(client_name, subject_text, table_df, discount, total, the_date):
    if not FONT_FILE.exists():
        st.error("נדרש קובץ DejaVuSans.ttf בתיקיית האפליקציה עבור עברית ב־PDF.")
        return None

    pdf = PDF(orientation="P", unit="mm", format="A4")
    pdf.add_font('DejaVu', '', str(FONT_FILE), uni=True)
    pdf.set_auto_page_break(auto=False, margin=15)
    pdf.add_page()
    pdf.set_line_width(0.2)

    # פס עליון
    band_h = 28
    pdf.set_fill_color(248, 250, 252)
    pdf.rect(x=0, y=0, w=210, h=band_h, style='F')

    # תאריך
    pdf.set_font('DejaVu', '', 12)
    pdf.set_xy(pdf.l_margin, 9)
    pdf.cell(0, 8, get_display(heb(the_date.strftime('%d.%m.%Y'))), align='L')

    # לוגו (קצת יותר גדול)
    if LOGO_FILE.exists():
        logo_w = 36  # הוגדל
        x_logo = pdf.w - pdf.r_margin - logo_w
        pdf.image(str(LOGO_FILE), x=x_logo, y=6, w=logo_w)

    # כותרת מסמך
    pdf.set_y(band_h + 6)
    pdf.set_font('DejaVu', '', 13)
    pdf.cell(0, 8, get_display(heb(f"שם לקוח: {s(client_name)}")), ln=True, align='R')
    pdf.set_font('DejaVu', '', 20)
    title_line = f"הצעת מחיר{': ' + s(subject_text) if s(subject_text) else ''}"
    pdf.cell(0, 10, get_display(heb(title_line)), ln=True, align='R')

    # טבלת פריטים RTL — הסדר שביקשת
    headers = ["פריט", "עלות ליחידה (₪)", "כמות", "סה\"כ (₪)", "תיאור / הערות"]
    col_w = [46, 34, 18, 28, 64]  # פריט | עלות | כמות | סה"כ | תיאור/הערות
    line_h = 8

    draw_table_header_rtl(pdf, headers, col_w)

    row_alt = False
    for _, r in table_df.iterrows():
        row_alt = not row_alt
        bg = (250, 250, 250) if row_alt else None
        xs = rtl_x_positions(pdf, col_w)

        name = s(r.get("פריט",""))
        unit = r.get("עלות ליחידה (₪)")
        qty  = r.get("כמות")
        note = s(r.get("תיאור / הערות","")).replace("\r","")

        unit_txt = fmt_money_or_blank(unit)
        qty_txt  = fmt_qty_or_blank(qty)
        tot_txt  = ""
        try:
            if not is_blank(unit) and not is_blank(qty):
                tot_txt = f"{float(unit)*float(qty):.2f}"
        except Exception:
            tot_txt = ""

        y0 = pdf.get_y()

        # ---- מדידה (בלי ציור) לקבלת גובה שורה אחיד ----
        h_name, _ = measure_rtl_height(pdf, name, col_w[0], line_h)
        h_note, _ = measure_rtl_height(pdf, note, col_w[4], line_h)
        h_row = max(line_h, h_name, h_note)

        ensure_page_space(pdf, h_row, headers, col_w)
        y0 = pdf.get_y()
        xs = rtl_x_positions(pdf, col_w)

        # ---- ציור בפועל (ללא קווי ביניים) ----
        draw_block_rtl(pdf, xs[0], y0, col_w[0], h_row, name, line_h=line_h, align='R', bg=bg, pad_r=0.0)
        draw_num_block(pdf,  xs[1], y0, col_w[1], h_row, unit_txt, bg=bg)
        draw_num_block(pdf,  xs[2], y0, col_w[2], h_row, qty_txt,  bg=bg)
        draw_num_block(pdf,  xs[3], y0, col_w[3], h_row, tot_txt,  bg=bg)
        draw_block_rtl(pdf, xs[4], y0, col_w[4], h_row, note, line_h=line_h, align='R', bg=bg, pad_r=0.0)

        pdf.set_y(y0 + h_row)

    # קופסת סיכום
    pdf.ln(8)
    pdf.set_fill_color(248, 250, 252)
    pdf.set_draw_color(229, 231, 235)
    box_h = 20 if discount and discount>0 else 16
    box_w = 96
    ensure_page_space(pdf, box_h + 10, headers, col_w)
    x = pdf.w - pdf.r_margin - box_w
    y = pdf.get_y()
    pdf.rect(x, y, box_w, box_h, style='DF')
    pdf.set_xy(x + 6, y + (4 if discount and discount>0 else 3))
    pdf.set_font('DejaVu', '', 14)
    pdf.cell(box_w - 12, 8, get_display(heb(f"סה\"כ לתשלום: {total:,.2f} ₪")), align='R')
    if discount and discount>0:
        pdf.set_xy(x + 6, y + 12)
        pdf.set_font('DejaVu', '', 11)
        pdf.cell(box_w - 12, 6, get_display(heb(f"הנחה: -{discount:,.2f} ₪")), align='R')

    # תנאים וחתימה
    pdf.ln(22)
    ensure_page_space(pdf, 30, headers, col_w)
    pdf.set_font('DejaVu', '', 12)
    pdf.multi_cell(0, 7, get_display(heb("תנאים והערות:\nהמחירים כוללים מע״מ.")), align='R')
    pdf.ln(8)

    pdf.set_draw_color(229, 231, 235)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(6)

    sig_block = f"בברכה,\n{s(sig_name)}\n{s(sig_contact)}\n{s(sig_company)}"
    pdf.multi_cell(0, 8, get_display(heb(sig_block)), align='C')

    raw = pdf.output(dest='S')
    return raw if isinstance(raw, (bytes, bytearray)) else raw.encode('latin-1')

# ---------------- Build & Download ----------------
safe_client = safe_filename(client_name)
safe_subject = safe_filename(subject_text)
html_name = f"הצעת_מחיר_{safe_client}_{safe_subject}.html" if safe_subject else f"הצעת_מחיר_{safe_client}.html"
pdf_name  = f"הצעת_מחיר_{safe_client}_{safe_subject}.pdf"  if safe_subject else f"הצעת_מחיר_{safe_client}.pdf"

full_html = build_html_doc(client_name, subject_text, calc, discount_val, grand_total,
                           sig_name, sig_contact, sig_company, today)
pdf_ready = bool(client_name.strip()) and len(calc) > 0
pdf_bytes = build_pdf_bytes(client_name, subject_text, calc, discount_val, grand_total, today) if pdf_ready else None

col_dl1, col_dl2, col_dl3 = st.columns([1,1,1])
with col_dl1:
    st.download_button("📥 הורדה כ־HTML", data=full_html.encode("utf-8"),
                       file_name=html_name, mime="text/html", use_container_width=True)
with col_dl2:
    st.download_button("📥 הורדה כ־PDF",
                       data=(bytes(pdf_bytes) if isinstance(pdf_bytes, bytearray) else (pdf_bytes or b"")),
                       file_name=pdf_name, mime="application/pdf",
                       disabled=(pdf_bytes is None), use_container_width=True)
with col_dl3:
    if st.button("💾 שמירה בארכיון", type="primary", use_container_width=True, disabled=(pdf_bytes is None)):
        try:
            row = archive_save(client_name, subject_text, today, grand_total,
                               pdf_bytes, full_html.encode("utf-8"), calc)
            st.success(f"נשמר בארכיון: {row['date']} · {row['client']} · {row['subject']}")
        except Exception as e:
            st.error(f"שמירה נכשלה: {e}")

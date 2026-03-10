import streamlit as st
import pandas as pd
import re
from collections import OrderedDict
from graphviz import Digraph
import io, os, tempfile
from fpdf import FPDF

# 1. إعدادات الهوية البصرية (RTL)
st.set_page_config(page_title="LL(1) Academic Studio V6.6", layout="wide")
st.markdown("""
    <style>
    .main { direction: RTL; text-align: right; }
    [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    .stTable td { white-space: pre !important; font-family: 'monospace'; }
    .status-box { padding: 12px; border-radius: 8px; text-align: center; font-weight: bold; }
    .accepted { background-color: #d4edda; color: #155724; }
    .rejected { background-color: #f8d7da; color: #721c24; }
    </style>
    """, unsafe_allow_html=True)

# 2. تهيئة الذاكرة
if 'done' not in st.session_state:
    st.session_state.update({'done': False, 'status': "", 'trace': [], 'dot': None, 'n_id': 0, 'stack': []})

# 3. محرك الأمثلة الجاهزة (Presets)
PRESETS = {
    "حسابية (Arithmetic)": {
        "grammar": "E -> T E'\nE' -> + T E' | ε\nT -> F T'\nT' -> * F T' | ε\nF -> ( E ) | id",
        "sentence": "id + id * id $"
    },
    "منطقية (Boolean)": {
        "grammar": "B -> T B'\nB' -> or T B' | ε\nT -> F T'\nT' -> and F T' | ε\nF -> not F | true | false",
        "sentence": "true or false and true $"
    },
    "شرطية (If-Else)": {
        "grammar": "S -> i C t S E\nE -> e S | ε\nC -> b",
        "sentence": "i b t i b t a e a $"
    }
}

# 4. وظائف المعالجة الذكية
def smart_format(text):
    text = text.replace("→", "->").replace("ε", "epsilon")
    text = re.sub(r'([+\-*\/()|])', r' \1 ', text)
    return re.sub(r' +', ' ', text).strip()

class AcademicPDF(FPDF):
    def __init__(self):
        super().__init__()
        # إصلاح خطأ add_font المكتشف في الصور
        if os.path.exists("DejaVuSans.ttf"):
            self.add_font("DejaVu", "", "DejaVuSans.ttf")
            self.font_to_use = "DejaVu"
        else:
            self.font_to_use = "Arial"

    def header(self):
        self.set_font(self.font_to_use, '', 12)
        self.cell(0, 10, 'University of Misan - College of Education', 0, 1, 'C')
        self.ln(5)

    def write_section(self, title, df=None, grammar=None):
        self.set_font(self.font_to_use, '', 11)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 10, title, 1, 1, 'L', fill=True)
        self.ln(2)
        self.set_font(self.font_to_use, '', 9)
        if grammar:
            for k, v in grammar.items():
                line = f"{k} -> {' | '.join([' '.join(p) for p in v])}"
                self.cell(0, 7, line, 0, 1)
        if df is not None:
            col_w = self.epw / len(df.columns)
            for col in df.columns: self.cell(col_w, 8, str(col), 1, 0, 'C')
            self.ln()
            for row in df.values:
                for item in row: self.cell(col_w, 8, str(item), 1, 0, 'C')
                self.ln()
        self.ln(5)

# 5. لوحة التحكم
with st.sidebar:
    st.title("⚙️ الإعدادات")
    
    # ميزة تحميل مثال جاهز
    selected_preset = st.selectbox("📂 تحميل مثال أكاديمي جاهز:", ["-- اختر مثالاً --"] + list(PRESETS.keys()))
    
    if selected_preset != "-- اختر مثالاً --":
        g_val = PRESETS[selected_preset]["grammar"]
        s_val = PRESETS[selected_preset]["sentence"]
    else:
        g_val = "E -> T E'\nE' -> + T E' | ε\nT -> F T'\nT' -> * F T' | ε\nF -> ( E ) | id"
        s_val = "id + id * id $"

    raw_in = st.text_area("أدخل القواعد:", value=g_val, height=180)
    sentence = st.text_input("الجملة المراد فحصها:", value=s_val)
    
    if st.button("🗑 مسح الذاكرة بالكامل"):
        st.session_state.clear()
        st.rerun()

# 6. معالجة القواعد (مع Guard Clause لمنع ValueError)
grammar = OrderedDict()
if raw_in:
    for line in raw_in.strip().split('\n'):
        if '->' in line:
            c_line = smart_format(line)
            try:
                lhs, rhs = c_line.split('->')
                grammar[lhs.strip()] = [p.strip().split() for p in rhs.split('|')]
            except ValueError: continue # تجاوز الأسطر التي لا تحتوي على تقسيم صحيح

# --- (دوال fix_recursion و get_ff و M-Table كما في النسخ السابقة لضمان الدقة) ---
# [ملاحظة: الدوال هنا تظل ثابتة لضمان النتائج الأكاديمية]

def fix_recursion(grammar):
    new_g = OrderedDict()
    for nt, prods in grammar.items():
        rec = [p[1:] for p in prods if p and p[0] == nt]
        non_rec = [p for p in prods if not (p and p[0] == nt)]
        if rec:
            new_nt = f"{nt}'"; new_g[nt] = [p + [new_nt] for p in non_rec] if non_rec else [[new_nt]]
            new_g[new_nt] = [p + [new_nt] for p in rec] + [['ε']]
        else: new_g[nt] = prods
    return new_g

def get_ff(grammar):
    first = {nt: set() for nt in grammar}
    def get_f(seq):
        res = set()
        if not seq or seq == ['ε'] or seq == ['epsilon']: return {'ε'}
        for s in seq:
            sf = first[s] if s in grammar else {s}; res.update(sf - {'ε'})
            if 'ε' not in sf: break
        else: res.add('ε')
        return res
    while True:
        changed = False
        for nt, prods in grammar.items():
            old = len(first[nt])
            for p in prods: first[nt].update(get_f(p))
            if len(first[nt]) > old: changed = True
        if not changed: break
    fo = {nt: set() for nt in grammar}; fo[list(grammar.keys())[0]].add('$')
    while True:
        changed = False
        for nt, prods in grammar.items():
            for p in prods:
                for i, B in enumerate(p):
                    if B in grammar:
                        old = len(fo[B]); beta = p[i+1:]
                        if beta:
                            fb = get_f(beta); fo[B].update(fb - {'ε'})
                            if 'ε' in fb: fo[B].update(fo[nt])
                        else: fo[B].update(fo[nt])
                        if len(fo[B]) > old: changed = True
        if not changed: break
    return first, fo

if grammar:
    fixed_g = fix_recursion(grammar)
    f_s, fo_s = get_ff(fixed_g)
    
    # بناء جدول M-Table
    terms = sorted(list({s for ps in fixed_g.values() for p in ps for s in p if s not in fixed_g and s != 'ε'})) + ['$']
    m_table = pd.DataFrame("", index=fixed_g.keys(), columns=terms)
    for nt, prods in fixed_g.items():
        for p in prods:
            pf = set()
            for s in p:
                sf = f_s[s] if s in fixed_g else {s}; pf.update(sf - {'ε'})
                if 'ε' not in sf: break
            else: pf.add('ε')
            for a in pf:
                if a != 'ε': m_table.at[nt, a] = f"{nt}->{' '.join(p)}"
            if 'ε' in pf:
                for b in fo_s[nt]: m_table.at[nt, b] = f"{nt}->{' '.join(p)}"

    st.title("🎓 LL(1) Compiler Studio - V6.6")
    
    st.subheader("📊 جداول التحليل الرياضي")
    c1, c2 = st.columns([1, 2])
    with c1: st.write("**الـ First & Follow:**"); st.table(pd.DataFrame({"First": [str(f_s[n]) for n in fixed_g], "Follow": [str(fo_s[n]) for n in fixed_g]}, index=fixed_g.keys()))
    with c2: st.write("**جدول التنبؤ (M-Table):**"); st.dataframe(m_table, use_container_width=True)

    st.divider()
    
    # 7. المحاكاة
    if st.session_state.dot is None:
        st.session_state.dot = Digraph(); st.session_state.dot.node('0', list(fixed_g.keys())[0], style='filled', fillcolor='lightblue')
        st.session_state.stack = [('$', '0'), (list(fixed_g.keys())[0], '0')]

    def run_step():
        s = st.session_state
        if s.done or not s.stack: return
        tokens = smart_format(sentence).split()
        m_count = sum(1 for x in s.trace if "Match" in x['Action'])
        look = tokens[m_count] if m_count < len(tokens) else '$'
        top, pid = s.stack.pop()
        
        # استخدام الرمز غير المرئي لمنع تحول السلسلة لـ Bullets
        display_input = "\u200B " + " ".join(tokens[m_count:])
        
        row = {"Stack": " ".join([v for v, i in s.stack] + [top]), "Input": display_input, "Action": ""}
        if top == look:
            row["Action"] = f"Match {look}"
            if top == '$': s.done, s.status = True, "Accepted"
        elif top in fixed_g:
            rule = m_table.at[top, look]
            if rule and rule != "":
                row["Action"] = f"Apply {rule}"
                rhs = rule.split('->')[1].split()
                if rhs == ['ε'] or rhs == ['epsilon']:
                    nid = f"e_{pid}_{s.n_id}"; s.dot.node(nid, "ε", shape='plaintext'); s.dot.edge(pid, nid)
                else:
                    tmp = []
                    for sym in rhs:
                        s.n_id += 1; nid = str(s.n_id)
                        s.dot.node(nid, sym, style='filled', fillcolor='lightgreen'); s.dot.edge(pid, nid)
                        tmp.append((sym, nid))
                    for item in reversed(tmp): s.stack.append(item)
            else:
                row["Action"] = "❌ Error"; s.done, s.status = True, "Rejected"
        else:
            row["Action"] = "❌ Error"; s.done, s.status = True, "Rejected"
        s.trace.append(row)

    st.subheader("⏳ محاكاة خطوات الإعراب")
    btn1, btn2 = st.columns(2)
    if btn1.button("⏭ خطوة واحدة"): run_step()
    if btn2.button("▶ تشغيل تلقائي"):
        while not st.session_state.done: run_step()

    if st.session_state.trace:
        st.table(pd.DataFrame(st.session_state.trace))
        st.graphviz_chart(st.session_state.dot)
        if st.session_state.done:
            st.markdown(f'<div class="status-box {"accepted" if st.session_state.status == "Accepted" else "rejected"}">{st.session_state.status}</div>', unsafe_allow_html=True)

    # 8. التصدير
    st.divider()
    if st.button("📄 توليد وتحميل تقرير PDF الشامل"):
        pdf = AcademicPDF(); pdf.add_page()
        pdf.write_section("1. Corrected Grammar", grammar=fixed_g)
        pdf.write_section("2. First & Follow Sets", df=pd.DataFrame({"First": [str(f_s[n]) for n in fixed_g], "Follow": [str(fo_s[n]) for n in fixed_g]}, index=fixed_g.keys()).reset_index())
        pdf.write_section("3. Prediction Table", df=m_table.reset_index())
        if st.session_state.trace:
            pdf.write_section("4. Trace Steps", df=pd.DataFrame(st.session_state.trace))
            # تحويل الشجرة لصورة داخل الـ PDF
            img_data = st.session_state.dot.pipe(format='png')
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                tmp.write(img_data); tmp_path = tmp.name
            pdf.add_page()
            pdf.image(tmp_path, x=10, y=20, w=180)
            os.unlink(tmp_path)
        
        # تصدير الملف بشكل آمن
        st.download_button("📥 اضغط هنا لتحميل الملف", pdf.output(), "LL1_Final_Report.pdf", "application/pdf")

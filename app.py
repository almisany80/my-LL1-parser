import streamlit as st
import pandas as pd
import re
from collections import OrderedDict
from graphviz import Digraph
import io
import os
import tempfile
from fpdf import FPDF

# 1. إعدادات الواجهة والجماليات (RTL)
st.set_page_config(page_title="LL(1) Intelligent Studio V6.5", layout="wide")
st.markdown("""
    <style>
    .main { direction: RTL; text-align: right; }
    [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    /* منع تحول الرموز الرياضية إلى قوائم نقطية في جداول ستريمليت */
    .stTable td { white-space: pre !important; font-family: 'monospace' !important; color: #1e1e1e; }
    .status-box { padding: 15px; border-radius: 8px; text-align: center; font-weight: bold; margin: 10px 0; }
    .accepted { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
    .rejected { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
    .header-style { background-color: #f0f2f6; padding: 10px; border-radius: 5px; border-right: 5px solid #007bff; }
    </style>
    """, unsafe_allow_html=True)

# 2. تهيئة الذاكرة (Session State) لتجنب AttributeError
if 'done' not in st.session_state:
    st.session_state.update({
        'done': False, 'status': "", 'step': 0, 
        'stack': [], 'trace': [], 'dot': None, 
        'n_id': 0
    })

# 3. وظيفة المعالجة الذكية (Smart Tokenizer) لمرونة الإدخال
def smart_format(text):
    """تنظيف المدخلات وإضافة مسافات حول الرموز تلقائياً"""
    text = text.replace("→", "->").replace("ε", "epsilon")
    # إضافة مسافات حول الرموز الخاصة
    text = re.sub(r'([+\-*\/()|])', r' \1 ', text)
    # تنظيف المسافات الزائدة
    text = re.sub(r' +', ' ', text)
    return text.strip()

# 4. فئة PDF الأكاديمية (دعم الجداول والصور)
class AcademicPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.font_to_use = "DejaVu" if os.path.exists("DejaVuSans.ttf") else "Arial"
        if os.path.exists("DejaVuSans.ttf"): self.add_font("DejaVu", "", "DejaVuSans.ttf")

    def header(self):
        self.set_font(self.font_to_use, '', 12)
        self.cell(0, 8, 'University of Misan - College of Education', 0, 1, 'C')
        self.cell(0, 8, 'Computer Science Department - LL(1) Report', 0, 1, 'C')
        self.ln(10)

    def write_section(self, title, df=None, grammar=None):
        self.set_font(self.font_to_use, '', 11)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 10, title, 1, 1, 'L', fill=True)
        self.ln(2)
        self.set_font(self.font_to_use, '', 9)
        if grammar:
            for k, v in grammar.items():
                line = f"{k} -> {' | '.join([' '.join(p) for p in v])}"
                self.cell(0, 8, line, 0, 1)
        if df is not None:
            col_w = self.epw / len(df.columns)
            for col in df.columns: self.cell(col_w, 8, str(col), 1, 0, 'C')
            self.ln()
            for row in df.values:
                for item in row: self.cell(col_w, 8, str(item), 1, 0, 'C')
                self.ln()
        self.ln(5)

    def add_tree_image(self, dot_graph):
        self.add_page()
        self.set_font(self.font_to_use, '', 11)
        self.cell(0, 10, "5. Visual Parsing Tree", 1, 1, 'L', fill=True)
        self.ln(5)
        try:
            img_data = dot_graph.pipe(format='png')
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                tmp.write(img_data)
                tmp_path = tmp.name
            self.image(tmp_path, x=10, y=None, w=180)
            os.unlink(tmp_path)
        except: self.cell(0, 10, "(Tree rendering skipped)", 0, 1)

# 5. محرك المعالجة الرياضي
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

# 6. الواجهة والتحكم
with st.sidebar:
    st.header("⚙️ الإعدادات")
    with st.expander("❓ دليل كتابة القواعد"):
        st.info("اكتب القواعد بمرونة، مثال:\nE -> E+T | T\nالنظام سيعالج المسافات والرموز تلقائياً.")
    
    raw_in = st.text_area("أدخل القواعد:", "E -> T E'\nE' -> + T E' | ε\nT -> F T'\nT' -> * F T' | ε\nF -> ( E ) | id", height=180)
    sentence = st.text_input("الجملة المراد فحصها:", "id + id * id $")
    if st.button("🗑 إعادة ضبط النظام"):
        st.session_state.clear(); st.rerun()

# معالجة القواعد
grammar = OrderedDict()
if raw_in:
    for line in raw_in.strip().split('\n'):
        if '->' in line:
            c_line = smart_format(line)
            lhs, rhs = c_line.split('->')
            grammar[lhs.strip()] = [p.strip().split() for p in rhs.split('|')]

if grammar:
    fixed_g = fix_recursion(grammar)
    f_s, fo_s = get_ff(fixed_g)
    
    st.markdown('<h2 class="header-style">🖥️ LL(1) Compiler Studio - V6.5</h2>', unsafe_allow_html=True)
    
    # عرض الجداول
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📋 القواعد المصححة")
        for k, v in fixed_g.items(): st.code(f"{k} → {' | '.join([' '.join(p) for p in v])}")
    with c2:
        st.subheader("🔍 مجموعات First & Follow")
        ff_df = pd.DataFrame({"First": [str(f_s[n]) for n in fixed_g], "Follow": [str(fo_s[n]) for n in fixed_g]}, index=fixed_g.keys())
        st.table(ff_df)

    # بناء M-Table
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
    
    st.subheader("📊 جدول التنبؤ (Parsing Table)")
    st.dataframe(m_table, use_container_width=True)

    # 7. المحاكاة (Simulation)
    st.divider()
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
        
        # حل مشكلة النقاط السوداء (Zero Width Space)
        display_input = "\u200B " + " ".join(tokens[m_count:])
        
        row = {"Stack": " ".join([v for v, i in s.stack] + [top]), "Input": display_input, "Action": ""}
        if top == look:
            row["Action"] = f"Match {look}"
            if top == '$': s.done, s.status = True, "Accepted"
        elif top in fixed_g:
            rule = m_table.at[top, look]
            if rule:
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

    col_btn1, col_btn2 = st.columns(2)
    if col_btn1.button("⏭ خطوة تالية"): run_step()
    if col_btn2.button("▶ تشغيل كامل"):
        while not st.session_state.done: run_step()

    if st.session_state.trace:
        st.subheader("⏳ تتبع خطوات الإعراب")
        st.table(pd.DataFrame(st.session_state.trace))
        st.graphviz_chart(st.session_state.dot)
        if st.session_state.done:
            st.markdown(f'<div class="status-box {"accepted" if st.session_state.status == "Accepted" else "rejected"}">{st.session_state.status}</div>', unsafe_allow_html=True)

    # 8. التصدير (PDF & Excel)
    st.divider()
    c_pdf, c_xls = st.columns(2)
    with c_pdf:
        if st.button("📄 تحميل تقرير PDF الشامل"):
            pdf = AcademicPDF(); pdf.add_page()
            pdf.write_section("1. Input Grammar", grammar=fixed_g)
            pdf.write_section("2. First & Follow Sets", df=ff_df.reset_index())
            pdf.write_section("3. Prediction Table", df=m_table.reset_index())
            if st.session_state.trace:
                pdf.write_section("4. Execution Trace", df=pd.DataFrame(st.session_state.trace))
                pdf.add_tree_image(st.session_state.dot)
            st.download_button("📥 حفظ التقرير PDF", bytes(pdf.output()), "LL1_Misan_Report.pdf", "application/pdf")

    with c_xls:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
            ff_df.to_excel(wr, sheet_name='Sets')
            m_table.to_excel(wr, sheet_name='Table')
            if st.session_state.trace: pd.DataFrame(st.session_state.trace).to_excel(wr, sheet_name='Trace', index=False)
        st.download_button("📥 تحميل ملف Excel", buf.getvalue(), "Compiler_Data.xlsx")

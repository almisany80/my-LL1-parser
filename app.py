import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import io
import os
from fpdf import FPDF

# 1. إعدادات الواجهة (RTL) ومعالجة مظهر الجداول
st.set_page_config(page_title="LL(1) Compiler Studio V6.3", layout="wide")
st.markdown("""
    <style>
    .main { direction: RTL; text-align: right; }
    [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    /* إجبار الجداول على عرض النصوص كما هي ومنع القوائم النقطية */
    .stTable td { white-space: pre !important; font-family: 'monospace' !important; color: #1e1e1e; }
    .status-box { padding: 15px; border-radius: 8px; text-align: center; font-weight: bold; margin: 10px 0; }
    .accepted { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
    .rejected { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
    </style>
    """, unsafe_allow_html=True)

# 2. تهيئة الذاكرة (Session State) في بداية السكربت لمنع الـ AttributeError
if 'done' not in st.session_state:
    st.session_state.update({
        'done': False, 'status': "", 'step': 0, 
        'stack': [], 'trace': [], 'dot': Digraph(), 
        'n_id': 0, 'last_grammar': ""
    })

# 3. فئة PDF الأكاديمية (معالجة الأخطاء الباينري)
class AcademicPDF(FPDF):
    def __init__(self):
        super().__init__()
        if os.path.exists("DejaVuSans.ttf"):
            self.add_font("DejaVu", "", "DejaVuSans.ttf")
            self.font_to_use = "DejaVu"
        else:
            self.font_to_use = "Arial"

    def header(self):
        self.set_font(self.font_to_use, '', 11)
        self.cell(0, 10, 'University of Misan - LL(1) Parsing Report', 0, 1, 'C')
        self.ln(5)

    def write_table(self, title, df):
        self.set_font(self.font_to_use, '', 10)
        self.cell(0, 10, title, 1, 1, 'C')
        col_width = self.epw / len(df.columns)
        for col in df.columns: self.cell(col_width, 7, str(col), 1, 0, 'C')
        self.ln()
        for row in df.values:
            for item in row: self.cell(col_width, 7, str(item), 1, 0, 'C')
            self.ln()
        self.ln(5)

# 4. محرك المعالجة (Grammar Engine)
def fix_left_recursion(grammar):
    new_g = OrderedDict()
    for nt, prods in grammar.items():
        rec = [p[1:] for p in prods if p and p[0] == nt]
        non_rec = [p for p in prods if not (p and p[0] == nt)]
        if rec:
            new_nt = f"{nt}'"
            new_g[nt] = [p + [new_nt] for p in non_rec] if non_rec else [[new_nt]]
            new_g[new_nt] = [p + [new_nt] for p in rec] + [['ε']]
        else: new_g[nt] = prods
    return new_g

def calculate_sets(grammar):
    first = {nt: set() for nt in grammar}
    def get_f(seq):
        res = set()
        if not seq or seq == ['ε']: return {'ε'}
        for s in seq:
            sf = first[s] if s in grammar else {s}
            res.update(sf - {'ε'})
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
    
    follow = {nt: set() for nt in grammar}; follow[list(grammar.keys())[0]].add('$')
    while True:
        changed = False
        for nt, prods in grammar.items():
            for p in prods:
                for i, B in enumerate(p):
                    if B in grammar:
                        old = len(follow[B]); beta = p[i+1:]
                        if beta:
                            fb = get_f(beta); follow[B].update(fb - {'ε'})
                            if 'ε' in fb: follow[B].update(follow[nt])
                        else: follow[B].update(follow[nt])
                        if len(follow[B]) > old: changed = True
        if not changed: break
    return first, follow

# 5. المدخلات (Sidebar)
with st.sidebar:
    st.header("⚙️ لوحة التحليل")
    raw_input = st.text_area("أدخل القواعد:", "E -> T E'\nE' -> + T E' | ε\nT -> F T'\nT' -> * F T' | ε\nF -> ( E ) | id", height=180)
    test_sentence = st.text_input("الجملة المختبرة:", "id + id * id $")
    
    if st.button("🗑 مسح الجلسة وإعادة الضبط"):
        st.session_state.clear()
        st.rerun()

# 6. المعالجة الأساسية
grammar = OrderedDict()
for line in raw_input.strip().split('\n'):
    if '->' in line:
        lhs, rhs = line.split('->')
        grammar[lhs.strip()] = [p.strip().split() for p in rhs.split('|')]

if grammar:
    fixed_g = fix_left_recursion(grammar)
    first_s, follow_s = calculate_sets(fixed_g)
    
    # بناء جدول التنبؤ
    terms = sorted(list({s for ps in fixed_g.values() for p in ps for s in p if s not in fixed_g and s != 'ε'})) + ['$']
    m_table = pd.DataFrame("", index=fixed_g.keys(), columns=terms)
    for nt, prods in fixed_g.items():
        for p in prods:
            pf = set()
            for s in p:
                sf = first_s[s] if s in fixed_g else {s}; pf.update(sf - {'ε'})
                if 'ε' not in sf: break
            else: pf.add('ε')
            for a in pf:
                if a != 'ε': m_table.at[nt, a] = f"{nt}->{' '.join(p)}"
            if 'ε' in pf:
                for b in follow_s[nt]: m_table.at[nt, b] = f"{nt}->{' '.join(p)}"

    # العرض الأكاديمي للنتائج
    st.title("🖥️ LL(1) Compiler Studio")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📋 القواعد بعد المعالجة")
        for k, v in fixed_g.items(): st.code(f"{k} → {' | '.join([' '.join(p) for p in v])}")
    with col2:
        st.subheader("🔍 مجموعات First & Follow")
        ff_df = pd.DataFrame({"First": [str(first_s[n]) for n in fixed_g], "Follow": [str(follow_s[n]) for n in fixed_g]}, index=fixed_g.keys())
        st.table(ff_df)

    st.subheader("📊 جدول التنبؤ (Parsing Table)")
    st.dataframe(m_table, use_container_width=True)

    # 7. المحاكاة (معالجة مشكلة النقاط السوداء)
    st.divider()
    st.subheader("⏳ تتبع الجملة (Parsing Trace)")
    
    if not st.session_state.stack:
        st.session_state.stack = [('$', '0'), (list(fixed_g.keys())[0], '0')]
        st.session_state.dot = Digraph(); st.session_state.dot.node('0', list(fixed_g.keys())[0], style='filled', fillcolor='lightblue')

    def step_sim():
        s = st.session_state
        if s.done or not s.stack: return
        tokens = test_sentence.split()
        match_count = sum(1 for x in s.trace if "Match" in x['Action'])
        look = tokens[match_count] if match_count < len(tokens) else '$'
        top, pid = s.stack.pop()
        
        # الحل الجذري للنقاط السوداء: تغليف المدخلات بترميز خاص أو مسافة غير قابلة للكسر
        # \u200B هي مسافة صفرية العرض تمنع المتصفح من رؤية الرمز (+ أو -) كبداية قائمة
        display_input = "\u200B " + " ".join(tokens[match_count:])
        
        step_rec = {"Stack": " ".join([v for v, i in s.stack] + [top]), "Input": display_input, "Action": ""}
        
        if top == look:
            step_rec["Action"] = f"Match {look}"
            if top == '$': s.done, s.status = True, "Accepted"
        elif top in fixed_g:
            rule = m_table.at[top, look]
            if rule:
                step_rec["Action"] = f"Apply {rule}"
                rhs = rule.split('->')[1].split()
                if rhs == ['ε']:
                    nid = f"e_{pid}_{s.n_id}"; s.dot.node(nid, "ε", shape='plaintext'); s.dot.edge(pid, nid)
                else:
                    tmp = []
                    for sym in rhs:
                        s.n_id += 1; nid = str(s.n_id)
                        s.dot.node(nid, sym, style='filled', fillcolor='lightgreen'); s.dot.edge(pid, nid)
                        tmp.append((sym, nid))
                    for item in reversed(tmp): s.stack.append(item)
            else:
                step_rec["Action"] = "❌ Error"; s.done, s.status = True, "Rejected"
        else:
            step_rec["Action"] = "❌ Error"; s.done, s.status = True, "Rejected"
        s.trace.append(step_rec)

    btn_col1, btn_col2 = st.columns(2)
    if btn_col1.button("⏭ خطوة تالية"): step_sim()
    if btn_col2.button("▶ تشغيل كامل"):
        while not st.session_state.done: step_sim()

    if st.session_state.trace:
        st.table(pd.DataFrame(st.session_state.trace))
        st.graphviz_chart(st.session_state.dot)
        if st.session_state.done:
            css_class = "accepted" if st.session_state.status == "Accepted" else "rejected"
            st.markdown(f'<div class="status-box {css_class}">{st.session_state.status}</div>', unsafe_allow_html=True)

    # 8. التصدير (إصلاح خطأ الـ PDF والـ Excel المفقود)
    st.divider()
    st.subheader("📥 تصدير التقارير النهائية")
    exp_col1, exp_col2 = st.columns(2)
    
    with exp_col1:
        if st.button("📄 تصدير تقرير PDF"):
            try:
                pdf = AcademicPDF(); pdf.add_page()
                pdf.write_table("First & Follow Sets", ff_df.reset_index())
                pdf.write_table("Parsing Table (M-Table)", m_table.reset_index())
                if st.session_state.trace:
                    pdf.write_table("Parsing Trace", pd.DataFrame(st.session_state.trace))
                # التحويل الصريح لـ bytes لحل مشكلة bytearray
                pdf_output = bytes(pdf.output())
                st.download_button("📥 تحميل PDF", pdf_output, "LL1_Report.pdf", "application/pdf")
            except Exception as e:
                st.error(f"خطأ تقني في PDF: {str(e)}")

    with exp_col2:
        # إضافة زر الإكسل مع التأكد من وجود البيانات
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            ff_df.to_excel(writer, sheet_name='FF_Sets')
            m_table.to_excel(writer, sheet_name='M_Table')
            if st.session_state.trace:
                pd.DataFrame(st.session_state.trace).to_excel(writer, sheet_name='Trace', index=False)
        st.download_button("📥 تحميل ملف Excel", buf.getvalue(), "Compiler_Data.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

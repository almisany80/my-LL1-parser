import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import io
import os
from fpdf import FPDF

# 1. إعدادات الواجهة (RTL) وتنسيق الجداول
st.set_page_config(page_title="LL(1) Compiler Studio V6.1", layout="wide")
st.markdown("""
    <style>
    .main { direction: RTL; text-align: right; }
    [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    /* منع تحول الرموز الرياضية إلى نقاط في الجداول */
    .stTable td { white-space: nowrap !important; font-family: 'Courier New', monospace !important; }
    .status-accepted { background-color: #2e7d32; color: white; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; }
    .status-rejected { background-color: #c62828; color: white; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# 2. فئة PDF المحدثة (إصلاح خطأ 'unicode' ورموز العمليات)
class AcademicPDF(FPDF):
    def __init__(self):
        super().__init__()
        # إصلاح الخطأ: إزالة 'unicode=True' لأن المكتبات الحديثة تدعمه افتراضياً
        if os.path.exists("DejaVuSans.ttf"):
            self.add_font("DejaVu", "", "DejaVuSans.ttf")
            self.font_to_use = "DejaVu"
        else:
            self.font_to_use = "Arial"

    def header(self):
        self.set_font(self.font_to_use, '', 12)
        self.cell(0, 10, 'LL(1) Parsing Report - University of Misan', 0, 1, 'C')
        self.ln(5)

    def add_section(self, title, df=None, grammar=None):
        self.set_font(self.font_to_use, '', 11)
        self.cell(0, 10, title, 0, 1, 'L')
        self.set_font(self.font_to_use, '', 9)
        if grammar:
            for k, v in grammar.items():
                line = f"{k} -> {' | '.join([' '.join(p) for p in v])}"
                self.cell(0, 8, line, 0, 1)
        if df is not None:
            col_width = self.epw / len(df.columns)
            # رسم رؤوس الجدول
            for col in df.columns:
                self.cell(col_width, 8, str(col), 1, 0, 'C')
            self.ln()
            # رسم البيانات مع ضمان عدم تحول الرموز
            for row in df.values:
                for datum in row:
                    self.cell(col_width, 8, str(datum), 1, 0, 'C')
                self.ln()
        self.ln(5)

# 3. محرك المعالجة (Grammar Engine)
def transform_grammar(grammar):
    new_g = OrderedDict()
    for nt, prods in grammar.items():
        recursive = [p[1:] for p in prods if p and p[0] == nt]
        non_recursive = [p for p in prods if not (p and p[0] == nt)]
        if recursive:
            new_nt = f"{nt}'"
            new_g[nt] = [p + [new_nt] for p in non_recursive] if non_recursive else [[new_nt]]
            new_g[new_nt] = [p + [new_nt] for p in recursive] + [['ε']]
        else: new_g[nt] = prods
    return new_g

def calculate_ff(grammar):
    first = {nt: set() for nt in grammar}
    def get_seq_first(seq):
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
            old_len = len(first[nt])
            for p in prods: first[nt].update(get_seq_first(p))
            if len(first[nt]) > old_len: changed = True
        if not changed: break
    
    follow = {nt: set() for nt in grammar}; follow[list(grammar.keys())[0]].add('$')
    while True:
        changed = False
        for nt, prods in grammar.items():
            for p in prods:
                for i, B in enumerate(p):
                    if B in grammar:
                        old_len = len(follow[B]); beta = p[i+1:]
                        if beta:
                            fb = get_seq_first(beta); follow[B].update(fb - {'ε'})
                            if 'ε' in fb: follow[B].update(follow[nt])
                        else: follow[B].update(follow[nt])
                        if len(follow[B]) > old_len: changed = True
        if not changed: break
    return first, follow

# 4. واجهة المدخلات
with st.sidebar:
    st.header("⚙️ لوحة التحكم")
    raw_in = st.text_area("أدخل القواعد:", "E -> T E'\nE' -> + T E' | ε\nT -> F T'\nT' -> * F T' | ε\nF -> ( E ) | id", height=150)
    sentence = st.text_input("الجملة المختبرة (مثلاً id + id $):", "id + id * id $")
    if st.button("🗑 مسح الذاكرة"):
        st.session_state.clear()
        st.rerun()

# 5. التنفيذ والعرض
grammar = OrderedDict()
for line in raw_in.strip().split('\n'):
    if '->' in line:
        lhs, rhs = line.split('->')
        grammar[lhs.strip()] = [p.strip().split() for p in rhs.split('|')]

if grammar:
    fixed_g = transform_grammar(grammar)
    f_sets, fo_sets = calculate_ff(fixed_g)
    
    st.header("1️⃣ التحليل الأكاديمي")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📋 القواعد بعد المعالجة")
        for k, v in fixed_g.items():
            st.code(f"{k} → {' | '.join([' '.join(p) for p in v])}")
    with c2:
        st.subheader("🔍 جداول First & Follow")
        ff_df = pd.DataFrame({
            "First": [str(f_sets[n]) for n in fixed_g],
            "Follow": [str(fo_sets[n]) for n in fixed_g]
        }, index=fixed_g.keys())
        st.table(ff_df)

    # بناء M-Table مع ضمان استقرار الرموز
    terms = sorted(list({s for ps in fixed_g.values() for p in ps for s in p if s not in fixed_g and s != 'ε'})) + ['$']
    m_table = pd.DataFrame("", index=fixed_g.keys(), columns=terms)
    for nt, prods in fixed_g.items():
        for p in prods:
            p_f = set()
            for s in p:
                sf = f_sets[s] if s in fixed_g else {s}; p_f.update(sf - {'ε'})
                if 'ε' not in sf: break
            else: p_f.add('ε')
            for a in p_f:
                if a != 'ε': m_table.at[nt, a] = f"{nt}->{' '.join(p)}"
            if 'ε' in p_f:
                for b in fo_sets[nt]: m_table.at[nt, b] = f"{nt}->{' '.join(p)}"

    st.subheader("📊 جدول التنبؤ (M-Table)")
    st.dataframe(m_table, use_container_width=True)

    # 6. المحاكاة (Step-by-Step)
    st.header("2️⃣ تتبع الجملة (Simulation)")
    if 'idx' not in st.session_state:
        st.session_state.update({'idx': 0, 'stack': [('$', '0'), (list(fixed_g.keys())[0], '0')], 'trace': [], 'dot': Digraph(), 'finished': False, 'node_id': 0})
        st.session_state.dot.node('0', list(fixed_g.keys())[0], style='filled', fillcolor='lightblue')

    def run_step():
        s = st.session_state
        if s.finished or not s.stack: return
        tokens = sentence.split(); look_idx = sum(1 for x in s.trace if "Match" in x['Action'])
        look = tokens[look_idx] if look_idx < len(tokens) else '$'
        top, pid = s.stack.pop()
        
        # ضمان ظهور الرموز الرياضية كنصوص في الجدول
        step_data = {"Stack": " ".join([v for v, i in s.stack] + [top]), "Input": " ".join(tokens[look_idx:]), "Action": ""}
        
        if top == look:
            step_data["Action"] = f"Match {look}"
            if top == '$': s.finished, s.status = True, "Accepted"
        elif top in fixed_g:
            rule = m_table.at[top, look]
            if rule:
                step_data["Action"] = f"Apply {rule}"
                rhs = rule.split('->')[1].split()
                if rhs == ['ε']:
                    nid = f"e_{pid}_{s.node_id}"; s.dot.node(nid, "ε", shape='plaintext'); s.dot.edge(pid, nid)
                else:
                    temp = []
                    for sym in rhs:
                        s.node_id += 1; nid = str(s.node_id)
                        s.dot.node(nid, sym, style='filled', fillcolor='lightgreen'); s.dot.edge(pid, nid)
                        temp.append((sym, nid))
                    for item in reversed(temp): s.stack.append(item)
            else:
                step_data["Action"] = "❌ Error"; s.finished, s.status = True, "Rejected"
        else:
            step_data["Action"] = "❌ Error"; s.finished, s.status = True, "Rejected"
        s.trace.append(step_data)

    col1, col2 = st.columns(2)
    if col1.button("⏭ خطوة تالية"): run_step()
    if col2.button("▶ تشغيل كامل"):
        while not st.session_state.finished: run_step()

    if st.session_state.trace:
        st.table(pd.DataFrame(st.session_state.trace))
        st.graphviz_chart(st.session_state.dot)
        if st.session_state.finished:
            st.markdown(f'<div class="status-{st.session_state.status.lower()}">{st.session_state.status}</div>', unsafe_allow_html=True)

    # 7. التصدير (إصلاح الخطأ النهائي)
    st.header("3️⃣ تصدير التقارير")
    if st.button("📄 توليد وتحميل PDF"):
        try:
            pdf = AcademicPDF(); pdf.add_page()
            pdf.add_section("1. Corrected Grammar", grammar=fixed_g)
            pdf.add_section("2. First & Follow Sets", df=ff_df.reset_index())
            pdf.add_section("3. Prediction Table (M-Table)", df=m_table.reset_index())
            if st.session_state.trace:
                pdf.add_section("4. Execution Trace", df=pd.DataFrame(st.session_state.trace))
            st.download_button("📥 اضغط هنا لتحميل PDF", pdf.output(), "LL1_Report_V6.pdf", "application/pdf")
        except Exception as e:
            st.error(f"حدث خطأ في المكتبة: {str(e)}")

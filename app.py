import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import io
import os
from fpdf import FPDF

# 1. إعدادات الواجهة (RTL) وتنسيق الجداول لمنع "النقاط"
st.set_page_config(page_title="LL(1) Compiler Studio V6.2", layout="wide")
st.markdown("""
    <style>
    .main { direction: RTL; text-align: right; }
    [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    /* منع تحول الرموز الرياضية إلى قوائم نقطية في جداول ستريمليت */
    .stTable td { white-space: pre !important; font-family: 'Courier New', monospace !important; }
    .header-box { background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-right: 5px solid #ff4b4b; margin-bottom: 20px; }
    .status-accepted { background-color: #2e7d32; color: white; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# 2. فئة PDF المحدثة (إصلاح توافق البيانات والخطوط)
class AcademicPDF(FPDF):
    def __init__(self):
        super().__init__()
        # التأكد من وجود ملف الخط في المستودع (كما في image_f76eb5.png)
        if os.path.exists("DejaVuSans.ttf"):
            self.add_font("DejaVu", "", "DejaVuSans.ttf")
            self.font_to_use = "DejaVu"
        else:
            self.font_to_use = "Arial"

    def header(self):
        self.set_font(self.font_to_use, '', 12)
        self.cell(0, 10, 'LL(1) Analysis Report - University of Misan', 0, 1, 'C')
        self.ln(5)

    def add_section(self, title, df=None, grammar=None):
        self.set_font(self.font_to_use, '', 11)
        self.set_fill_color(240, 242, 246)
        self.cell(0, 10, title, 1, 1, 'L', fill=True)
        self.ln(2)
        self.set_font(self.font_to_use, '', 9)
        if grammar:
            for k, v in grammar.items():
                line = f"{k} -> {' | '.join([' '.join(p) for p in v])}"
                self.cell(0, 8, line, 0, 1)
        if df is not None:
            col_width = self.epw / len(df.columns)
            for col in df.columns: self.cell(col_width, 8, str(col), 1, 0, 'C')
            self.ln()
            for row in df.values:
                for datum in row: self.cell(col_width, 8, str(datum), 1, 0, 'C')
                self.ln()
        self.ln(5)

# 3. محرك القواعد (إزالة التكرار الأيسر)
def clean_grammar(grammar):
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

def get_ff(grammar):
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

# 4. لوحة التحكم والمدخلات
with st.sidebar:
    st.header("⚙️ الإعدادات")
    raw_in = st.text_area("أدخل القواعد:", "E -> T E'\nE' -> + T E' | ε\nT -> F T'\nT' -> * F T' | ε\nF -> ( E ) | id", height=200)
    sentence = st.text_input("الجملة (مثال: id + id $):", "id + id * id $")
    if st.button("🔄 إعادة ضبط"):
        st.session_state.clear()
        st.rerun()

# 5. المعالجة والعرض
grammar = OrderedDict()
for line in raw_in.strip().split('\n'):
    if '->' in line:
        lhs, rhs = line.split('->')
        grammar[lhs.strip()] = [p.strip().split() for p in rhs.split('|')]

if grammar:
    fixed_g = clean_grammar(grammar)
    f_sets, fo_sets = get_ff(fixed_g)
    
    # 5.1 القواعد المصححة
    st.markdown('<div class="header-box"><h3>1️⃣ القواعد المصححة (Corrected Grammar)</h3></div>', unsafe_allow_html=True)
    for k, v in fixed_g.items():
        st.markdown(f"**{k}** → {' | '.join([' '.join(p) for p in v])}")

    # 5.2 جداول First & Follow
    st.markdown('<div class="header-box"><h3>2️⃣ جداول First & Follow</h3></div>', unsafe_allow_html=True)
    ff_df = pd.DataFrame({
        "First Set": [str(f_sets[n]) for n in fixed_g],
        "Follow Set": [str(fo_sets[n]) for n in fixed_g]
    }, index=fixed_g.keys())
    st.table(ff_df)

    # 5.3 جدول التنبؤ (M-Table)
    terms = sorted(list({s for ps in fixed_g.values() for p in ps for s in p if s not in fixed_g and s != 'ε'})) + ['$']
    m_table = pd.DataFrame("", index=fixed_g.keys(), columns=terms)
    for nt, prods in fixed_g.items():
        for p in prods:
            pf = set()
            for s in p:
                sf = f_sets[s] if s in fixed_g else {s}; pf.update(sf - {'ε'})
                if 'ε' not in sf: break
            else: pf.add('ε')
            for a in pf:
                if a != 'ε': m_table.at[nt, a] = f"{nt}->{' '.join(p)}"
            if 'ε' in pf:
                for b in fo_sets[nt]: m_table.at[nt, b] = f"{nt}->{' '.join(p)}"
    
    st.subheader("📊 جدول التنبؤ (Parsing Table)")
    st.dataframe(m_table, use_container_width=True)

    # 6. المحاكاة (إصلاح مشكلة الرموز والاقتباسات)
    st.markdown('<div class="header-box"><h3>3️⃣ تتبع الجملة (Simulation Trace)</h3></div>', unsafe_allow_html=True)
    if 'step' not in st.session_state:
        st.session_state.update({'step': 0, 'stack': [('$', '0'), (list(fixed_g.keys())[0], '0')], 'trace': [], 'dot': Digraph(), 'done': False, 'n_id': 0})
        st.session_state.dot.node('0', list(fixed_g.keys())[0], style='filled', fillcolor='lightblue')

    def run_simulation():
        s = st.session_state
        if s.done or not s.stack: return
        tokens = sentence.split(); idx = sum(1 for x in s.trace if "Match" in x['Action'])
        look = tokens[idx] if idx < len(tokens) else '$'
        top, pid = s.stack.pop()
        
        # إضافة مسافة قبل الرمز لمنع تحوله لنقطة في جدول ستريمليت
        clean_input = " " + " ".join(tokens[idx:])
        step_data = {"Stack": " ".join([v for v, i in s.stack] + [top]), "Input": clean_input, "Action": ""}

        if top == look:
            step_data["Action"] = f"Match {look}"
            if top == '$': s.done, s.status = True, "Accepted"
        elif top in fixed_g:
            rule = m_table.at[top, look]
            if rule:
                step_data["Action"] = f"Apply {rule}"
                rhs = rule.split('->')[1].split()
                if rhs == ['ε']:
                    nid = f"e_{pid}_{s.n_id}"; s.dot.node(nid, "ε", shape='plaintext'); s.dot.edge(pid, nid)
                else:
                    temp = []
                    for sym in rhs:
                        s.n_id += 1; nid = str(s.n_id)
                        # إزالة الاقتباسات من العقد
                        s.dot.node(nid, sym, style='filled', fillcolor='lightgreen')
                        s.dot.edge(pid, nid)
                        temp.append((sym, nid))
                    for item in reversed(temp): s.stack.append(item)
            else:
                step_data["Action"] = "❌ Error"; s.done, s.status = True, "Rejected"
        else:
            step_data["Action"] = "❌ Error"; s.done, s.status = True, "Rejected"
        s.trace.append(step_data)

    c1, c2 = st.columns(2)
    if c1.button("⏭ خطوة تالية"): run_simulation()
    if c2.button("▶ تشغيل كامل"):
        while not st.session_state.done: run_simulation()

    if st.session_state.trace:
        st.table(pd.DataFrame(st.session_state.trace))
        st.graphviz_chart(st.session_state.dot)
        if st.session_state.done:
            st.markdown(f'<div class="status-accepted">{st.session_state.status}</div>', unsafe_allow_html=True)

    # 7. التصدير المحدث (PDF & Excel)
    st.markdown('<div class="header-box"><h3>4️⃣ تصدير النتائج</h3></div>', unsafe_allow_html=True)
    col_pdf, col_xls = st.columns(2)
    
    with col_pdf:
        if st.button("📄 تحميل تقرير PDF"):
            try:
                pdf = AcademicPDF(); pdf.add_page()
                pdf.add_section("1. Corrected Grammar", grammar=fixed_g)
                pdf.add_section("2. First & Follow Sets", df=ff_df.reset_index())
                pdf.add_section("3. Parsing Table", df=m_table.reset_index())
                if st.session_state.trace:
                    pdf.add_section("4. Execution Trace", df=pd.DataFrame(st.session_state.trace))
                
                # الحل النهائي لخطأ bytearray: التحويل الصريح لـ bytes
                pdf_bytes = bytes(pdf.output())
                st.download_button("📥 حفظ بصيغة PDF", pdf_bytes, "Compiler_Report.pdf", "application/pdf")
            except Exception as e:
                st.error(f"خطأ في الـ PDF: {str(e)}")

    with col_xls:
        # إضافة زر الإكسل المفقود
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            ff_df.to_excel(writer, sheet_name='Sets')
            m_table.to_excel(writer, sheet_name='M_Table')
            if st.session_state.trace:
                pd.DataFrame(st.session_state.trace).to_excel(writer, sheet_name='Trace', index=False)
        st.download_button("📥 تحميل ملف Excel", buffer.getvalue(), "Compiler_Data.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

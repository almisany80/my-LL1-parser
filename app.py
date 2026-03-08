import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import re
import time
import io
from fpdf import FPDF # مكتبة توليد PDF

# --- 1. إعدادات الصفحة والتنسيق ---
st.set_page_config(page_title="LL(1) Academic Studio", layout="wide")

st.markdown("""
    <style>
    .main { direction: RTL; text-align: right; }
    [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    .ltr-text { direction: LTR !important; text-align: left !important; display: inline-block; }
    .stTable, .stDataFrame { direction: LTR !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. وظائف العرض الأكاديمي والتحليل ---

def display_academic_grammar(grammar_dict):
    """تحويل القاموس البرمجي إلى شكل رياضي أكاديمي"""
    lines = []
    for nt, prods in grammar_dict.items():
        formatted_prods = " | ".join([" ".join(p) for p in prods])
        lines.append(f"**{nt}** &nbsp; → &nbsp; {formatted_prods}")
    return lines

def auto_fix_grammar(grammar):
    temp_g = OrderedDict()
    for nt, prods in grammar.items():
        rec = [p[1:] for p in prods if p and p[0] == nt]
        non_rec = [p for p in prods if not (p and p[0] == nt)]
        if rec:
            new_nt = f"{nt}'"
            temp_g[nt] = [p + [new_nt] for p in non_rec] if non_rec else [[new_nt]]
            temp_g[new_nt] = [p + [new_nt] for p in rec] + [['ε']]
        else: temp_g[nt] = prods
    
    final_g = OrderedDict()
    for nt, prods in temp_g.items():
        if len(prods) <= 1: final_g[nt] = prods; continue
        prefixes = {}
        for p in prods:
            f = p[0] if p else 'ε'
            if f not in prefixes: prefixes[f] = []
            prefixes[f].append(p)
        if any(len(v) > 1 for k, v in prefixes.items() if k != 'ε'):
            final_g[nt] = []
            for f, p_list in prefixes.items():
                if len(p_list) > 1 and f != 'ε':
                    new_nt = f"{nt}_f"
                    final_g[nt].append([f, new_nt])
                    final_g[new_nt] = [p[1:] if len(p) > 1 else ['ε'] for p in p_list]
                else: final_g[nt].extend(p_list)
        else: final_g[nt] = prods
    return final_g

def get_analysis_sets(grammar):
    first = {nt: set() for nt in grammar}
    def calc_f(s):
        if not s or (s not in grammar and s != 'ε'): return {s}
        if s == 'ε': return {'ε'}
        res = set()
        for p in grammar.get(s, []):
            for char in p:
                cf = calc_f(char)
                res.update(cf - {'ε'})
                if 'ε' not in cf: break
            else: res.add('ε')
        return res
    for nt in grammar: first[nt] = calc_f(nt)
    start = list(grammar.keys())[0] if grammar else ""
    follow = {nt: set() for nt in grammar}; follow[start].add('$')
    for _ in range(5):
        for nt, prods in grammar.items():
            for p in prods:
                for i, sym in enumerate(p):
                    if sym in grammar:
                        next_p = p[i+1:]
                        if next_p:
                            fn = set()
                            for s in next_p:
                                sf = first[s] if s in grammar else {s}
                                fn.update(sf - {'ε'})
                                if 'ε' not in sf: break
                            else: fn.add('ε')
                            follow[sym].update(fn - {'ε'})
                            if 'ε' in fn: follow[sym].update(follow[nt])
                        else: follow[sym].update(follow[nt])
    return first, follow

def build_m_table(grammar, first, follow):
    terms = sorted(list({s for ps in grammar.values() for p in ps for s in p if s not in grammar and s != 'ε'}))
    if '$' in terms: terms.remove('$')
    terms.append('$')
    table = {nt: {t: "" for t in terms} for nt in grammar}
    for nt, prods in grammar.items():
        for p in prods:
            pf = set()
            for s in p:
                sf = first[s] if s in grammar else {s}
                pf.update(sf - {'ε'})
                if 'ε' not in sf: break
            else: pf.add('ε')
            for a in pf:
                if a != 'ε' and a in table[nt]: table[nt][a] = f"{nt} -> {' '.join(p)}"
            if 'ε' in pf:
                for b in follow[nt]:
                    if b in table[nt]: table[nt][b] = f"{nt} -> {' '.join(p)}"
    return pd.DataFrame(table).T[terms]

# --- 3. وظيفة توليد تقرير PDF الأكاديمي ---

class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'LL(1) Predictive Parsing Academic Report', 0, 1, 'C')
        self.ln(5)

    def chapter_title(self, label):
        self.set_font('Arial', 'B', 12)
        self.set_fill_color(200, 220, 255)
        self.cell(0, 10, label, 0, 1, 'L', True)
        self.ln(4)

    def add_grammar_section(self, title, grammar_dict):
        self.chapter_title(title)
        self.set_font('Courier', '', 11)
        for nt, prods in grammar_dict.items():
            formatted = " | ".join([" ".join(p) for p in prods])
            self.cell(0, 8, f"{nt} -> {formatted}", 0, 1)
        self.ln(5)

    def add_table(self, df, title):
        self.chapter_title(title)
        self.set_font('Arial', 'B', 10)
        # تحديد عرض الأعمدة تلقائياً
        col_width = self.epw / (len(df.columns) + 1)
        # رأس الجدول
        self.cell(col_width, 10, 'NT', 1)
        for col in df.columns: self.cell(col_width, 10, str(col), 1)
        self.ln()
        # محتوى الجدول
        self.set_font('Arial', '', 9)
        for i, row in df.iterrows():
            if self.get_y() > 250: self.add_page() # حماية فواصل الصفحات
            self.cell(col_width, 8, str(i), 1)
            for val in row: self.cell(col_width, 8, str(val), 1)
            self.ln()
        self.ln(5)

# --- 4. واجهة التطبيق ---

with st.sidebar:
    st.header("📥 إدخال القواعد")
    raw_input = st.text_area("القواعد الأصلية:", "E → E + T | T\nT → T * F | F\nF → ( E ) | id", height=150)
    speed = st.slider("⏱️ سرعة المحاكاة:", 0.1, 2.0, 0.5)

grammar_raw = {}
for line in raw_input.split('\n'):
    if '→' in line or '->' in line:
        parts = re.split(r'→|->|=', line)
        grammar_raw[parts[0].strip()] = [p.strip().split() for p in parts[1].split('|')]

if grammar_raw:
    # 1. القواعد المصححة
    st.header("1️⃣ القواعد المصححة (Academic View)")
    fixed_g = auto_fix_grammar(grammar_raw)
    with st.container():
        for line in display_academic_grammar(fixed_g):
            st.markdown(f'<div class="ltr-text">{line}</div>', unsafe_allow_html=True)

    # 2 & 3. الحسابات
    f_sets, fo_sets = get_analysis_sets(fixed_g)
    ff_df = pd.DataFrame({
        "First": [", ".join(list(s)) for s in f_sets.values()],
        "Follow": [", ".join(list(s)) for s in fo_sets.values()]
    }, index=f_sets.keys())
    
    st.header("2️⃣ مجموعات First & Follow")
    st.table(ff_df)

    st.header("3️⃣ مصفوفة الإعراب (M-Table)")
    m_table = build_m_table(fixed_g, f_sets, fo_sets)
    st.dataframe(m_table, use_container_width=True)

    # 4 & 5. المحاكاة
    st.header("4️⃣ & 5️⃣ المحاكاة والشجرة")
    user_input = st.text_input("الجملة:", "id + id * id")
    tokens = user_input.split() + ['$']

    if 'sim' not in st.session_state:
        st.session_state.sim = {'stack': [], 'idx': 0, 'dot': Digraph(), 'trace': [], 'done': False, 'node_id': 0}

    col_btn1, col_btn2 = st.columns(2)
    if col_btn1.button("🔄 ضبط / إعادة تعيين"):
        start = list(fixed_g.keys())[0]
        st.session_state.sim = {'stack': [('$', 0), (start, 0)], 'idx': 0, 'dot': Digraph(), 'trace': [], 'done': False, 'node_id': 0}
        st.session_state.sim['dot'].attr(rankdir='TD')
        st.session_state.sim['dot'].node("0", start, style='filled', fillcolor="#BBDEFB")
        st.rerun()

    tree_area = st.empty()
    trace_area = st.empty()

    if col_btn2.button("▶️ تشغيل تلقائي"):
        s = st.session_state.sim
        while not s['done']:
            if s['stack']:
                top, pid = s['stack'].pop()
                look = tokens[s['idx']]
                step = {"Stack": " ".join([x for x, i in s['stack'] + [(top, pid)]]), "Input": " ".join(tokens[s['idx']:]), "Action": ""}
                
                if top == look:
                    step["Action"] = f"Match {look}"
                    s['idx'] += 1
                elif top in fixed_g:
                    rule = m_table.at[top, look]
                    if rule:
                        rhs = rule.split('->')[1].strip().split()
                        new_nodes = []
                        for sym in rhs:
                            s['node_id'] += 1
                            nid = s['node_id']
                            s['dot'].node(str(nid), sym, style='filled', fillcolor="#C8E6C9" if sym in fixed_g else "#FFF9C4")
                            s['dot'].edge(str(pid), str(nid))
                            if sym != 'ε': new_nodes.append((sym, nid))
                        for n in reversed(new_nodes): s['stack'].append(n)
                        step["Action"] = f"Apply {rule}"
                if not s['stack'] or (top == '$' and look == '$'): s['done'] = True
                s['trace'].append(step)
                tree_area.graphviz_chart(s['dot'])
                trace_area.table(pd.DataFrame(s['trace']))
                time.sleep(speed)
            else: break

    # 6. التقرير النهائي (Excel + PDF)
    st.header("6️⃣ تحميل التقارير النهائية")
    col_dl1, col_dl2 = st.columns(2)
    
    with col_dl1:
        # Excel
        out_ex = io.BytesIO()
        with pd.ExcelWriter(out_ex, engine='openpyxl') as writer:
            ff_df.to_excel(writer, sheet_name='Analysis')
            m_table.to_excel(writer, sheet_name='M_Table')
        st.download_button("📥 تحميل التقرير (Excel)", out_ex.getvalue(), "LL1_Report.xlsx")

    with col_dl2:
        # PDF
        if st.button("📄 توليد تقرير PDF"):
            pdf = PDFReport()
            pdf.add_page()
            pdf.add_grammar_section("Original Grammar", grammar_raw)
            pdf.add_grammar_section("Corrected Grammar", fixed_g)
            pdf.add_table(ff_df, "First & Follow Sets")
            pdf.add_table(m_table, "Predictive Parsing Table (M-Table)")
            if st.session_state.sim['trace']:
                pdf.add_table(pd.DataFrame(st.session_state.sim['trace']), "Parsing Trace Steps")
            
            # إضافة الشجرة كصورة (تتطلب حفظ مؤقت)
            if st.session_state.sim['node_id'] > 0:
                pdf.chapter_title("Final Parse Tree")
                img_data = st.session_state.sim['dot'].pipe(format='png')
                pdf.image(io.BytesIO(img_data), w=pdf.epw)
                
            st.download_button("📥 تحميل التقرير (PDF)", pdf.output(), "LL1_Academic_Report.pdf")


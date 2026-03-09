import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import re
import time
import io
import os
from fpdf import FPDF

# 1. التنسيق العام (RTL) --- #
st.set_page_config(page_title="LL(1) Academic Ultimate", layout="wide")
st.markdown("""
    <style>
    .main { direction: RTL; text-align: right; }
    [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    .ltr-table { direction: LTR !important; text-align: left !important; font-family: sans-serif; }
    .status-accepted { background-color: #2e7d32; color: white; padding: 15px; border-radius: 8px; text-align: center; font-size: 20px; }
    .status-rejected { background-color: #c62828; color: white; padding: 15px; border-radius: 8px; text-align: center; font-size: 20px; }
    .grammar-box { background-color: #f0f2f6; padding: 10px; border-radius: 5px; border-right: 5px solid #ff4b4b; margin: 10px 0; }
    </style>
    """, unsafe_allow_html=True)

LEVEL_COLORS = ["#BBDEFB", "#C8E6C9", "#FFF9C4", "#F8BBD0", "#E1BEE7", "#B2EBF2"]

# 2. محركات التصحيح والتحليل (Advanced Grammar Engines) --- #
def remove_left_recursion(grammar):
    new_grammar = OrderedDict()
    for nt, prods in grammar.items():
        recursive = [p[1:] for p in prods if p and p[0] == nt]
        non_recursive = [p for p in prods if not (p and p[0] == nt)]
        
        if recursive:
            new_nt = f"{nt}'"
            new_grammar[nt] = [p + [new_nt] for p in non_recursive] if non_recursive else [[new_nt]]
            new_grammar[new_nt] = [p + [new_nt] for p in recursive] + [['ε']]
        else:
            new_grammar[nt] = prods
    return new_grammar

def apply_left_factoring(grammar):
    new_grammar = OrderedDict()
    for nt, prods in grammar.items():
        if len(prods) <= 1:
            new_grammar[nt] = prods
            continue
        
        prods.sort()
        prefix = os.path.commonprefix([tuple(p) for p in prods])
        
        if prefix:
            new_nt = f"{nt}f"
            prefix = list(prefix)
            new_grammar[nt] = [prefix + [new_nt]]
            suffix = [p[len(prefix):] if p[len(prefix):] else ['ε'] for p in prods]
            new_grammar[new_nt] = suffix
        else:
            new_grammar[nt] = prods
    return new_grammar

def get_first_follow(grammar):
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

    for _ in range(len(grammar)):
        for nt in grammar:
            for prod in grammar[nt]:
                first[nt].update(get_seq_first(prod))

    start = list(grammar.keys())[0]
    follow = {nt: set() for nt in grammar}
    follow[start].add('$')
    for _ in range(len(grammar)):
        for nt, prods in grammar.items():
            for p in prods:
                for i, B in enumerate(p):
                    if B in grammar:
                        beta = p[i+1:]
                        fb = get_seq_first(beta)
                        follow[B].update(fb - {'ε'})
                        if 'ε' in fb: follow[B].update(follow[nt])
    return first, follow

# 3. محرك تقارير PDF --- #
class AcademicPDF(FPDF):
    def __init__(self):
        super().__init__()
        if os.path.exists("DejaVuSans.ttf"):
            self.add_font("DejaVu", "", "DejaVuSans.ttf")
            self.f_name = "DejaVu"
        else:
            self.f_name = "Arial"

    def header(self):
        self.set_font(self.f_name, "", 14)
        self.cell(0, 10, "LL(1) Parser Report", ln=True, align="C")
        self.ln(5)

    def add_section(self, title, df=None, grammar=None):
        self.set_font(self.f_name, "", 12)
        self.set_fill_color(230, 230, 230)
        _ = self.cell(0, 10, f" {title}", ln=True, fill=True)
        self.ln(2)
        if grammar:
            self.set_font(self.f_name, "", 10)
            for k, v in grammar.items():
                _ = self.cell(0, 8, f"{k} -> {' | '.join([' '.join(p) for p in v])}", ln=True)
        elif df is not None:
            self.set_font(self.f_name, "", 8)
            cols = list(df.columns)
            cw = self.epw / (len(cols) + (0 if "Stack" in cols else 1))
            if "Stack" not in cols: _ = self.cell(cw, 8, "NT", 1, 0, 'C')
            for c in cols: _ = self.cell(cw, 8, str(c), 1, 0, 'C')
            self.ln()
            for _, r in df.iterrows():
                if self.get_y() > 250: self.add_page()
                if "Stack" not in cols: _ = self.cell(cw, 7, str(r.name), 1, 0, 'C')
                for v in r: _ = self.cell(cw, 7, str(v), 1, 0, 'L')
                self.ln()
        self.ln(5)

# 4. واجهة المستخدم --- #
with st.sidebar:
    st.header("⚙️ المدخلات")
    raw_in = st.text_area("أدخل القواعد:", "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id", height=150)
    speed = st.slider("سرعة المحاكاة:", 0.1, 2.0, 0.5)

grammar_raw = OrderedDict()
for line in raw_in.split('\n'):
    if '->' in line:
        lhs, rhs = line.split('->')
        grammar_raw[lhs.strip()] = [opt.strip().split() for opt in rhs.split('|')]

if grammar_raw:
    # خطوة التحقق والتصحيح
    st.header("1️⃣ التحقق والتصحيح (Verification)")
    g_step1 = remove_left_recursion(grammar_raw)
    fixed_g = apply_left_factoring(g_step1)
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("القواعد الأصلية:")
        for k, v in grammar_raw.items():
            st.markdown(f'<div class="grammar-box ltr-table">{k} → {" | ".join([" ".join(p) for p in v])}</div>', unsafe_allow_html=True)
    with col_b:
        st.subheader("القواعد المصححة:")
        for k, v in fixed_g.items():
            st.markdown(f'<div class="grammar-box ltr-table" style="border-right-color:#2e7d32">{k} → {" | ".join([" ".join(p) for p in v])}</div>', unsafe_allow_html=True)

    # حساب First & Follow
    f_sets, fo_sets = get_first_follow(fixed_g)
    ff_df = pd.DataFrame({
        "First": [", ".join(sorted(list(s))) for s in f_sets.values()],
        "Follow": [", ".join(sorted(list(s))) for s in fo_sets.values()]
    }, index=f_sets.keys())

    # بناء M-Table
    terms = sorted(list({s for ps in fixed_g.values() for p in ps for s in p if s not in fixed_g and s != 'ε'})) + ['$']
    m_table = pd.DataFrame("", index=fixed_g.keys(), columns=terms)
    for nt, prods in fixed_g.items():
        for p in prods:
            first_p = set()
            for s in p:
                sf = f_sets[s] if s in fixed_g else {s}
                first_p.update(sf - {'ε'})
                if 'ε' not in sf: break
            else: first_p.add('ε')
            for a in first_p:
                if a != 'ε': m_table.at[nt, a] = f"{nt} -> {' '.join(p)}"
            if 'ε' in first_p:
                for b in fo_sets[nt]: m_table.at[nt, b] = f"{nt} -> {' '.join(p)}"

    st.header("2️⃣ جداول مجموعات First & Follow")
    st.markdown('<div class="ltr-table">', unsafe_allow_html=True)
    st.table(ff_df)
    st.header("3️⃣ مصفوفة الإعراب (M-Table)")
    st.dataframe(m_table, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.header("4️⃣ & 5️⃣ تتبع الجملة ورسم الشجرة التفاعلية")
    u_input = st.text_input("أدخل الجملة:", "id + id * id $")
    if 'sim' not in st.session_state: st.session_state.sim = {'trace': [], 'dot': None}

    if st.button("▶ تشغيل"):
        tokens, idx, node_id, trace = u_input.split(), 0, 0, []
        stack = [('$', '0'), (list(fixed_g.keys())[0], '0')]
        dot = Digraph()
        dot.node('0', list(fixed_g.keys())[0], style='filled', fillcolor=LEVEL_COLORS[0])
        
        while stack:
            top, pid = stack.pop()
            look = tokens[idx] if idx < len(tokens) else '$'
            step = {"Stack": " ".join([s for s, i in stack] + [top]), "Input": look, "Action": ""}
            
            if top == look:
                step["Action"] = f"✅ Match {look}"; idx += 1
                if top == '$': break
            elif top in fixed_g:
                rule = m_table.at[top, look]
                if rule:
                    rhs = rule.split('->')[1].strip().split()
                    step["Action"] = f"Apply {rule}"
                    new_nodes = []
                    for sym in rhs:
                        node_id += 1; nid = str(node_id)
                        dot.node(nid, sym, style='filled', fillcolor=LEVEL_COLORS[node_id % 6])
                        dot.edge(pid, nid)
                        if sym != 'ε': new_nodes.append((sym, nid))
                    for n in reversed(new_nodes): stack.append(n)
                else: step["Action"] = "❌ Error"; trace.append(step); break
            else: step["Action"] = "❌ Error"; trace.append(step); break
            trace.append(step)
        st.session_state.sim = {'trace': trace, 'dot': dot}

    if st.session_state.sim['trace']:
        st.markdown('<div class="ltr-table">', unsafe_allow_html=True)
        st.table(pd.DataFrame(st.session_state.sim['trace']))
        st.markdown('</div>', unsafe_allow_html=True)
        st.graphviz_chart(st.session_state.sim['dot'])

    st.header("6️⃣ تحميل التقارير")
    cp, cx = st.columns(2)
    with cp:
        if st.button("📄 PDF"):
            pdf = AcademicPDF(); pdf.add_page()
            pdf.add_section("1. Original Grammar", grammar=grammar_raw)
            pdf.add_section("2. Fixed Grammar", grammar=fixed_g)
            pdf.add_section("3. First & Follow", df=ff_df)
            pdf.add_section("4. M-Table", df=m_table)
            if st.session_state.sim['trace']:
                pdf.add_section("5. Trace", df=pd.DataFrame(st.session_state.sim['trace']))
                pdf.add_page(); pdf.image(io.BytesIO(st.session_state.sim['dot'].pipe(format='png')), w=pdf.epw)
            st.download_button("📥 تحميل PDF", bytes(pdf.output()), "Report.pdf")
    with cx:
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as w:
            ff_df.to_excel(w, sheet_name='Sets')
            m_table.to_excel(w, sheet_name='M_Table')
            if st.session_state.sim['trace']: pd.DataFrame(st.session_state.sim['trace']).to_excel(w, sheet_name='Trace', index=False)
        st.download_button("📥 تحميل Excel", out.getvalue(), "Data.xlsx")







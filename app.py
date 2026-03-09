import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import re
import time
import io
import os
import copy
from fpdf import FPDF

# --- 1. التنسيق العام (RTL) ---
st.set_page_config(page_title="LL(1) Ultimate Academic Studio", layout="wide")

st.markdown("""
    <style>
    .main { direction: RTL; text-align: right; }
    [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    .ltr-text { direction: LTR !important; text-align: left !important; font-family: 'Courier New', monospace; font-size: 18px; }
    .stTable, .stDataFrame { direction: LTR !important; text-align: left !important; }
    .status-accepted { background-color: #2e7d32; color: white; padding: 20px; border-radius: 10px; text-align: center; font-size: 24px; font-weight: bold; margin: 20px 0; }
    .status-rejected { background-color: #c62828; color: white; padding: 20px; border-radius: 10px; text-align: center; font-size: 24px; font-weight: bold; margin: 20px 0; }
    </style>
    """, unsafe_allow_html=True)

# ألوان مستويات الشجرة
LEVEL_COLORS = ["#BBDEFB", "#C8E6C9", "#FFF9C4", "#F8BBD0", "#E1BEE7", "#B2EBF2", "#FFE0B2", "#D7CCC8"]

# --- 2. محركات التصحيح والتحليل المنطقي ---

def auto_fix_grammar(grammar):
    temp_g = OrderedDict()
    for nt, prods in grammar.items():
        rec = [p[1:] for p in prods if p and p[0] == nt]
        non_rec = [p for p in prods if not (p and p[0] == nt)]
        if rec:
            new_nt = f"{nt}p"
            temp_g[nt] = [p + [new_nt] for p in non_rec] if non_rec else [[new_nt]]
            temp_g[new_nt] = [p + [new_nt] for p in rec] + [['ε']]
        else: temp_g[nt] = prods
    return temp_g

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

    changed = True
    while changed:
        changed = False
        for nt in grammar:
            old = len(first[nt])
            for prod in grammar[nt]: first[nt].update(get_seq_first(prod))
            if len(first[nt]) > old: changed = True

    start = list(grammar.keys())[0]
    follow = {nt: set() for nt in grammar}; follow[start].add('$')
    changed = True
    while changed:
        changed = False
        for nt, prods in grammar.items():
            for p in prods:
                for i in range(len(p)):
                    B = p[i]
                    if B in grammar:
                        old = len(follow[B])
                        beta = p[i+1:]
                        if beta:
                            fb = get_seq_first(beta)
                            follow[B].update(fb - {'ε'})
                            if 'ε' in fb: follow[B].update(follow[nt])
                        else: follow[B].update(follow[nt])
                        if len(follow[B]) > old: changed = True
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
                if a != 'ε' and a in table[nt]: table[nt][a] = f"{nt} → {' '.join(p)}"
            if 'ε' in pf:
                for b in follow[nt]: 
                    if b in table[nt]: table[nt][b] = f"{nt} → {' '.join(p)}"
    return pd.DataFrame(table).T[terms]

# --- 3. محرك تقارير PDF العبقري ---

class AcademicPDF(FPDF):
    def __init__(self):
        super().__init__()
        # تم تعديل السطر التالي لإزالة unicode=True وحل مشكلة TypeError
        if os.path.exists("DejaVuSans.ttf"):
            self.add_font("DejaVu", "", "DejaVuSans.ttf")
            self.f_name = "DejaVu"
        else: 
            self.f_name = "Arial"

    def header(self):
        self.set_font(self.f_name, "", 16)
        self.cell(0, 10, "LL(1) Predictive Parsing Academic Report", ln=True, align="C")
        self.ln(10)

    def add_section(self, title, df=None, grammar=None):
        self.set_font(self.f_name, "", 12)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 10, title, ln=True, fill=True)
        self.ln(2)
        if grammar:
            self.set_font(self.f_name, "", 10)
            for k, v in grammar.items():
                line = f"{k} -> {' | '.join([' '.join(p) for p in v])}"
                self.cell(0, 8, line, ln=True)
        elif df is not None:
            self.set_font(self.f_name, "", 8)
            cw = self.epw / (len(df.columns) + 1)
            self.cell(cw, 8, "NT", 1); [self.cell(cw, 8, str(c), 1) for c in df.columns]; self.ln()
            for i, r in df.iterrows():
                if self.get_y() > 250: self.add_page()
                self.cell(cw, 7, str(i), 1); [self.cell(cw, 7, str(v), 1) for v in r]; self.ln()
        self.ln(5)

# --- 4. واجهة المستخدم والمحاكاة ---

with st.sidebar:
    st.header("📥 إدخال القواعد 🤖")
    raw_in = st.text_area("أدخل القواعد:", "E → E + T | T\nT → T * F | F\nF → ( E ) | id", height=150)
    speed = st.slider("⏱️ سرعة المحاكاة:", 0.1, 1.5, 0.5)

# معالجة القواعد
grammar_raw = OrderedDict()
for line in raw_in.split('\n'):
    line = line.strip()
    if '→' in line or '->' in line:
        ps = re.split(r'→|->|=', line)
        if len(ps) == 2:
            lhs = ps[0].strip()
            grammar_raw[lhs] = [opt.strip().split() for opt in ps[1].split('|')]

if grammar_raw:
    # 1. القواعد وتصحيحها
    st.header("1️⃣ التحقق والتصحيح")
    fixed_g = auto_fix_grammar(grammar_raw)
    for nt, prods in fixed_g.items():
        st.markdown(f'<div class="ltr-text">{nt} → {" | ".join([" ".join(p) for p in prods])}</div>', unsafe_allow_html=True)

    # 2 & 3. الحسابات والجداول
    f_sets, fo_sets = get_first_follow(fixed_g)
    ff_df = pd.DataFrame({
        "First": [", ".join(sorted(list(s))) for s in f_sets.values()], 
        "Follow": [", ".join(sorted(list(s))) for s in fo_sets.values()]
    }, index=f_sets.keys())
    
    st.header("2️⃣ & 3️⃣ الجداول (First, Follow, M-Table)")
    st.table(ff_df)
    m_table = build_m_table(fixed_g, f_sets, fo_sets)
    st.dataframe(m_table, use_container_width=True)

    # 4 & 5. المحاكاة والشجرة
    st.header("4️⃣ & 5️⃣ المحاكاة والشجرة")
    u_input = st.text_input("أدخل الجملة:", "id + id * id $")
    
    if 'sim' not in st.session_state:
        st.session_state.sim = {'stack': [], 'idx': 0, 'dot': Digraph(), 'trace': [], 'done': False, 'node_id': 0, 'lvl': {0:0}}

    c1, c2, c3 = st.columns(3)
    if c1.button("🔄 ضبط"):
        start = list(fixed_g.keys())[0]
        st.session_state.sim = {'stack': [('$', 0), (start, 0)], 'idx': 0, 'dot': Digraph(), 'trace': [], 'done': False, 'node_id': 0, 'lvl': {0:0}}
        st.session_state.sim['dot'].attr(rankdir='TD')
        st.session_state.sim['dot'].node("0", start, style='filled', fillcolor=LEVEL_COLORS[0])
        st.rerun()

    if c2.button("▶️ تشغيل تلقائي"):
        if "$" not in u_input:
            st.warning("⚠️ تنبيه: يجب كتابة رمز ($) في نهاية الجملة.")
        else:
            tokens = u_input.split()
            s = st.session_state.sim
            # تهيئة الحالة إذا كانت فارغة
            if not s['stack']:
                start = list(fixed_g.keys())[0]
                s['stack'] = [('$', 0), (start, 0)]
                s['dot'].node("0", start, style='filled', fillcolor=LEVEL_COLORS[0])

            placeholder = st.empty()
            
            while not s['done']:
                if s['stack']:
                    top, pid = s['stack'].pop()
                    look = tokens[s['idx']] if s['idx'] < len(tokens) else '$'
                    
                    if top == look:
                        if top == '$': 
                            s['done'] = True
                            st.success("✅ الجملة مقبولة!")
                        s['idx'] += 1
                    elif top in fixed_g:
                        prod_str = m_table.loc[top, look] if look in m_table.columns else ""
                        if prod_str:
                            rhs = prod_str.split('→')[1].strip().split()
                            for symbol in reversed(rhs):
                                if symbol != 'ε':
                                    s['node_id'] += 1
                                    new_id = str(s['node_id'])
                                    s['stack'].append((symbol, new_id))
                                    s['dot'].node(new_id, symbol)
                                    s['dot'].edge(str(pid), new_id)
                        else:
                            st.error("❌ الجملة مرفوضة!")
                            s['done'] = True
                    
                    with placeholder.container():
                        st.graphviz_chart(s['dot'])
                    time.sleep(speed)
                else:
                    s['done'] = True

    # خيار تحميل التقرير
    if st.button("📄 توليد تقرير PDF"):
        pdf = AcademicPDF()
        pdf.add_page()
        pdf.add_section("Grammar Rules", grammar=fixed_g)
        pdf.add_section("First & Follow Sets", df=ff_df)
        pdf.add_section("Parsing Table (M-Table)", df=m_table)
        
        html = pdf.output(dest='S')
        st.download_button("تحميل التقرير", data=html, file_name="LL1_Report.pdf", mime="application/pdf")

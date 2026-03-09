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

LEVEL_COLORS = ["#BBDEFB", "#C8E6C9", "#FFF9C4", "#F8BBD0", "#E1BEE7", "#B2EBF2", "#FFE0B2", "#D7CCC8"]

# --- 2. محركات التحليل (First, Follow, M-Table) ---

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

    start = list(grammar.keys())[0] if grammar else ""
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

# --- 3. محرك تقارير PDF الأكاديمي (تم تصحيح خطأ add_font) ---

class AcademicPDF(FPDF):
    def __init__(self):
        super().__init__()
        # تصحيح: إزالة unicode=True لأن fpdf2 تتعامل معه تلقائياً
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
                line = f"{k} \u2192 {' | '.join([' '.join(p) for p in v])}"
                self.cell(0, 8, line, ln=True)
        elif df is not None:
            self.set_font(self.f_name, "", 8)
            cw = self.epw / (len(df.columns) + 1)
            self.cell(cw, 8, "NT", 1)
            for c in df.columns: self.cell(cw, 8, str(c), 1)
            self.ln()
            for i, r in df.iterrows():
                if self.get_y() > 250: self.add_page()
                self.cell(cw, 7, str(i), 1)
                for v in r: self.cell(cw, 7, str(v), 1)
                self.ln()
        self.ln(5)

# --- 4. واجهة المستخدم والمحاكاة ---

with st.sidebar:
    st.header("📥 إدخال القواعد")
    raw_in = st.text_area("أدخل القواعد:", "E → E + T | T\nT → T * F | F\nF → ( E ) | id", height=150)
    speed = st.slider("⏱️ سرعة المحاكاة:", 0.1, 1.5, 0.5)

grammar_raw = OrderedDict()
for line in raw_in.split('\n'):
    line = line.strip()
    if '→' in line or '->' in line:
        ps = re.split(r'→|->|=', line)
        if len(ps) == 2:
            lhs = ps[0].strip()
            grammar_raw[lhs] = [opt.strip().split() for opt in ps[1].split('|')]

if grammar_raw:
    st.header("1️⃣ التحليل والجداول")
    f_sets, fo_sets = get_first_follow(grammar_raw)
    ff_df = pd.DataFrame({
        "First": [", ".join(sorted(list(s))) for s in f_sets.values()],
        "Follow": [", ".join(sorted(list(s))) for s in fo_sets.values()]
    }, index=f_sets.keys())
    st.table(ff_df)
    
    m_table = build_m_table(grammar_raw, f_sets, fo_sets)
    st.dataframe(m_table, use_container_width=True)

    st.header("2️⃣ المحاكاة والشجرة")
    u_input = st.text_input("أدخل الجملة:", "id + id * id $")
    
    if 'sim' not in st.session_state:
        st.session_state.sim = {'stack': [], 'idx': 0, 'dot': Digraph(), 'trace': [], 'done': False, 'node_id': 0, 'lvl': {0:0}}

    c1, c2 = st.columns(2)
    if c1.button("🔄 ضبط"):
        start = list(grammar_raw.keys())[0]
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
            t_area, tr_area = st.empty(), st.empty()
            while not s['done']:
                if s['stack']:
                    top, pid = s['stack'].pop()
                    look = tokens[s['idx']] if s['idx'] < len(tokens) else '$'
                    step = {"المكدس": " ".join([x for x, i in s['stack'] + [(top, pid)]]), "المؤشر": look, "الإجراء": ""}
                    if top == look:
                        step["الإجراء"] = f"✅ Match {look}"; s['idx'] += 1
                        if top == '$': s['done'] = True
                    elif top in grammar_raw:
                        rule = m_table.at[top, look]
                        if rule:
                            rhs = rule.split('→')[1].strip().split()
                            curr_l = s['lvl'].get(str(pid), 0) + 1
                            new_n = []
                            for sym in rhs:
                                s['node_id'] += 1
                                nid = str(s['node_id'])
                                s['lvl'][nid] = curr_l
                                s['dot'].node(nid, sym, style='filled', fillcolor=LEVEL_COLORS[curr_l % len(LEVEL_COLORS)], shape='circle' if sym in grammar_raw else 'ellipse')
                                s['dot'].edge(str(pid), nid)
                                if sym != 'ε': new_n.append((sym, nid))
                            for n in reversed(new_n): s['stack'].append(n)
                            step["الإجراء"] = f"تطبيق {rule}"
                    if not s['stack'] or (top == '$' and look == '$'): s['done'] = True
                    s['trace'].append(step)
                    t_area.graphviz_chart(s['dot'])
                    tr_area.table(pd.DataFrame(s['trace']))
                    time.sleep(speed)
                else: s['done'] = True
            
            if s['done']:
                if s['idx'] == len(tokens):
                    st.markdown('<div class="status-accepted">الجملة مقبولة ✅</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="status-rejected">الجملة مرفوضة ❌</div>', unsafe_allow_html=True)

    # 3. التقارير
    st.header("3️⃣ تحميل التقارير")
    if st.button("📄 توليد PDF الأكاديمي"):
        pdf = AcademicPDF()
        pdf.add_page()
        pdf.add_section("Grammar", grammar=grammar_raw)
        pdf.add_section("First & Follow", df=ff_df)
        pdf.add_section("M-Table", df=m_table)
        if st.session_state.sim['trace']:
            pdf.add_section("Simulation Trace", df=pd.DataFrame(st.session_state.sim['trace']))
            pdf.add_page()
            img = st.session_state.sim['dot'].pipe(format='png')
            pdf.image(io.BytesIO(img), w=pdf.epw)
        st.download_button("📥 تحميل PDF الآن", pdf.output(), "Academic_Report.pdf")

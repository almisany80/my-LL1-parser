import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import re
import io
import os
from fpdf import FPDF

# 1. التنسيق والنمط العام (RTL Support)
st.set_page_config(page_title="LL(1) Academic Ultimate", layout="wide")
st.markdown("""
    <style>
    .main { direction: RTL; text-align: right; }
    [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    .ltr-table { direction: LTR !important; text-align: left !important; font-family: 'Consolas', monospace; }
    .status-accepted { background-color: #1b5e20; color: white; padding: 20px; border-radius: 12px; text-align: center; font-weight: bold; font-size: 20px; }
    .status-rejected { background-color: #b71c1c; color: white; padding: 20px; border-radius: 12px; text-align: center; font-weight: bold; font-size: 20px; }
    .grammar-box { background-color: #f8f9fa; padding: 12px; border-radius: 8px; border-right: 6px solid #d32f2f; margin: 10px 0; }
    </style>
    """, unsafe_allow_html=True)

LEVEL_COLORS = ["#BBDEFB", "#C8E6C9", "#FFF9C4", "#F8BBD0", "#E1BEE7", "#B2EBF2"]

# 2. وظائف المعالجة التلقائية للقواعد
def remove_left_recursion(grammar):
    new_grammar = OrderedDict()
    for nt, prods in grammar.items():
        recursive = [p[1:] for p in prods if p and p[0] == nt]
        non_recursive = [p for p in prods if not (p and p[0] == nt)]
        if recursive:
            new_nt = f"{nt}'"
            new_grammar[nt] = [p + [new_nt] for p in non_recursive] if non_recursive else [[new_nt]]
            new_grammar[new_nt] = [p + [new_nt] for p in recursive] + [['ε']]
        else: new_grammar[nt] = prods
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
            new_grammar[nt] = [list(prefix) + [new_nt]]
            suffix = [p[len(prefix):] if p[len(prefix):] else ['ε'] for p in prods]
            new_grammar[new_nt] = suffix
        else: new_grammar[nt] = prods
    return new_grammar

def get_first_follow_stable(grammar):
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
    follow = {nt: set() for nt in grammar}
    follow[list(grammar.keys())[0]].add('$')
    while True:
        changed = False
        for nt, prods in grammar.items():
            for p in prods:
                for i, B in enumerate(p):
                    if B in grammar:
                        old_len = len(follow[B])
                        beta = p[i+1:]
                        if beta:
                            fb = get_seq_first(beta)
                            follow[B].update(fb - {'ε'})
                            if 'ε' in fb: follow[B].update(follow[nt])
                        else: follow[B].update(follow[nt])
                        if len(follow[B]) > old_len: changed = True
        if not changed: break
    return first, follow

# 3. نظام التقارير المصحح
class AcademicPDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, "LL(1) Compiler Design Analysis Report", ln=True, align="C")
        self.ln(5)

    def add_section(self, title, df=None, grammar=None):
        self.set_font("Arial", "B", 11)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 10, f" {title}", ln=True, fill=True)
        self.ln(2)
        if grammar:
            self.set_font("Courier", "", 10)
            for k, v in grammar.items():
                self.cell(0, 8, f"{k} -> {' | '.join([' '.join(p) for p in v])}", ln=True)
        elif df is not None:
            self.set_font("Arial", "", 9)
            cols = list(df.columns); cw = self.epw / (len(cols) + 1)
            self.cell(cw, 8, "Key", 1, 0, 'C', True)
            for c in cols: self.cell(cw, 8, str(c), 1, 0, 'C', True)
            self.ln()
            for i, r in df.iterrows():
                self.cell(cw, 7, str(i), 1, 0, 'C')
                for v in r: self.cell(cw, 7, str(v)[:20], 1, 0, 'L')
                self.ln()
        self.ln(5)

# 4. إدارة حالة الجلسة
if 'sim' not in st.session_state:
    st.session_state.sim = {'trace': [], 'dot': None, 'status': None, 'stack': [], 'idx': 0, 'node_id': 0, 'finished': False}

# 5. بناء الواجهة
with st.sidebar:
    st.header("⚙️ مدخلات النظام")
    raw_in = st.text_area("أدخل القواعد:", "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id", height=150)
    u_input = st.text_input("الجملة (ضع مسافة بين الرموز):", "id + id * id $")
    if st.button("🔄 إعادة ضبط الإعدادات"):
        st.session_state.sim = {'trace': [], 'dot': None, 'status': None, 'stack': [], 'idx': 0, 'node_id': 0, 'finished': False}
        st.rerun()

# تحليل القواعد الأساسية
grammar_raw = OrderedDict()
for line in raw_in.split('\n'):
    if '->' in line:
        lhs, rhs = line.split('->')
        grammar_raw[lhs.strip()] = [opt.strip().split() for opt in rhs.split('|')]

if grammar_raw:
    # المعالجة الآلية للقواعد
    fixed_g = apply_left_factoring(remove_left_recursion(grammar_raw))
    f_sets, fo_sets = get_first_follow_stable(fixed_g)
    
    # عرض القواعد (الأصلية والمصححة)
    st.header("1️⃣ مراجعة القواعد (Grammar Review)")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("القواعد الأصلية")
        for k, v in grammar_raw.items(): st.markdown(f'<div class="grammar-box ltr-table">{k} → {" | ".join([" ".join(p) for p in v])}</div>', unsafe_allow_html=True)
    with c2:
        st.subheader("بعد التصحيح (Simplified)")
        for k, v in fixed_g.items(): st.markdown(f'<div class="grammar-box ltr-table" style="border-right-color:#2e7d32">{k} → {" | ".join([" ".join(p) for p in v])}</div>', unsafe_allow_html=True)

    # جداول First & Follow
    st.header("2️⃣ جداول التحليل (LL1 Sets)")
    ff_df = pd.DataFrame({
        "First": [", ".join(sorted(list(s))) for s in f_sets.values()],
        "Follow": [", ".join(sorted(list(s))) for s in fo_sets.values()]
    }, index=f_sets.keys())
    st.markdown('<div class="ltr-table">', unsafe_allow_html=True)
    st.table(ff_df)
    st.markdown('</div>', unsafe_allow_html=True)

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

    st.subheader("Predictive Parsing Table (M-Table)")
    st.markdown('<div class="ltr-table">', unsafe_allow_html=True)
    st.dataframe(m_table, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # المحاكاة والتحكم
    st.header("3️⃣ محاكاة تتبع الجملة (Parsing Simulation)")
    b1, b2 = st.columns([1, 4])
    
    if b1.button("▶ تشغيل كامل"):
        tokens = u_input.split(); stack = [('$', '0'), (list(fixed_g.keys())[0], '0')]
        idx, node_id, trace = 0, 0, []; dot = Digraph(); status = "Rejected"
        dot.node('0', list(fixed_g.keys())[0], style='filled', fillcolor=LEVEL_COLORS[0])
        while stack:
            top, pid = stack.pop(); look = tokens[idx] if idx < len(tokens) else '$'
            step = {"Stack": " ".join([s for s, i in stack] + [top]), "Input": look, "Action": ""}
            if top == look:
                step["Action"] = f"Match {look}"; idx += 1
                if top == '$': status = "Accepted"; trace.append(step); break
            elif top in fixed_g:
                rule = m_table.at[top, look]
                if rule:
                    rhs = rule.split('->')[1].strip().split(); step["Action"] = f"Apply {rule}"
                    new_nodes = []
                    for sym in rhs:
                        node_id += 1; nid = str(node_id)
                        dot.node(nid, sym, style='filled', fillcolor=LEVEL_COLORS[node_id % 6])
                        dot.edge(pid, nid)
                        if sym != 'ε': new_nodes.append((sym, nid))
                    for n in reversed(new_nodes): stack.append(n)
                else: step["Action"] = "Error"; trace.append(step); break
            else: step["Action"] = "Error"; trace.append(step); break
            trace.append(step)
        st.session_state.sim = {'trace': trace, 'dot': dot, 'status': status, 'finished': True}

    if b2.button("⏭ خطوة تالية"):
        if not st.session_state.sim['stack']:
            st.session_state.sim['stack'] = [('$', '0'), (list(fixed_g.keys())[0], '0')]
            st.session_state.sim['dot'] = Digraph()
            st.session_state.sim['dot'].node('0', list(fixed_g.keys())[0], style='filled', fillcolor=LEVEL_COLORS[0])
        
        tokens = u_input.split(); idx = st.session_state.sim['idx']; stack = st.session_state.sim['stack']
        dot = st.session_state.sim['dot']; node_id = st.session_state.sim['node_id']
        
        if stack and not st.session_state.sim['finished']:
            top, pid = stack.pop(); look = tokens[idx] if idx < len(tokens) else '$'
            step = {"Stack": " ".join([s for s, i in stack] + [top]), "Input": look, "Action": ""}
            if top == look:
                step["Action"] = f"Match {look}"; idx += 1
                if top == '$': st.session_state.sim['status'] = "Accepted"; st.session_state.sim['finished'] = True
            elif top in fixed_g:
                rule = m_table.at[top, look]
                if rule:
                    rhs = rule.split('->')[1].strip().split(); step["Action"] = f"Apply {rule}"
                    new_nodes = []
                    for sym in rhs:
                        node_id += 1; nid = str(node_id)
                        dot.node(nid, sym, style='filled', fillcolor=LEVEL_COLORS[node_id % 6])
                        dot.edge(pid, nid)
                        if sym != 'ε': new_nodes.append((sym, nid))
                    for n in reversed(new_nodes): stack.append(n)
                else: st.session_state.sim['status'] = "Rejected"; st.session_state.sim['finished'] = True
            else: st.session_state.sim['status'] = "Rejected"; st.session_state.sim['finished'] = True
            st.session_state.sim['trace'].append(step)
            st.session_state.sim['idx'] = idx; st.session_state.sim['node_id'] = node_id

    # عرض جدول المحاكاة والرسم
    if st.session_state.sim['trace']:
        st.markdown('<div class="ltr-table">', unsafe_allow_html=True)
        st.table(pd.DataFrame(st.session_state.sim['trace']))
        st.markdown('</div>', unsafe_allow_html=True)
        if st.session_state.sim['finished']:
            if st.session_state.sim['status'] == "Accepted":
                st.markdown('<div class="status-accepted">Accepted ✅</div>', unsafe_allow_html=True)
            else: st.markdown('<div class="status-rejected">Rejected ❌</div>', unsafe_allow_html=True)
        st.graphviz_chart(st.session_state.sim['dot'])

    # التقارير
    st.header("4️⃣ تحميل التقارير")
    cp, cx = st.columns(2)
    with cp:
        if st.button("📄 تحميل PDF"):
            pdf = AcademicPDF(); pdf.add_page()
            pdf.add_section("Original Grammar", grammar=grammar_raw)
            pdf.add_section("M-Table", df=m_table)
            if st.session_state.sim['trace']:
                pdf.add_section("Trace", df=pd.DataFrame(st.session_state.sim['trace']))
            st.download_button("📥 PDF", bytes(pdf.output()), "Report.pdf")
    with cx:
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as w:
            ff_df.to_excel(w, sheet_name='Analysis'); m_table.to_excel(w, sheet_name='Table')
        st.download_button("📥 Excel", out.getvalue(), "Data.xlsx")

import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import re
import time
import io
import os
from fpdf import FPDF

# 1. التنسيق العام (RTL & Styles) --- #
st.set_page_config(page_title="LL(1) Academic Studio Pro", layout="wide")
st.markdown("""
    <style>
    .main { direction: RTL; text-align: right; }
    [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    .ltr-table { direction: LTR !important; text-align: left !important; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    .status-accepted { background-color: #1b5e20; color: white; padding: 20px; border-radius: 12px; text-align: center; font-size: 22px; font-weight: bold; border: 2px solid #2e7d32; }
    .status-rejected { background-color: #b71c1c; color: white; padding: 20px; border-radius: 12px; text-align: center; font-size: 22px; font-weight: bold; border: 2px solid #c62828; }
    .grammar-box { background-color: #f8f9fa; padding: 12px; border-radius: 8px; border-right: 6px solid #d32f2f; margin: 10px 0; font-family: monospace; }
    </style>
    """, unsafe_allow_html=True)

LEVEL_COLORS = ["#BBDEFB", "#C8E6C9", "#FFF9C4", "#F8BBD0", "#E1BEE7", "#B2EBF2"]

# 2. المحركات البرمجية (Core Engines) --- #
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
            prefix = list(prefix)
            new_grammar[nt] = [prefix + [new_nt]]
            suffix = [p[len(prefix):] if p[len(prefix):] else ['ε'] for p in prods]
            new_grammar[new_nt] = suffix
        else: new_grammar[nt] = prods
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
    for _ in range(len(grammar)+1):
        for nt in grammar:
            for prod in grammar[nt]: first[nt].update(get_seq_first(prod))
    start = list(grammar.keys())[0]
    follow = {nt: set() for nt in grammar}
    follow[start].add('$')
    for _ in range(len(grammar)+1):
        for nt, prods in grammar.items():
            for p in prods:
                for i, B in enumerate(p):
                    if B in grammar:
                        beta = p[i+1:]
                        fb = get_seq_first(beta)
                        follow[B].update(fb - {'ε'})
                        if 'ε' in fb: follow[B].update(follow[nt])
    return first, follow

# 3. نظام التقارير PDF --- #
class AcademicPDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 15)
        self.cell(0, 10, "LL(1) Comprehensive Analysis Report", ln=True, align="C")
        self.ln(10)

    def add_section(self, title, df=None, grammar=None):
        self.set_font("Arial", "B", 12)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 10, f" {title}", ln=True, fill=True)
        self.ln(3)
        if grammar:
            self.set_font("Courier", "", 10)
            for k, v in grammar.items():
                self.cell(0, 8, f"{k} -> {' | '.join([' '.join(p) for p in v])}", ln=True)
        elif df is not None:
            self.set_font("Arial", "", 9)
            cols = list(df.columns)
            cw = self.epw / (len(cols) + 1)
            self.cell(cw, 8, "NT/Step", 1, 0, 'C', True)
            for c in cols: self.cell(cw, 8, str(c), 1, 0, 'C', True)
            self.ln()
            for i, r in df.iterrows():
                if self.get_y() > 260: self.add_page()
                self.cell(cw, 7, str(i), 1, 0, 'C')
                for v in r: self.cell(cw, 7, str(v)[:20], 1, 0, 'L')
                self.ln()
        self.ln(5)

# 4. إدارة حالة التطبيق (Session State) --- #
if 'sim' not in st.session_state:
    st.session_state.sim = {
        'trace': [], 'dot': None, 'status': None, 
        'stack': [], 'idx': 0, 'node_id': 0, 'finished': False
    }

# 5. واجهة المستخدم (UI) --- #
with st.sidebar:
    st.header("⚙️ الإعدادات")
    raw_in = st.text_area("أدخل القواعد:", "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id", height=180)
    u_input = st.text_input("الجملة المراد فحصها:", "id + id * id $")
    
    if st.button("🔄 إعادة ضبط الكل"):
        st.session_state.sim = {'trace': [], 'dot': None, 'status': None, 'stack': [], 'idx': 0, 'node_id': 0, 'finished': False}
        st.rerun()

# تحليل القواعد
grammar_raw = OrderedDict()
try:
    for line in raw_in.split('\n'):
        if '->' in line:
            lhs, rhs = line.split('->')
            grammar_raw[lhs.strip()] = [opt.strip().split() for opt in rhs.split('|')]
except:
    st.error("خطأ في صيغة القواعد. يرجى التأكد من استخدام السهم (->)")

if grammar_raw:
    # المعالجة الآلية
    g_step1 = remove_left_recursion(grammar_raw)
    fixed_g = apply_left_factoring(g_step1)
    f_sets, fo_sets = get_first_follow(fixed_g)
    
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

    # العرض الأكاديمي
    st.header("1️⃣ التحليل اللغوي (Grammar Analysis)")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("القواعد الأصلية")
        for k, v in grammar_raw.items(): st.markdown(f'<div class="grammar-box ltr-table">{k} → {" | ".join([" ".join(p) for p in v])}</div>', unsafe_allow_html=True)
    with c2:
        st.subheader("القواعد المصححة")
        for k, v in fixed_g.items(): st.markdown(f'<div class="grammar-box ltr-table" style="border-right-color:#2e7d32">{k} → {" | ".join([" ".join(p) for p in v])}</div>', unsafe_allow_html=True)

    st.header("2️⃣ جداول LL(1)")
    st.markdown('<div class="ltr-table">', unsafe_allow_html=True)
    ff_df = pd.DataFrame({"First": [", ".join(sorted(list(s))) for s in f_sets.values()], "Follow": [", ".join(sorted(list(s))) for s in fo_sets.values()]}, index=f_sets.keys())
    st.table(ff_df)
    st.subheader("Parsing Table (M-Table)")
    st.dataframe(m_table, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # المحاكاة (Simulation)
    st.header("3️⃣ محاكاة الإعراب (Simulation)")
    col_run, col_step = st.columns([1, 4])
    
    # منطق التشغيل الكامل
    if col_run.button("▶ تشغيل كامل"):
        tokens = u_input.split()
        stack = [('$', '0'), (list(fixed_g.keys())[0], '0')]
        idx, node_id, trace = 0, 0, []
        dot = Digraph()
        dot.node('0', list(fixed_g.keys())[0], style='filled', fillcolor=LEVEL_COLORS[0])
        status = "Rejected"
        
        while stack:
            top, pid = stack.pop()
            look = tokens[idx] if idx < len(tokens) else '$'
            step = {"Stack": " ".join([s for s, i in stack] + [top]), "Input": look, "Action": ""}
            
            if top == look:
                step["Action"] = f"✅ Match {look}"
                idx += 1
                if top == '$': status = "Accepted"; trace.append(step); break
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
                else: step["Action"] = "❌ Error (No Rule)"; trace.append(step); break
            else: step["Action"] = "❌ Error (Mismatch)"; trace.append(step); break
            trace.append(step)
        st.session_state.sim = {'trace': trace, 'dot': dot, 'status': status, 'finished': True}

    # منطق التشغيل خطوة بخطوة
    if col_step.button("⏭ خطوة تالية"):
        if not st.session_state.sim['stack']:
            st.session_state.sim['stack'] = [('$', '0'), (list(fixed_g.keys())[0], '0')]
            st.session_state.sim['dot'] = Digraph()
            st.session_state.sim['dot'].node('0', list(fixed_g.keys())[0], style='filled', fillcolor=LEVEL_COLORS[0])
        
        tokens = u_input.split()
        idx = st.session_state.sim['idx']
        stack = st.session_state.sim['stack']
        dot = st.session_state.sim['dot']
        node_id = st.session_state.sim['node_id']
        
        if stack and not st.session_state.sim['finished']:
            top, pid = stack.pop()
            look = tokens[idx] if idx < len(tokens) else '$'
            step = {"Stack": " ".join([s for s, i in stack] + [top]), "Input": look, "Action": ""}
            
            if top == look:
                step["Action"] = f"✅ Match {look}"
                idx += 1
                if top == '$': 
                    st.session_state.sim['status'] = "Accepted"
                    st.session_state.sim['finished'] = True
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
                else: 
                    step["Action"] = "❌ Error"; st.session_state.sim['status'] = "Rejected"
                    st.session_state.sim['finished'] = True
            else: 
                step["Action"] = "❌ Error"; st.session_state.sim['status'] = "Rejected"
                st.session_state.sim['finished'] = True
            
            st.session_state.sim['trace'].append(step)
            st.session_state.sim['idx'] = idx
            st.session_state.sim['node_id'] = node_id

    # عرض النتائج
    if st.session_state.sim['trace']:
        st.markdown('<div class="ltr-table">', unsafe_allow_html=True)
        st.table(pd.DataFrame(st.session_state.sim['trace']))
        st.markdown('</div>', unsafe_allow_html=True)
        
        if st.session_state.sim['finished']:
            if st.session_state.sim['status'] == "Accepted":
                st.markdown('<div class="status-accepted">الجملة مقبولة (Accepted) ✅</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="status-rejected">الجملة مرفوضة (Rejected) ❌</div>', unsafe_allow_html=True)
        
        st.graphviz_chart(st.session_state.sim['dot'])

    # 6. التقارير --- #
    st.header("4️⃣ تحميل التقارير")
    cp, cx = st.columns(2)
    with cp:
        if st.button("📄 توليد PDF الأكاديمي"):
            pdf = AcademicPDF(); pdf.add_page()
            pdf.add_section("Original Grammar", grammar=grammar_raw)
            pdf.add_section("Fixed Grammar", grammar=fixed_g)
            pdf.add_section("Parsing Sets", df=ff_df)
            pdf.add_section("Parsing Table", df=m_table)
            if st.session_state.sim['trace']:
                pdf.add_section("Simulation Trace", df=pd.DataFrame(st.session_state.sim['trace']))
            st.download_button("📥 تحميل PDF", bytes(pdf.output()), "LL1_Academic_Report.pdf")
    with cx:
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as w:
            ff_df.to_excel(w, sheet_name='First_Follow')
            m_table.to_excel(w, sheet_name='M_Table')
        st.download_button("📥 تحميل Excel", out.getvalue(), "Grammar_Data.xlsx")

import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import re
import time
import io
import os
from fpdf import FPDF

# 1. التنسيق الأكاديمي (RTL) مع دعم الخطوط العربية
st.set_page_config(page_title="LL(1) Academic Studio V3", layout="wide")
st.markdown("""
    <style>
    .main { direction: RTL; text-align: right; }
    [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    .ltr-table { direction: LTR !important; text-align: left !important; font-family: 'Consolas', monospace; }
    .status-accepted { background-color: #2e7d32; color: white; padding: 15px; border-radius: 8px; text-align: center; font-size: 18px; font-weight: bold; }
    .status-rejected { background-color: #c62828; color: white; padding: 15px; border-radius: 8px; text-align: center; font-size: 18px; font-weight: bold; }
    .grammar-box { background-color: #f8f9fa; padding: 10px; border-radius: 5px; border-right: 5px solid #d32f2f; margin: 10px 0; font-family: monospace; }
    </style>
    """, unsafe_allow_html=True)

LEVEL_COLORS = ["#BBDEFB", "#C8E6C9", "#FFF9C4", "#F8BBD0", "#E1BEE7", "#B2EBF2"]

# --- 2. محرك التحليل المنطقي (Core Engine) ---

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

    # تكرار حتى الاستقرار لمنع الأخطاء في القواعد المعقدة
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

# --- 3. محرك التقارير (PDF) المصحح ---

class AcademicPDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, "LL(1) Parser Academic Report - University of Misan", ln=True, align="C")
        self.ln(5)

    def add_section(self, title, df=None, grammar=None):
        self.set_font("Arial", "B", 12)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 10, f" {title}", ln=True, fill=True)
        self.ln(2)
        if grammar:
            self.set_font("Courier", "", 10)
            for k, v in grammar.items():
                self.cell(0, 8, f"{k} -> {' | '.join([' '.join(p) for p in v])}", ln=True)
        elif df is not None:
            self.set_font("Arial", "", 8)
            cw = self.epw / (len(df.columns) + 1)
            self.cell(cw, 8, "Item", 1, 0, 'C', True)
            for c in df.columns: self.cell(cw, 8, str(c), 1, 0, 'C', True)
            self.ln()
            for i, r in df.iterrows():
                self.cell(cw, 7, str(i), 1, 0, 'C')
                for v in r: self.cell(cw, 7, str(v)[:25], 1, 0, 'L')
                self.ln()
        self.ln(5)

# --- 4. واجهة المستخدم والمحاكاة ---

# صمام الأمان: إعادة ضبط الحالة عند تغيير النص المدخل
if 'last_raw' not in st.session_state: st.session_state.last_raw = ""

with st.sidebar:
    st.header("⚙️ الإعدادات")
    raw_in = st.text_area("أدخل القواعد:", "S -> i e T S S' | a\nS' -> e S | ε\nE -> b", height=150)
    # إذا تغيرت القواعد، صفر الحالة فوراً لمنع الواجهة البيضاء
    if raw_in != st.session_state.last_raw:
        st.session_state.sim = {'trace': [], 'dot': None, 'finished': False, 'status': None}
        st.session_state.last_raw = raw_in

    u_input = st.text_input("الجملة المراد فحصها:", "i e b a $")
    speed = st.slider("سرعة التحريك:", 0.1, 1.5, 0.5)

# معالجة القواعد
grammar_raw = OrderedDict()
for line in raw_in.split('\n'):
    if '->' in line:
        lhs, rhs = line.split('->')
        grammar_raw[lhs.strip()] = [opt.strip().split() for opt in rhs.split('|')]

if grammar_raw:
    # 1. عرض القواعد
    st.header("1️⃣ مراجعة القواعد")
    for k, v in grammar_raw.items():
        st.markdown(f'<div class="grammar-box ltr-table">{k} → {" | ".join([" ".join(p) for p in v])}</div>', unsafe_allow_html=True)

    # 2. الحسابات
    f_sets, fo_sets = get_first_follow_stable(grammar_raw)
    ff_df = pd.DataFrame({
        "First": [", ".join(sorted(list(s))) for s in f_sets.values()],
        "Follow": [", ".join(sorted(list(s))) for s in fo_sets.values()]
    }, index=f_sets.keys())
    
    st.header("2️⃣ جداول First & Follow")
    st.table(ff_df)

    # 3. M-Table
    terms = sorted(list({s for ps in grammar_raw.values() for p in ps for s in p if s not in grammar_raw and s != 'ε'})) + ['$']
    m_table = pd.DataFrame("", index=grammar_raw.keys(), columns=terms)
    for nt, prods in grammar_raw.items():
        for p in prods:
            p_first = set()
            for s in p:
                sf = f_sets[s] if s in grammar_raw else {s}
                p_first.update(sf - {'ε'})
                if 'ε' not in sf: break
            else: p_first.add('ε')
            for a in p_first:
                if a != 'ε': m_table.at[nt, a] = f"{nt} -> {' '.join(p)}"
            if 'ε' in p_first:
                for b in fo_sets[nt]: m_table.at[nt, b] = f"{nt} -> {' '.join(p)}"

    st.header("3️⃣ مصفوفة الإعراب (M-Table)")
    st.dataframe(m_table, use_container_width=True)

    # 4. المحاكاة
    st.header("4️⃣ التتبع التفاعلي والشجرة")
    if st.button("▶ بدء عملية التحليل"):
        tokens, idx, node_id, trace = u_input.split(), 0, 0, []
        stack = [('$', '0'), (list(grammar_raw.keys())[0], '0')]
        dot = Digraph(); dot.attr(rankdir='TD')
        dot.node('0', list(grammar_raw.keys())[0], style='filled', fillcolor=LEVEL_COLORS[0])
        
        while stack:
            top, pid = stack.pop()
            look = tokens[idx] if idx < len(tokens) else '$'
            step = {"Stack": " ".join([s for s, i in stack] + [top]), "Input": look, "Action": ""}
            
            if top == look:
                step["Action"] = f"Match {look}"; idx += 1
                if top == '$': st.session_state.sim['status'] = "Accepted"; break
            elif top in grammar_raw:
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
                else: st.session_state.sim['status'] = "Rejected"; trace.append(step); break
            else: st.session_state.sim['status'] = "Rejected"; trace.append(step); break
            trace.append(step)
        
        st.session_state.sim.update({'trace': trace, 'dot': dot, 'finished': True})

    # العرض
    if st.session_state.sim['trace']:
        st.table(pd.DataFrame(st.session_state.sim['trace']))
        if st.session_state.sim['finished']:
            res = st.session_state.sim['status']
            st.markdown(f'<div class="status-{"accepted" if res=="Accepted" else "rejected"}">{res}</div>', unsafe_allow_html=True)
        st.graphviz_chart(st.session_state.sim['dot'])

    # 5. التقارير
    st.header("5️⃣ التصدير")
    if st.button("📄 توليد تقرير PDF"):
        pdf = AcademicPDF(); pdf.add_page()
        pdf.add_section("Grammar", grammar=grammar_raw)
        pdf.add_section("Sets", df=ff_df)
        pdf.add_section("M-Table", df=m_table)
        st.download_button("📥 تحميل PDF", bytes(pdf.output()), "LL1_Report.pdf")

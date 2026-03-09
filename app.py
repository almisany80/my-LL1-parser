import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import re
import io
import os
from fpdf import FPDF

# 1. إعدادات الواجهة (RTL Support)
st.set_page_config(page_title="LL(1) Academic Studio Pro", layout="wide")
st.markdown("""
    <style>
    .main { direction: RTL; text-align: right; }
    [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    .ltr-table { direction: LTR !important; text-align: left !important; font-family: 'Consolas', monospace; }
    .status-accepted { background-color: #1b5e20; color: white; padding: 15px; border-radius: 8px; text-align: center; font-weight: bold; }
    .status-rejected { background-color: #b71c1c; color: white; padding: 15px; border-radius: 8px; text-align: center; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

LEVEL_COLORS = ["#BBDEFB", "#C8E6C9", "#FFF9C4", "#F8BBD0", "#E1BEE7", "#B2EBF2"]

# 2. المحرك الحسابي الدقيق (Precision Logic)
def get_first_follow_stable(grammar):
    # تهيئة المجموعات
    first = {nt: set() for nt in grammar}
    non_terminals = set(grammar.keys())
    
    def get_seq_first(seq):
        res = set()
        if not seq or seq == ['ε']: return {'ε'}
        for s in seq:
            # إذا كان الرمز غير طرفي، نأخذ مجموعته، وإذا كان طرفياً نأخذه هو نفسه
            sf = first[s] if s in non_terminals else {s}
            res.update(sf - {'ε'})
            if 'ε' not in sf: break
        else: res.add('ε')
        return res

    # حساب First بشكل تكراري حتى الاستقرار
    while True:
        changed = False
        for nt, prods in grammar.items():
            old_len = len(first[nt])
            for p in prods:
                first[nt].update(get_seq_first(p))
            if len(first[nt]) > old_len: changed = True
        if not changed: break

    # حساب Follow بشكل تكراري حتى الاستقرار
    follow = {nt: set() for nt in grammar}
    start_node = list(grammar.keys())[0]
    follow[start_node].add('$')
    
    while True:
        changed = False
        for nt, prods in grammar.items():
            for p in prods:
                for i, B in enumerate(p):
                    if B in non_terminals:
                        old_len = len(follow[B])
                        # ننظر إلى الرموز التي تلي B
                        beta = p[i+1:]
                        if beta:
                            first_beta = get_seq_first(beta)
                            follow[B].update(first_beta - {'ε'})
                            if 'ε' in first_beta:
                                follow[B].update(follow[nt])
                        else:
                            # إذا لم يتبع B شيء، يأخذ Follow الـ LHS
                            follow[B].update(follow[nt])
                        if len(follow[B]) > old_len: changed = True
        if not changed: break
    
    return first, follow

# 3. نظام التقارير المصحح
class AcademicPDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, "LL(1) Parser Academic Analysis", ln=True, align="C")
        self.ln(5)

    def add_section(self, title, df=None, grammar=None):
        self.set_font("Arial", "B", 11)
        self.set_fill_color(245, 245, 245)
        self.cell(0, 10, f" {title}", ln=True, fill=True)
        self.ln(2)
        if grammar:
            self.set_font("Courier", "", 10)
            for k, v in grammar.items():
                self.cell(0, 8, f"{k} -> {' | '.join([' '.join(p) for p in v])}", ln=True)
        elif df is not None:
            self.set_font("Arial", "", 9)
            cw = self.epw / (len(df.columns) + 1)
            self.cell(cw, 8, "NT", 1, 0, 'C', True)
            for c in df.columns: self.cell(cw, 8, str(c), 1, 0, 'C', True)
            self.ln()
            for i, r in df.iterrows():
                self.cell(cw, 7, str(i), 1, 0, 'C')
                for v in r: self.cell(cw, 7, str(v)[:20], 1, 0, 'L')
                self.ln()
        self.ln(5)

# 4. بناء واجهة الاستخدام
with st.sidebar:
    st.header("⚙️ المدخلات")
    # القواعد المدخلة كما في الصورة
    default_grammar = "S -> i e T S S` | a\nS` -> e S | ε\nE -> b"
    raw_in = st.text_area("أدخل القواعد (تأكد من المسافات بين الرموز):", default_grammar, height=180)
    u_input = st.text_input("الجملة:", "i e b i e b a $")

# معالجة القواعد
grammar = OrderedDict()
for line in raw_in.split('\n'):
    if '->' in line:
        lhs, rhs = line.split('->')
        grammar[lhs.strip()] = [opt.strip().split() for opt in rhs.split('|')]

if grammar:
    # الحسابات
    f_sets, fo_sets = get_first_follow_stable(grammar)
    
    st.header("1️⃣ التحليل الحسابي (Sets Analysis)")
    ff_df = pd.DataFrame({
        "First": [", ".join(sorted(list(s))) for s in f_sets.values()],
        "Follow": [", ".join(sorted(list(s))) for s in fo_sets.values()]
    }, index=f_sets.keys())
    
    st.markdown('<div class="ltr-table">', unsafe_allow_html=True)
    st.table(ff_df)
    st.markdown('</div>', unsafe_allow_html=True)

    # بناء M-Table
    all_terms = set()
    for prods in grammar.values():
        for p in prods:
            for sym in p:
                if sym not in grammar and sym != 'ε': all_terms.add(sym)
    terms = sorted(list(all_terms)) + ['$']
    
    m_table = pd.DataFrame("", index=grammar.keys(), columns=terms)
    for nt, prods in grammar.items():
        for p in prods:
            p_first = set()
            if p == ['ε']: p_first = {'ε'}
            else:
                for s in p:
                    sf = f_sets[s] if s in grammar else {s}
                    p_first.update(sf - {'ε'})
                    if 'ε' not in sf: break
                else: p_first.add('ε')
            
            for a in p_first:
                if a != 'ε': m_table.at[nt, a] = f"{nt} -> {' '.join(p)}"
            if 'ε' in p_first:
                for b in fo_sets[nt]: m_table.at[nt, b] = f"{nt} -> {' '.join(p)}"

    st.header("2️⃣ مصفوفة الإعراب (M-Table)")
    st.markdown('<div class="ltr-table">', unsafe_allow_html=True)
    st.dataframe(m_table, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # 5. التصدير
    if st.button("📄 توليد التقرير النهائي"):
        pdf = AcademicPDF(); pdf.add_page()
        pdf.add_section("Input Grammar", grammar=grammar)
        pdf.add_section("First & Follow Sets", df=ff_df)
        pdf.add_section("Predictive Parsing Table", df=m_table)
        st.download_button("📥 تحميل التقرير", bytes(pdf.output()), "LL1_Analysis.pdf")

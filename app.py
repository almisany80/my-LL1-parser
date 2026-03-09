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
    .status-accepted { background-color: #2e7d32; color: white; padding: 15px; border-radius: 8px; text-align: center; font-size: 20px; font-weight: bold; margin-bottom: 20px; }
    .status-rejected { background-color: #c62828; color: white; padding: 15px; border-radius: 8px; text-align: center; font-size: 20px; font-weight: bold; margin-bottom: 20px; }
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
            if "Stack" not in cols: _ = self.cell(cw,

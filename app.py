import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import re
import time
import io
import os
from fpdf import FPDF

# 1. الإعدادات العامة (RTL Support)
st.set_page_config(page_title="LL(1) Academic Studio Pro", layout="wide")
st.markdown("""
    <style>
    .main { direction: RTL; text-align: right; }
    [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    .ltr-table { direction: LTR !important; text-align: left !important; font-family: 'Segoe UI', sans-serif; }
    .status-accepted { background-color: #1b5e20; color: white; padding: 20px; border-radius: 12px; text-align: center; font-weight: bold; }
    .status-rejected { background-color: #b71c1c; color: white; padding: 20px; border-radius: 12px; text-align: center; font-weight: bold; }
    .grammar-box { background-color: #f8f9fa; padding: 10px; border-radius: 8px; border-right: 6px solid #d32f2f; margin: 10px 0; }
    </style>
    """, unsafe_allow_html=True)

LEVEL_COLORS = ["#BBDEFB", "#C8E6C9", "#FFF9C4", "#F8BBD0", "#E1BEE7", "#B2EBF2"]

# 2. المحركات البرمجية (Core Logic)
def clean_grammar(raw_text):
    grammar = OrderedDict()
    try:
        for line in raw_text.split('\n'):
            line = line.strip()
            if not line: continue
            # دعم كافة أشكال الأسهم
            parts = re.split(r'->|→|=', line)
            if len(parts) == 2:
                lhs = parts[0].strip()
                rhs = [opt.strip().split() for opt in parts[1].split('|')]
                grammar[lhs] = rhs
    except Exception as e:
        st.error(f"خطأ في قراءة القواعد: {e}")
    return grammar

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
            prefix_list = list(prefix)
            new_grammar[nt] = [prefix_list + [new_nt]]
            suffix = [p[len(prefix_list):] if p[len(prefix_list):] else ['ε'] for p in prods]
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
    for _ in range(len(grammar) + 1):
        for nt in grammar:
            for prod in grammar[nt]: first[nt].update(get_seq_first(prod))
    
    start = list(grammar.keys())[0]
    follow = {nt: set() for nt in grammar}
    follow[start].add('$')
    for _ in range(len(grammar) + 1):
        for nt, prods in grammar.items():
            for p in prods:
                for i, B in enumerate(p):
                    if B in grammar:
                        beta = p[i+1:]
                        fb = get_seq_first(beta)
                        follow[B].update(fb - {'ε'})
                        if 'ε' in fb: follow[B].update(follow[nt])
    return first, follow

# 3. نظام التقارير (Fixed PDF Logic)
class AcademicPDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, "LL(1) Grammar Analysis Report", ln=True, align="C")
        self.ln(10)

    def add_section(self, title, df=None, grammar=None):
        self.set_font("Arial", "B", 12)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 10, f" {title}", ln=True, fill=True)
        self.ln(3)
        if grammar:
            self.set_font("Courier", "", 10)
            for k, v in grammar.items():
                line = f"{k} -> {' | '.join([' '.join(p) for p in v])}"
                self.cell(0, 8, line, ln=True)
        elif df is not None:
            self.set_font("Arial", "", 9)
            cols = list(df.columns)
            cw = self.epw / (len(cols) + 1)
            self.cell(cw, 8, "Index", 1, 0, 'C', True)
            for c in cols: self.cell(cw, 8, str(c), 1, 0, 'C', True)
            self.ln()
            for i, r in df.iterrows():
                if self.get_y() > 260: self.add_page()
                self.cell(cw, 7, str(i), 1, 0, 'C')
                for v in r: self.cell(cw, 7, str(v)[:20], 1, 0, 'L')
                self.ln()
        self.ln(5)

# 4. إدارة الحالة (Session State Management)
if 'sim' not in st.session_state:
    st.session_state.sim = {'trace': [], 'dot': None, 'status': None, 'stack': [], 'idx': 0, 'node_id': 0, 'finished': False}

# 5. الواجهة البرمجية (UI)
with st.sidebar:
    st.header("⚙️ المدخلات")
    raw_in = st.text_area("أدخل القواعد:", "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id", height=150)
    u_input = st.text_input("الجملة المراد فحصها:", "id + id * id $")
    
    # إعادة ضبط الحالة عند تغيير المدخلات
    if st.button("🔄 إعادة ضبط النظام"):
        st.session_state.sim = {'trace': [], 'dot': None, 'status': None, 'stack': [], 'idx': 0, 'node_id': 0, 'finished': False}
        st.rerun()

grammar_raw = clean_grammar(raw_in)

if grammar_raw:
    try:
        # المعالجة التلقائية
        g_fixed = apply_left_factoring(remove_left_recursion(grammar_raw))
        f_sets, fo_sets = get_first_follow(g_fixed)
        
        # إنشاء جدول الإعراب (M-Table)
        terms = sorted(list({s for ps in g_fixed.values() for p in ps for s in p if s not in g_fixed and s != 'ε'})) + ['$']
        m_table = pd.DataFrame("", index=g_fixed.keys(), columns=terms)
        for nt, prods in g_fixed.items():
            for p in prods:
                first_p = set()
                for s in p:
                    sf = f_sets[s] if s in g_fixed else {s}
                    first_p.update(sf - {'ε'})
                    if 'ε' not in sf: break
                else: first_p.add('ε')
                for a in first_p:
                    if a != 'ε': m_table.at[nt, a] = f"{nt} -> {' '.join(p)}"
                if 'ε' in first_p:
                    for b in fo_sets[nt]: m_table.at[nt, b] = f"{nt} -> {' '.join(p)}"

        # عرض النتائج التعليمية
        st.header("1️⃣ تحليل القواعد")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("القواعد الأصلية")
            for k, v in grammar_raw.items(): st.markdown(f'<div class="grammar-box ltr-table">{k} → {" | ".join([" ".join(p) for p in v])}</div>', unsafe_allow_html=True)
        with c2:
            st.subheader("القواعد المصححة")
            for k, v in g_fixed.items(): st.markdown(f'<div class="grammar-box ltr-table" style="border-right-color:#2e7d32">{k} → {" | ".join([" ".join(p) for p in v])}</div>', unsafe_allow_html=True)

        st.header("2️⃣ جداول LL(1)")
        ff_df = pd.DataFrame({"First": [", ".join(sorted(list(s))) for s in f_sets.values()], "Follow": [", ".join(sorted(list(s))) for s in fo_sets.values()]}, index=f_sets.keys())
        st.markdown('<div class="ltr-table">', unsafe_allow_html=True)
        st.table(ff_df)
        st.subheader("M-Table")
        st.dataframe(m_table, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # المحاكاة (Simulation)
        st.header("3️⃣ محاكاة الإعراب")
        col_run, col_step = st.columns([1, 4])
        
        # زر التشغيل الكامل
        if col_run.button("▶ تشغيل كامل"):
            tokens = u_input.split()
            stack = [('$', '0'), (list(g_fixed.keys())[0], '0')]
            idx, node_id, trace = 0, 0, []
            dot = Digraph()
            dot.node('0', list(g_fixed.keys())[0], style='filled', fillcolor=LEVEL_COLORS[0])
            status = "Rejected"
            
            while stack:
                top, pid = stack.pop()
                look = tokens[idx] if idx < len(tokens) else '$'
                step = {"Stack": " ".join([s for s, i in stack] + [top]), "Input": look, "Action": ""}
                
                if top == look:
                    step["Action"] = f"✅ Match {look}"
                    idx += 1
                    if top == '$': status = "Accepted"; trace.append(step); break
                elif top in g_fixed:
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
                        step["Action"] = "❌ Error (No Rule)"; trace.append(step); break
                else: 
                    step["Action"] = "❌ Error (Mismatch)"; trace.append(step); break
                trace.append(step)
            st.session_state.sim = {'trace': trace, 'dot': dot, 'status': status, 'finished': True}

        # عرض النتائج
        if st.session_state.sim['trace']:
            st.markdown('<div class="ltr-table">', unsafe_allow_html=True)
            st.table(pd.DataFrame(st.session_state.sim['trace']))
            st.markdown('</div>', unsafe_allow_html=True)
            
            if st.session_state.sim['finished']:
                if st.session_state.sim['status'] == "Accepted":
                    st.markdown('<div class="status-accepted">تم قبول الجملة بنجاح ✅</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="status-rejected">الجملة غير مطابقة للقواعد ❌</div>', unsafe_allow_html=True)
            st.graphviz_chart(st.session_state.sim['dot'])

        # التقارير
        st.header("4️⃣ تصدير البيانات")
        cp, cx = st.columns(2)
        with cp:
            if st.button("📄 تحميل PDF"):
                pdf = AcademicPDF(); pdf.add_page()
                pdf.add_section("Original Grammar", grammar=grammar_raw)
                pdf.add_section("M-Table", df=m_table)
                if st.session_state.sim['trace']:
                    pdf.add_section("Trace", df=pd.DataFrame(st.session_state.sim['trace']))
                st.download_button("📥 PDF Download", bytes(pdf.output()), "Report.pdf")
        with cx:
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as w:
                ff_df.to_excel(w, sheet_name='Analysis')
                m_table.to_excel(w, sheet_name='Table')
            st.download_button("📥 Excel Download", out.getvalue(), "Data.xlsx")

    except Exception as e:
        st.error(f"حدث خطأ غير متوقع: {e}")
        st.info("يرجى التأكد من أن القواعد تتبع صيغة صحيحة مثل E -> T E'")

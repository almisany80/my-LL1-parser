import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import re
import time
import io
import os
from fpdf import FPDF

# 1. التنسيق العام (واجهة عربية RTL مع جداول إنجليزية LTR) --- #
st.set_page_config(page_title="LL(1) Academic Studio", layout="wide")
st.markdown("""
    <style>
    .main { direction: RTL; text-align: right; }
    [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    .ltr-table { direction: LTR !important; text-align: left !important; }
    .status-accepted { background-color: #2e7d32; color: white; padding: 15px; border-radius: 8px; text-align: center; font-size: 20px; margin: 10px 0; }
    .status-rejected { background-color: #c62828; color: white; padding: 15px; border-radius: 8px; text-align: center; font-size: 20px; margin: 10px 0; }
    </style>
    """, unsafe_allow_html=True)

LEVEL_COLORS = ["#BBDEFB", "#C8E6C9", "#FFF9C4", "#F8BBD0", "#E1BEE7", "#B2EBF2"]

# 2. منطق التحليل (LL1 Logic) --- #
def auto_fix_grammar(grammar):
    temp_g = OrderedDict()
    for nt, prods in grammar.items():
        rec = [p[1:] for p in prods if p and p[0] == nt]
        non_rec = [p for p in prods if not (p and p[0] == nt)]
        if rec:
            new_nt = f"{nt}'"
            temp_g[nt] = [p + [new_nt] for p in non_rec] if non_rec else [[new_nt]]
            temp_g[new_nt] = [p + [new_nt] for p in rec] + [['ε']]
        else:
            temp_g[nt] = prods
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

# 3. محرك تقارير PDF (إصلاح مشكلة ظهور الأسطر واللغة) --- #
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
        self.cell(0, 10, "LL(1) Parser Academic Simulation Report", ln=True, align="C")
        self.ln(5)

    def add_section(self, title, df=None, grammar=None):
        self.set_font(self.f_name, "", 12)
        self.set_fill_color(230, 230, 230)
        self.cell(0, 10, f" {title}", ln=True, fill=True)
        self.ln(2)
        
        if grammar:
            self.set_font("Courier", "", 10)
            for k, v in grammar.items():
                self.cell(0, 7, f"{k} -> {' | '.join([' '.join(p) for p in v])}", ln=True)
        elif df is not None:
            self.set_font("Arial", "", 9)
            cols = list(df.columns)
            if "Stack" in cols: # تخصيص عرض أعمدة جدول المحاكاة
                cw = [90, 30, 70]
            else:
                cw = [self.epw / (len(cols)+1)] * (len(cols)+1)

            # طباعة العناوين
            if not "Stack" in cols: self.cell(cw[0], 8, "NT", 1, 0, 'C')
            for i, c in enumerate(cols):
                idx = i+1 if not "Stack" in cols else i
                self.cell(cw[idx] if isinstance(cw, list) else cw, 8, str(c), 1, 0, 'C')
            self.ln()

            # طباعة البيانات
            for idx, r in df.iterrows():
                if self.get_y() > 260: self.add_page()
                if not "Stack" in cols: self.cell(cw[0], 7, str(idx), 1)
                for i, v in enumerate(r):
                    c_idx = i+1 if not "Stack" in cols else i
                    # استخدام متغير مهمل (_) لمنع طباعة مخرجات الدالة في واجهة سريم ليت
                    _ = self.cell(cw[c_idx] if isinstance(cw, list) else cw, 7, str(v), 1)
                self.ln()
        self.ln(5)

# 4. واجهة المستخدم والمحاكاة --- #
with st.sidebar:
    st.header("1️⃣ إدخال القواعد")
    raw_in = st.text_area("أدخل القواعد (القاعدة الأولى هي البداية):", "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id", height=150)
    speed = st.slider("سرعة المحاكاة:", 0.1, 2.0, 0.5)

grammar_raw = OrderedDict()
for line in raw_in.split('\n'):
    if '->' in line:
        lhs, rhs = line.split('->')
        grammar_raw[lhs.strip()] = [opt.strip().split() for opt in rhs.split('|')]

if grammar_raw:
    fixed_g = auto_fix_grammar(grammar_raw)
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

    st.header("2️⃣ & 3️⃣ جداول التحليل")
    st.dataframe(m_table, use_container_width=True)

    st.header("4️⃣ & 5️⃣ محاكاة الجملة")
    u_input = st.text_input("أدخل الجملة المراد فحصها (افصل بمسافة):", "id + id * id $")

    if 'sim' not in st.session_state:
        st.session_state.sim = {'trace': [], 'dot': Digraph(), 'done': False}

    c1, c2, _ = st.columns([1, 1, 2])
    if c1.button("🔄 إعادة ضبط"):
        st.session_state.sim = {'trace': [], 'dot': Digraph(), 'done': False}
        st.rerun()

    if c2.button("▶ تشغيل المحاكاة"):
        tokens = u_input.split()
        stack = [('$', '0'), (list(fixed_g.keys())[0], '0')]
        idx = 0
        dot = Digraph(format='png')
        dot.node('0', list(fixed_g.keys())[0], style='filled', fillcolor=LEVEL_COLORS[0])
        node_id = 0
        trace = []
        
        while stack:
            top, pid = stack.pop()
            look = tokens[idx] if idx < len(tokens) else '$'
            # استخدام أعمدة باللغة الإنجليزية
            step = {"Stack": " ".join([s for s, i in stack] + [top]), "Input": look, "Action": ""}
            
            if top == look:
                step["Action"] = f"✅ Match {look}"
                idx += 1
                if top == '$': break
            elif top in fixed_g:
                rule = m_table.at[top, look]
                if rule != "":
                    rhs = rule.split('->')[1].strip().split()
                    step["Action"] = f"Apply {rule}" # نصوص إنجليزية
                    new_nodes = []
                    for sym in rhs:
                        node_id += 1
                        nid = str(node_id)
                        dot.node(nid, sym, style='filled', fillcolor=LEVEL_COLORS[node_id % 6])
                        dot.edge(pid, nid)
                        if sym != 'ε': new_nodes.append((sym, nid))
                    for n in reversed(new_nodes): stack.append(n)
                else:
                    step["Action"] = "❌ Error"
                    trace.append(step)
                    break
            else:
                step["Action"] = "❌ Error"
                trace.append(step)
                break
            trace.append(step)
        
        st.session_state.sim = {'trace': trace, 'dot': dot, 'done': True}
        
    if st.session_state.sim['trace']:
        st.markdown('<div class="ltr-table">', unsafe_allow_html=True)
        st.table(pd.DataFrame(st.session_state.sim['trace']))
        st.markdown('</div>', unsafe_allow_html=True)
        st.graphviz_chart(st.session_state.sim['dot'])

    st.header("6️⃣ تحميل التقارير")
    if st.button("📄 توليد PDF الأكاديمي"):
        pdf = AcademicPDF()
        pdf.add_page()
        pdf.add_section("1. Grammar Rules", grammar=fixed_g)
        pdf.add_section("2. M-Parsing Table", df=m_table)
        if st.session_state.sim['trace']:
            pdf.add_section("3. Simulation Trace", df=pd.DataFrame(st.session_state.sim['trace']))
            # إضافة صورة الشجرة
            img_data = st.session_state.sim['dot'].pipe(format='png')
            pdf.add_page()
            pdf.cell(0, 10, "4. Parse Tree Visual", ln=True)
            pdf.image(io.BytesIO(img_data), w=pdf.epw)
        
        # استخدام bytes() لضمان عمل زر التحميل بنجاح
        st.download_button("📥 تحميل ملف PDF الآن", bytes(pdf.output()), "LL1_Report.pdf", "application/pdf")

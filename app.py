import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import re
import time
import io
import copy
from fpdf import FPDF

# --- 1. إعدادات الصفحة والتنسيق العربي (RTL) ---
st.set_page_config(page_title="LL(1) Academic Studio", layout="wide")

st.markdown("""
    <style>
    .main { direction: RTL; text-align: right; }
    [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    .ltr-text { direction: LTR !important; text-align: left !important; font-family: monospace; font-size: 16px; }
    .stTable, .stDataFrame, [data-testid="stTable"] { direction: LTR !important; text-align: left !important; }
    </style>
    """, unsafe_allow_html=True)

# ألوان المستويات للشجرة
LEVEL_COLORS = ["#BBDEFB", "#C8E6C9", "#FFF9C4", "#F8BBD0", "#E1BEE7", "#B2EBF2", "#FFE0B2", "#D7CCC8"]

# --- 2. محركات التصحيح والتحليل المنطقي ---

def auto_fix_grammar(grammar):
    # إزالة التداخل اليساري (Left Recursion)
    temp_g = OrderedDict()
    for nt, prods in grammar.items():
        recursive = [p[1:] for p in prods if p and p[0] == nt]
        non_recursive = [p for p in prods if not (p and p[0] == nt)]
        if recursive:
            new_nt = f"{nt}p"
            temp_g[nt] = [p + [new_nt] for p in non_recursive] if non_recursive else [[new_nt]]
            temp_g[new_nt] = [p + [new_nt] for p in recursive] + [['ε']]
        else: temp_g[nt] = prods
    
    # إزالة العامل المشترك الأيسر (Left Factoring)
    final_g = OrderedDict()
    for nt, prods in temp_g.items():
        if len(prods) <= 1:
            final_g[nt] = prods
            continue
        prefixes = {}
        for p in prods:
            first_sym = p[0] if p else 'ε'
            if first_sym not in prefixes: prefixes[first_sym] = []
            prefixes[first_sym].append(p)
        
        has_factoring = any(len(v) > 1 for k, v in prefixes.items() if k != 'ε')
        if has_factoring:
            final_g[nt] = []
            for f, p_list in prefixes.items():
                if len(p_list) > 1 and f != 'ε':
                    new_nt = f"{nt}f"
                    final_g[nt].append([f, new_nt])
                    final_g[new_nt] = [p[1:] if len(p) > 1 else ['ε'] for p in p_list]
                else: final_g[nt].extend(p_list)
        else: final_g[nt] = prods
    return final_g

def get_analysis_sets(grammar):
    first = {nt: set() for nt in grammar}
    def calc_f(s):
        if not s or (s not in grammar and s != 'ε'): return {s}
        if s == 'ε': return {'ε'}
        res = set()
        for p in grammar.get(s, []):
            for char in p:
                cf = calc_f(char)
                res.update(cf - {'ε'})
                if 'ε' not in cf: break
            else: res.add('ε')
        return res
    for nt in grammar: first[nt] = calc_f(nt)
    start = list(grammar.keys())[0] if grammar else ""
    follow = {nt: set() for nt in grammar}; follow[start].add('$')
    for _ in range(5):
        for nt, prods in grammar.items():
            for p in prods:
                for i, sym in enumerate(p):
                    if sym in grammar:
                        next_p = p[i+1:]
                        if next_p:
                            fn = set()
                            for s in next_p:
                                sf = first[s] if s in grammar else {s}
                                fn.update(sf - {'ε'})
                                if 'ε' not in sf: break
                            else: fn.add('ε')
                            follow[sym].update(fn - {'ε'})
                            if 'ε' in fn: follow[sym].update(follow[nt])
                        else: follow[sym].update(follow[nt])
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
                if a != 'ε' and a in table[nt]: table[nt][a] = f"{nt} -> {' '.join(p)}"
            if 'ε' in pf:
                for b in follow[nt]:
                    if b in table[nt]: table[nt][b] = f"{nt} -> {' '.join(p)}"
    return pd.DataFrame(table).T[terms]

# --- 3. محرك التقارير (PDF & Excel) ---

class PDFReport(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 10, "LL(1) Predictive Parsing Academic Report", ln=True, align="C")
        self.ln(5)

    def safe_text(self, text):
        return str(text).replace('→', '->').replace('ε', 'epsilon').replace('\'', 'p')

    def add_section(self, title, content_type, data):
        self.set_font("Helvetica", "B", 12)
        self.set_fill_color(230, 230, 230)
        self.cell(0, 10, title, ln=True, fill=True)
        self.ln(2)
        if content_type == "grammar":
            self.set_font("Courier", "", 10)
            for nt, prods in data.items():
                formatted = " | ".join([" ".join(p) for p in prods])
                self.cell(0, 7, self.safe_text(f"{nt} -> {formatted}"), ln=True)
        elif content_type == "table":
            self.set_font("Helvetica", "", 8)
            col_w = self.epw / (len(data.columns) + 1)
            self.cell(col_w, 8, "NT", 1)
            for c in data.columns: self.cell(col_w, 8, self.safe_text(c), 1)
            self.ln()
            for i, row in data.iterrows():
                if self.get_y() > 260: self.add_page()
                self.cell(col_w, 7, self.safe_text(i), 1)
                for v in row: self.cell(col_w, 7, self.safe_text(v), 1)
                self.ln()
        self.ln(5)

# --- 4. واجهة التطبيق والمحاكاة ---

with st.sidebar:
    st.header("📥 إدخال القواعد")
    raw_input = st.text_area("القواعد الأصلية:", "E → E + T | T\nT → T * F | F\nF → ( E ) | id", height=150)
    speed = st.slider("⏱️ سرعة المحاكاة:", 0.1, 2.0, 0.5)

grammar_raw = OrderedDict()
for line in raw_input.split('\n'):
    line = line.strip()
    if '→' in line or '->' in line:
        parts = re.split(r'→|->|=', line)
        if len(parts) == 2:
            lhs = parts[0].strip()
            rhs_raw = parts[1].strip()
            grammar_raw[lhs] = [p.strip().split() for p in rhs_raw.split('|')]

if grammar_raw:
    # 1. القواعد المصححة
    st.header("1️⃣ القواعد المصححة")
    fixed_g = auto_fix_grammar(grammar_raw)
    for nt, prods in fixed_g.items():
        formatted_prods = " | ".join([" ".join(p) for p in prods])
        st.markdown(f'<div class="ltr-text">{nt} → {formatted_prods}</div>', unsafe_allow_html=True)

    f_sets, fo_sets = get_analysis_sets(fixed_g)
    ff_df = pd.DataFrame({"First": [", ".join(list(s)) for s in f_sets.values()], "Follow": [", ".join(list(s)) for s in fo_sets.values()]}, index=f_sets.keys())
    
    st.header("2️⃣ مجموعات First & Follow")
    st.table(ff_df)

    st.header("3️⃣ مصفوفة الإعراب (M-Table)")
    m_table = build_m_table(fixed_g, f_sets, fo_sets)
    st.dataframe(m_table, use_container_width=True)

    st.header("4️⃣ & 5️⃣ المحاكاة والشجرة")
    user_input = st.text_input("أدخل الجملة المراد تحليلها (اترك مسافات وضع $ في النهاية):", "id + id * id $")
    
    if 'sim' not in st.session_state:
        st.session_state.sim = {'stack': [], 'idx': 0, 'dot': Digraph(), 'trace': [], 'done': False, 'node_id': 0, 'lvl': {0:0}}

    col_btn1, col_btn2 = st.columns(2)
    if col_btn1.button("🔄 ضبط / إعادة تعيين"):
        start = list(fixed_g.keys())[0]
        st.session_state.sim = {'stack': [('$', 0), (start, 0)], 'idx': 0, 'dot': Digraph(), 'trace': [], 'done': False, 'node_id': 0, 'lvl': {0:0}}
        st.session_state.sim['dot'].attr(rankdir='TD')
        st.session_state.sim['dot'].node("0", start, style='filled', fillcolor=LEVEL_COLORS[0])
        st.rerun()

    tree_area, trace_area = st.empty(), st.empty()

    if col_btn2.button("▶️ تشغيل تلقائي"):
        if not user_input.strip().endswith('$'):
            st.warning("⚠️ تنبيه: يجب إنهاء الجملة برمز ($) لضمان نجاح عملية التحليل.")
        else:
            tokens = user_input.split()
            s = st.session_state.sim
            while not s['done']:
                if s['stack']:
                    top, pid = s['stack'].pop()
                    lookahead = tokens[s['idx']] if s['idx'] < len(tokens) else '$'
                    step = {"Stack": " ".join([x for x, i in s['stack'] + [(top, pid)]]), "Input": " ".join(tokens[s['idx']:]), "Action": ""}
                    
                    if top == lookahead:
                        step["Action"] = f"Match {lookahead}"; s['idx'] += 1
                    elif top in fixed_g:
                        rule = m_table.at[top, lookahead]
                        if rule:
                            rhs = rule.split('->')[1].strip().split()
                            curr_lvl = s['lvl'].get(pid, 0) + 1
                            new_nodes = []
                            for sym in rhs:
                                s['node_id'] += 1
                                nid = str(s['node_id'])
                                s['lvl'][nid] = curr_lvl
                                color = LEVEL_COLORS[curr_lvl % len(LEVEL_COLORS)]
                                s['dot'].node(nid, sym, style='filled', fillcolor=color, shape='circle' if sym in fixed_g else 'ellipse')
                                s['dot'].edge(str(pid), nid)
                                if sym != 'ε': new_nodes.append((sym, nid))
                            for n in reversed(new_nodes): s['stack'].append(n)
                            step["Action"] = f"Apply {rule}"
                    if not s['stack'] or (top == '$' and lookahead == '$'): s['done'] = True
                    s['trace'].append(step)
                    tree_area.graphviz_chart(s['dot'])
                    trace_area.table(pd.DataFrame(s['trace']))
                    time.sleep(speed)
                else: s['done'] = True; break
            st.success("✅ اكتملت عملية التحليل.")

    # 6. التقارير
    st.header("6️⃣ تحميل التقارير النهائية")
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        out_ex = io.BytesIO()
        with pd.ExcelWriter(out_ex, engine='openpyxl') as writer:
            ff_df.to_excel(writer, sheet_name='Sets')
            m_table.to_excel(writer, sheet_name='M_Table')
        st.download_button("📥 تحميل التقرير (Excel)", out_ex.getvalue(), "LL1_Report.xlsx")

    with col_dl2:
        if st.button("📄 توليد تقرير PDF الشامل"):
            try:
                pdf = PDFReport()
                pdf.add_page()
                pdf.add_section("Original Grammar", "grammar", grammar_raw)
                pdf.add_section("Corrected Grammar", "grammar", fixed_g)
                pdf.add_section("First and Follow Sets", "table", ff_df)
                pdf.add_section("M-Table Action Table", "table", m_table)
                if st.session_state.sim['trace']:
                    pdf.add_section("Simulation Trace Steps", "table", pd.DataFrame(st.session_state.sim['trace']))
                    # حماية محرك الرسم (الخطوة 3)
                    try:
                        pdf.add_page()
                        pdf.set_font("Helvetica", "B", 14)
                        pdf.cell(0, 10, "Final Parse Tree Visualization", ln=True, align="C")
                        img_bytes = st.session_state.sim['dot'].pipe(format='png')
                        pdf.image(io.BytesIO(img_bytes), w=pdf.epw)
                    except Exception as e_img:
                        st.warning(f"تم توليد التقرير بدون صورة الشجرة بسبب: {e_img}. تأكد من وجود ملف packages.txt")
                
                st.download_button("📥 اضغط لتحميل PDF", bytes(pdf.output()), "LL1_Final_Report.pdf", "application/pdf")
            except Exception as e:
                st.error(f"حدث خطأ أثناء بناء PDF: {e}")

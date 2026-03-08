import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import re
import time
import io
from fpdf import FPDF

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="LL(1) Advanced Studio", layout="wide")

st.markdown("""
    <style>
    .main { direction: RTL; text-align: right; }
    [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    .ltr-text { direction: LTR !important; text-align: left !important; font-family: monospace; font-size: 16px; }
    .stTable, .stDataFrame { direction: LTR !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. وظائف التحليل المنطقي ---

def auto_fix_grammar(grammar):
    temp_g = OrderedDict()
    for nt, prods in grammar.items():
        rec = [p[1:] for p in prods if p and p == nt]
        non_rec = [p for p in prods if not (p and p == nt)]
        if rec:
            new_nt = f"{nt}'"
            temp_g[nt] = [p + [new_nt] for p in non_rec] if non_rec else [[new_nt]]
            temp_g[new_nt] = [p + [new_nt] for p in rec] + [['ε']]
        else: temp_g[nt] = prods
    
    final_g = OrderedDict()
    for nt, prods in temp_g.items():
        if len(prods) <= 1: final_g[nt] = prods; continue
        prefixes = {}
        for p in prods:
            f = p if p else 'ε'
            if f not in prefixes: prefixes[f] = []
            prefixes[f].append(p)
        if any(len(v) > 1 for k, v in prefixes.items() if k != 'ε'):
            final_g[nt] = []
            for f, p_list in prefixes.items():
                if len(p_list) > 1 and f != 'ε':
                    new_nt = f"{nt}_f"
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

# --- 3. محرك تقارير PDF المطور ---

class PDFReport(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 10, "LL(1) Predictive Parsing Academic Report", ln=True, align="C")
        self.ln(10)

    def safe_text(self, text):
        return str(text).replace('→', '->').replace('ε', 'epsilon').replace('\'', 'p')

    def add_section_title(self, title):
        self.set_font("Helvetica", "B", 12)
        self.set_fill_color(230, 230, 230)
        self.cell(0, 10, title, ln=True, fill=True)
        self.ln(3)

    def add_grammar(self, title, grammar_dict):
        self.add_section_title(title)
        self.set_font("Courier", "", 10)
        for nt, prods in grammar_dict.items():
            formatted = " | ".join([" ".join(p) for p in prods])
            self.cell(0, 7, self.safe_text(f"{nt} -> {formatted}"), ln=True)
        self.ln(5)

    def add_data_table(self, df, title):
        self.add_section_title(title)
        self.set_font("Helvetica", "B", 8)
        # تحديد العرض
        col_width = self.epw / (len(df.columns) + 1)
        # الرأس
        self.cell(col_width, 8, "NT", 1)
        for col in df.columns: self.cell(col_width, 8, self.safe_text(col), 1)
        self.ln()
        # البيانات
        self.set_font("Helvetica", "", 7)
        for i, row in df.iterrows():
            if self.get_y() > 260: self.add_page()
            self.cell(col_width, 7, self.safe_text(i), 1)
            for val in row:
                self.cell(col_width, 7, self.safe_text(val), 1)
            self.ln()
        self.ln(5)

# --- 4. واجهة التطبيق ---

with st.sidebar:
    st.header("📥 إدخال القواعد 🤖")
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
    fixed_g = auto_fix_grammar(grammar_raw)
    
    st.header("1️⃣ القواعد المصححة")
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
    user_input = st.text_input("أدخل الجملة المراد تحليلها (تذكر ترك مسافات ووضع $ في النهاية):", "id + id * id $")
    
    # --- فحص التنبيهات (الشرط الأول) ---
    if st.button("▶️ ابدأ التشغيل التلقائي"):
        if not user_input.strip().endswith('$'):
            st.warning("⚠️ تنبيه: يجب إنهاء الجملة برمز ($) لضمان نجاح عملية التحليل.")
        elif ' ' not in user_input.strip()[:-1] and len(user_input.strip()) > 3:
            st.info("💡 نصيحة: يرجى ترك مسافات بين الرموز (مثال: id + id) ليتعرف عليها المحلل بدقة.")
        else:
            # بدء المحاكاة
            tokens = user_input.split()
            start_sym = list(fixed_g.keys())[0]
            st.session_state.sim = {'stack': [('$', 0), (start_sym, 0)], 'idx': 0, 'dot': Digraph(), 'trace': [], 'done': False, 'node_id': 0}
            st.session_state.sim['dot'].attr(rankdir='TD')
            st.session_state.sim['dot'].node("0", start_sym, style='filled', fillcolor="#BBDEFB")
            
            tree_area = st.empty()
            trace_area = st.empty()
            
            s = st.session_state.sim
            while not s['done']:
                if s['stack']:
                    top, pid = s['stack'].pop()
                    lookahead = tokens[s['idx']]
                    step = {"Stack": " ".join([x for x, i in s['stack'] + [(top, pid)]]), "Input": " ".join(tokens[s['idx']:]), "Action": ""}
                    
                    if top == lookahead:
                        step["Action"] = f"Match {lookahead}"; s['idx'] += 1
                    elif top in fixed_g:
                        rule = m_table.at[top, lookahead]
                        if rule:
                            rhs = rule.split('->')[1].strip().split()
                            new_nodes = []
                            for sym in rhs:
                                s['node_id'] += 1
                                nid = s['node_id']
                                s['dot'].node(str(nid), sym, style='filled', fillcolor="#C8E6C9" if sym in fixed_g else "#FFF9C4")
                                s['dot'].edge(str(pid), str(nid))
                                if sym != 'ε': new_nodes.append((sym, nid))
                            for n in reversed(new_nodes): s['stack'].append(n)
                            step["Action"] = f"Apply {rule}"
                    
                    if not s['stack'] or (top == '$' and lookahead == '$'): s['done'] = True
                    s['trace'].append(step)
                    tree_area.graphviz_chart(s['dot'])
                    trace_area.table(pd.DataFrame(s['trace']))
                    time.sleep(speed)
                else: break
            st.success("✅ اكتملت عملية التحليل.")

    # --- 6. التقارير (الشرط الثاني) ---
    st.header("6️⃣ تحميل التقارير النهائية")
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        out_ex = io.BytesIO()
        with pd.ExcelWriter(out_ex, engine='openpyxl') as writer:
            ff_df.to_excel(writer, sheet_name='Sets')
            m_table.to_excel(writer, sheet_name='M_Table')
        st.download_button("📥 تحميل التقرير (Excel)", out_ex.getvalue(), "LL1_Data_Report.xlsx")

    with col_dl2:
        if st.button("📄 توليد وتحميل تقرير PDF الشامل"):
            try:
                pdf = PDFReport()
                pdf.add_page()
                pdf.add_grammar("Original Grammar", grammar_raw)
                pdf.add_grammar("Corrected Grammar", fixed_g)
                pdf.add_data_table(ff_df, "First and Follow Sets")
                pdf.add_data_table(m_table, "M-Table Action Table")
                
                if 'sim' in st.session_state and st.session_state.sim['trace']:
                    pdf.add_data_table(pd.DataFrame(st.session_state.sim['trace']), "Simulation Trace Steps")
                    # إضافة الشجرة في نهاية الـ PDF
                    pdf.add_page()
                    pdf.add_section_title("Final Parse Tree Visualization")
                    img_bytes = st.session_state.sim['dot'].pipe(format='png')
                    img_stream = io.BytesIO(img_bytes)
                    pdf.image(img_stream, w=pdf.epw)
                
                st.download_button("📥 اضغط هنا لتحميل PDF الشامل", bytes(pdf.output()), "LL1_Full_Academic_Report.pdf", "application/pdf")
            except Exception as e:
                st.error(f"حدث خطأ أثناء بناء PDF: {e}")

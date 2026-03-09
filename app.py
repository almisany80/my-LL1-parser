import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import re
import time
import io
from fpdf import FPDF

# --- 1. إعدادات الصفحة والتنسيق ---
st.set_page_config(page_title="LL(1) Pro Studio", layout="wide")

st.markdown("""
    <style>
    .main { direction: RTL; text-align: right; }
    [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    .ltr-text { direction: LTR !important; text-align: left !important; font-family: monospace; font-size: 16px; }
    .stTable, .stDataFrame { direction: LTR !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. وظائف التحليل المنطقي المتقدمة (حل مشكلة First & Follow) ---

def get_first(grammar):
    # خوارزمية التكرار حتى الثبات لضمان حساب First بدقة
    first = {nt: set() for nt in grammar}
    
    def get_seq_first(sequence):
        res = set()
        if not sequence or sequence == ['ε']:
            return {'ε'}
        for sym in sequence:
            sym_f = first[sym] if sym in grammar else {sym}
            res.update(sym_f - {'ε'})
            if 'ε' not in sym_f:
                break
        else:
            res.add('ε')
        return res

    changed = True
    while changed:
        changed = False
        for nt in grammar:
            old_size = len(first[nt])
            for prod in grammar[nt]:
                first[nt].update(get_seq_first(prod))
            if len(first[nt]) > old_size:
                changed = True
    return first

def get_follow(grammar, start_symbol, first):
    follow = {nt: set() for nt in grammar}
    follow[start_symbol].add('$')
    
    def get_seq_first(sequence):
        res = set()
        if not sequence: return {'ε'}
        for sym in sequence:
            sym_f = first[sym] if sym in grammar else {sym}
            res.update(sym_f - {'ε'})
            if 'ε' not in sym_f: break
        else: res.add('ε')
        return res

    changed = True
    while changed:
        changed = False
        for nt, productions in grammar.items():
            for prod in productions:
                for i in range(len(prod)):
                    B = prod[i]
                    if B in grammar: # إذا كان الرمز غير طرفي
                        old_size = len(follow[B])
                        beta = prod[i+1:]
                        if beta:
                            first_beta = get_seq_first(beta)
                            follow[B].update(first_beta - {'ε'})
                            if 'ε' in first_beta:
                                follow[B].update(follow[nt])
                        else:
                            follow[B].update(follow[nt])
                        if len(follow[B]) > old_size:
                            changed = True
    return follow

def build_m_table(grammar, first, follow):
    terms = sorted(list({s for ps in grammar.values() for p in ps for s in p if s not in grammar and s != 'ε'}))
    if '$' in terms: terms.remove('$')
    terms.append('$')
    table = {nt: {t: "" for t in terms} for nt in grammar}
    
    def get_seq_first(sequence):
        res = set()
        if not sequence or sequence == ['ε']: return {'ε'}
        for sym in sequence:
            sym_f = first[sym] if sym in grammar else {sym}
            res.update(sym_f - {'ε'})
            if 'ε' not in sym_f: break
        else: res.add('ε')
        return res

    for nt, prods in grammar.items():
        for prod in prods:
            p_first = get_seq_first(prod)
            for a in p_first:
                if a != 'ε': table[nt][a] = f"{nt} -> {' '.join(prod)}"
            if 'ε' in p_first:
                for b in follow[nt]:
                    table[nt][b] = f"{nt} -> {' '.join(prod)}"
    return pd.DataFrame(table).T[terms]

def parse_grammar_flexible(raw_text):
    grammar = OrderedDict()
    lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
    for line in lines:
        parts = re.split(r'->|→|=', line)
        if len(parts) == 2:
            lhs = parts[0].strip()
            rhs_raw = parts[1].strip()
            options = rhs_raw.split('|')
            productions = []
            for opt in options:
                opt_str = opt.strip()
                # معالجة الرموز الملتصقة (مثل ABCDE) أو المنفصلة بمسافات
                if ' ' in opt_str:
                    symbols = [s.strip() for s in opt_str.split() if s.strip()]
                else:
                    symbols = re.findall(r"[A-Z]'?|[a-z]|ε|id|\(|\)|\+|\*|\-", opt_str)
                if symbols: productions.append(symbols)
                elif not opt_str or opt_str in ["ε", "epsilon"]: productions.append(["ε"])
            if lhs and productions: grammar[lhs] = productions
    return grammar

# --- 3. محرك تقارير PDF المطور ---

class PDFReport(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 10, "LL(1) Parsing Academic Report", ln=True, align="C")
        self.ln(10)

    def safe_text(self, text):
        return str(text).replace('→', '->').replace('ε', 'epsilon').replace('\'', 'p').replace('{', '').replace('}', '').replace("'", "")

    def add_section_title(self, title):
        self.set_font("Helvetica", "B", 12)
        self.set_fill_color(230, 230, 230)
        self.cell(0, 10, title, ln=True, fill=True)
        self.ln(3)

    def add_table_data(self, df, title):
        self.add_section_title(title)
        self.set_font("Helvetica", "", 8)
        col_width = self.epw / (len(df.columns) + 1)
        self.cell(col_width, 8, "NT", 1)
        for col in df.columns: self.cell(col_width, 8, self.safe_text(col), 1)
        self.ln()
        for i, row in df.iterrows():
            if self.get_y() > 260: self.add_page()
            self.cell(col_width, 7, self.safe_text(i), 1)
            for val in row:
                self.cell(col_width, 7, self.safe_text(val), 1)
            self.ln()
        self.ln(5)

# --- 4. واجهة التطبيق ---

with st.sidebar:
    st.header("📥 إدخال القواعد")
    raw_input = st.text_area("القواعد الأصلية:", "S → ABCDE\nA → a | ε\nB → b | ε\nC → c\nD → d | ε\nE → e | ε", height=150)
    speed = st.slider("⏱️ سرعة المحاكاة:", 0.1, 2.0, 0.5)

grammar_raw = parse_grammar_flexible(raw_input)

if grammar_raw:
    st.header("1️⃣ القواعد")
    for nt, prods in grammar_raw.items():
        formatted_prods = " | ".join([" ".join(p) for p in prods])
        st.markdown(f'<div class="ltr-text">{nt} → {formatted_prods}</div>', unsafe_allow_html=True)

    first_sets = get_first(grammar_raw)
    start_node_sym = list(grammar_raw.keys())[0]
    follow_sets = get_follow(grammar_raw, start_node_sym, first_sets)
    
    st.header("2️⃣ مجموعات First & Follow")
    ff_df = pd.DataFrame({
        "First": [", ".join(sorted(list(s))) for s in first_sets.values()],
        "Follow": [", ".join(sorted(list(s))) for s in follow_sets.values()]
    }, index=first_sets.keys())
    st.table(ff_df)

    st.header("3️⃣ مصفوفة الإعراب (M-Table)")
    m_table = build_m_table(grammar_raw, first_sets, follow_sets)
    st.dataframe(m_table, use_container_width=True)

    st.header("4️⃣ & 5️⃣ المحاكاة والشجرة")
    user_input = st.text_input("أدخل الجملة للتحليل (مثال: a b c d e $):", "a b c d e $")
    
    if st.button("▶️ ابدأ التشغيل التلقائي"):
        if not user_input.strip().endswith('$'):
            st.warning("⚠️ يجب إنهاء الجملة برمز ($).")
        else:
            tokens = user_input.split()
            st.session_state.sim = {'stack': [('$', -1), (start_node_sym, 0)], 'idx': 0, 'dot': Digraph(), 'trace': [], 'done': False, 'node_id': 0}
            st.session_state.sim['dot'].attr(rankdir='TD')
            st.session_state.sim['dot'].node("0", start_node_sym, style='filled', fillcolor="#BBDEFB")
            
            tree_area, trace_area = st.empty(), st.empty()
            s = st.session_state.sim
            while not s['done']:
                if s['stack']:
                    top, pid = s['stack'].pop()
                    lookahead = tokens[s['idx']] if s['idx'] < len(tokens) else '$'
                    step = {"Stack": " ".join([x for x, i in s['stack'] + [(top, pid)]]), "Input": " ".join(tokens[s['idx']:]), "Action": ""}
                    
                    if top == lookahead:
                        step["Action"] = f"Match {lookahead}"; s['idx'] += 1
                    elif top in grammar_raw:
                        rule = m_table.at[top, lookahead]
                        if rule:
                            rhs = rule.split('->')[1].strip().split()
                            new_nodes = []
                            for sym in rhs:
                                s['node_id'] += 1
                                nid = str(s['node_id'])
                                s['dot'].node(nid, sym, style='filled', fillcolor="#C8E6C9" if sym in grammar_raw else "#FFF9C4")
                                s['dot'].edge(str(pid), nid)
                                if sym != 'ε': new_nodes.append((sym, nid))
                            for n in reversed(new_nodes): s['stack'].append(n)
                            step["Action"] = f"Apply {rule}"
                    if not s['stack'] or (top == '$' and lookahead == '$'): s['done'] = True
                    s['trace'].append(step)
                    tree_area.graphviz_chart(s['dot'])
                    trace_area.table(pd.DataFrame(s['trace']))
                    time.sleep(speed)
                else: break
            st.success("✅ اكتمل التحليل.")

    st.header("6️⃣ تحميل التقارير")
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        out_ex = io.BytesIO()
        with pd.ExcelWriter(out_ex, engine='openpyxl') as writer:
            ff_df.to_excel(writer, sheet_name='Sets')
            m_table.to_excel(writer, sheet_name='M_Table')
        st.download_button("📥 تحميل Excel", out_ex.getvalue(), "LL1_Report.xlsx")

    with col_dl2:
        if st.button("📄 توليد تقرير PDF الشامل"):
            try:
                pdf = PDFReport()
                pdf.add_page()
                pdf.add_section_title("Grammar")
                for nt, prods in grammar_raw.items():
                    pdf.cell(0, 7, f"{nt} -> {' | '.join([' '.join(p) for p in prods])}", ln=True)
                pdf.add_table_data(ff_df, "First and Follow Sets")
                pdf.add_table_data(m_table, "Predictive Parsing Table")
                if 'sim' in st.session_state and st.session_state.sim['trace']:
                    pdf.add_table_data(pd.DataFrame(st.session_state.sim['trace']), "Simulation Trace")
                    pdf.add_page()
                    img_bytes = st.session_state.sim['dot'].pipe(format='png')
                    pdf.image(io.BytesIO(img_bytes), w=pdf.epw)
                st.download_button("📥 تحميل PDF", bytes(pdf.output()), "LL1_Full_Report.pdf", "application/pdf")
            except Exception as e:
                st.error(f"خطأ في بناء PDF: {e}")

import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import io
import os
from fpdf import FPDF

# 1. التنسيق الأكاديمي (RTL)
st.set_page_config(page_title="LL(1) Academic Studio V5.8", layout="wide")
st.markdown("""
    <style>
    .main { direction: RTL; text-align: right; }
    [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    .ltr-table { direction: LTR !important; text-align: left !important; font-family: 'Consolas', monospace; }
    .status-accepted { background-color: #2e7d32; color: white; padding: 15px; border-radius: 8px; text-align: center; font-weight: bold; margin-top:10px; }
    .status-rejected { background-color: #c62828; color: white; padding: 15px; border-radius: 8px; text-align: center; font-weight: bold; margin-top:10px; }
    .grammar-box { background-color: #f8f9fa; padding: 10px; border-radius: 5px; border-right: 5px solid #d32f2f; margin: 10px 0; font-family: monospace; }
    </style>
    """, unsafe_allow_html=True)

# 2. فئة إنشاء تقرير PDF (دعم الرموز الرياضية)
class AcademicPDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 12)
        self.cell(0, 10, 'LL(1) Parser Academic Report - University of Misan', 0, 1, 'C')
        self.ln(5)
    def add_section(self, title, df=None, grammar=None):
        self.set_font('Helvetica', 'B', 11)
        self.cell(0, 10, title, 0, 1, 'L')
        self.set_font('Courier', '', 9)
        if grammar:
            for k, v in grammar.items():
                line = f"{k} -> {' | '.join([' '.join(p) for p in v])}"
                self.cell(0, 8, line, 0, 1)
        if df is not None:
            self.set_font('Helvetica', '', 8)
            col_width = self.epw / len(df.columns)
            for col in df.columns: self.cell(col_width, 8, str(col), 1, 0, 'C')
            self.ln()
            for row in df.values:
                for datum in row: self.cell(col_width, 8, str(datum), 1, 0, 'C')
                self.ln()
        self.ln(5)

# 3. وظائف المعالجة النحوية
def remove_left_recursion(grammar):
    new_grammar = OrderedDict()
    for nt, prods in grammar.items():
        recursive = [p[1:] for p in prods if p and p[0] == nt]
        non_recursive = [p for p in prods if not (p and p[0] == nt)]
        if recursive:
            new_nt = f"{nt}'"; new_grammar[nt] = [p + [new_nt] for p in non_recursive] if non_recursive else [[new_nt]]
            new_grammar[new_nt] = [p + [new_nt] for p in recursive] + [['ε']]
        else: new_grammar[nt] = prods
    return new_grammar

def apply_left_factoring(grammar):
    new_grammar = OrderedDict()
    for nt, prods in grammar.items():
        if len(prods) <= 1: new_grammar[nt] = prods; continue
        prods.sort(); prefix = os.path.commonprefix([tuple(p) for p in prods])
        if prefix:
            new_nt = f"{nt}f"; new_grammar[nt] = [list(prefix) + [new_nt]]
            suffix = [p[len(prefix):] if p[len(prefix):] else ['ε'] for p in prods]; new_grammar[new_nt] = suffix
        else: new_grammar[nt] = prods
    return new_grammar

def get_ff(grammar):
    first = {nt: set() for nt in grammar}
    def get_seq_first(seq):
        res = set()
        if not seq or seq == ['ε']: return {'ε'}
        for s in seq:
            sf = first[s] if s in grammar else {s}; res.update(sf - {'ε'})
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
    follow = {nt: set() for nt in grammar}; follow[list(grammar.keys())[0]].add('$')
    while True:
        changed = False
        for nt, prods in grammar.items():
            for p in prods:
                for i, B in enumerate(p):
                    if B in grammar:
                        old_len = len(follow[B]); beta = p[i+1:]
                        if beta:
                            fb = get_seq_first(beta); follow[B].update(fb - {'ε'})
                            if 'ε' in fb: follow[B].update(follow[nt])
                        else: follow[B].update(follow[nt])
                        if len(follow[B]) > old_len: changed = True
        if not changed: break
    return first, follow

# 4. إدارة الحالة (Session State)
if 'sim' not in st.session_state:
    st.session_state.sim = {'trace': [], 'dot': None, 'status': None, 'stack': [], 'idx': 0, 'node_id': 0, 'finished': False, 'tokens': []}

with st.sidebar:
    st.header("⚙️ لوحة التحكم")
    def_g = "E -> T E'\nE' -> + T E' | ε\nT -> F T'\nT' -> * F T' | ε\nF -> ( E ) | id"
    raw_in = st.text_area("القواعد النحوية:", def_g, height=150)
    u_input = st.text_input("الجملة (مثلاً id + id $):", "id + id * id $")
    
    if st.button("🗑 مسح الجملة وإعادة الضبط"):
        st.session_state.sim = {'trace': [], 'dot': None, 'status': None, 'stack': [], 'idx': 0, 'node_id': 0, 'finished': False, 'tokens': []}
        st.rerun()

# 5. المعالجة الأساسية
grammar_raw = OrderedDict()
for line in raw_in.strip().split('\n'):
    if '->' in line:
        lhs, rhs = line.split('->')
        grammar_raw[lhs.strip()] = [opt.strip().split() for opt in rhs.split('|')]

if grammar_raw:
    fixed_g = apply_left_factoring(remove_left_recursion(grammar_raw))
    f_sets, fo_sets = get_ff(fixed_g)
    
    # بناء M-Table
    terms = sorted(list({s for ps in fixed_g.values() for p in ps for s in p if s not in fixed_g and s != 'ε'})) + ['$']
    m_data = {nt: {t: [] for t in terms} for nt in fixed_g}
    for nt, prods in fixed_g.items():
        for p in prods:
            p_f = set()
            for s in p:
                sf = f_sets[s] if s in fixed_g else {s}; p_f.update(sf - {'ε'})
                if 'ε' not in sf: break
            else: p_f.add('ε')
            for a in p_f:
                if a != 'ε': m_data[nt][a].append(f"{nt}->{' '.join(p)}")
            if 'ε' in p_f:
                for b in fo_sets[nt]: m_data[nt][b].append(f"{nt}->{' '.join(p)}")
    
    m_table = pd.DataFrame("", index=fixed_g.keys(), columns=terms)
    for nt in fixed_g:
        for t in terms:
            rules = list(set(m_data[nt].get(t, [])))
            m_table.at[nt, t] = rules[0] if len(rules) == 1 else (" | ".join(rules) if len(rules) > 1 else "")

    # عرض الجداول
    st.header("1️⃣ الجداول الأكاديمية")
    ff_df = pd.DataFrame({"First": [str(f_sets[n]) for n in fixed_g], "Follow": [str(fo_sets[n]) for n in fixed_g]}, index=fixed_g.keys())
    st.table(ff_df)
    st.subheader("M-Table (Parsing Table)")
    st.dataframe(m_table, use_container_width=True)

    # 6. محرك التتبع (Tracing Engine)
    def run_step(stack, tokens, idx, node_id, dot, trace):
        if not stack: return idx, node_id, True, "Accepted"
        top, pid = stack.pop(); look = tokens[idx] if idx < len(tokens) else '$'
        
        # التأكد من بقاء الرموز الرياضية نصوصاً صريحة
        current_stack_str = " ".join([v for v, i in stack] + [top])
        current_input_str = " ".join(tokens[idx:])
        step = {"Stack": current_stack_str, "Input": current_input_str, "Action": ""}
        
        if top == look:
            step["Action"] = f"Match {look}"; idx += 1; trace.append(step)
            return idx, node_id, (top == '$'), "Accepted" if top == '$' else None
        elif top in fixed_g:
            rules = list(set(m_data[top].get(look, [])))
            if len(rules) == 1:
                rhs = rules[0].split('->')[1].strip().split()
                if rhs == ['ε']: rhs = []
                step["Action"] = f"Apply {rules[0]}"; trace.append(step)
                temp = []
                for sym in rhs:
                    node_id += 1; nid = str(node_id)
                    dot.node(nid, f'"{sym}"', style='filled', fillcolor='#C8E6C9') # رسم رياضي
                    dot.edge(pid, nid); temp.append((sym, nid))
                if not rhs:
                    node_id += 1; nid = str(node_id); dot.node(nid, '"ε"', style='filled', fillcolor='#F8BBD0'); dot.edge(pid, nid)
                for item in reversed(temp): stack.append(item)
                return idx, node_id, False, None
            else:
                step["Action"] = f"Error: No rule for ({top}, {look})"; trace.append(step); return idx, node_id, True, "Rejected"
        else:
            step["Action"] = f"Error: Expected {top}"; trace.append(step); return idx, node_id, True, "Rejected"

    st.header("2️⃣ المحاكاة (Simulation)")
    col1, col2 = st.columns([1, 4])
    
    # زر التشغيل التلقائي
    if col1.button("▶ تشغيل تلقائي"):
        st.session_state.sim.update({'tokens': u_input.split(), 'stack': [('$', '0'), (list(fixed_g.keys())[0], '0')], 
                                    'dot': Digraph(), 'node_id': 0, 'idx': 0, 'trace': [], 'finished': False})
        st.session_state.sim['dot'].node('0', f'"{list(fixed_g.keys())[0]}"', style='filled', fillcolor='#BBDEFB')
        s = st.session_state.sim
        while not s['finished']:
            s['idx'], s['node_id'], s['finished'], s['status'] = run_step(s['stack'], s['tokens'], s['idx'], s['node_id'], s['dot'], s['trace'])

    # زر خطوة بخطوة
    if col2.button("⏭ خطوة بخطوة"):
        s = st.session_state.sim
        if not s['stack'] and not s['finished']:
            s.update({'tokens': u_input.split(), 'stack': [('$', '0'), (list(fixed_g.keys())[0], '0')], 
                     'dot': Digraph(), 'node_id': 0, 'idx': 0, 'trace': []})
            s['dot'].node('0', f'"{list(fixed_g.keys())[0]}"', style='filled', fillcolor='#BBDEFB')
        
        if not s['finished']:
            s['idx'], s['node_id'], s['finished'], s['status'] = run_step(s['stack'], s['tokens'], s['idx'], s['node_id'], s['dot'], s['trace'])

    # عرض النتائج
    if st.session_state.sim['trace']:
        st.markdown("**جدول تتبع الاشتقاق (Trace Table):**")
        st.table(pd.DataFrame(st.session_state.sim['trace']))
        st.graphviz_chart(st.session_state.sim['dot'])
        if st.session_state.sim['finished']:
            st.markdown(f'<div class="status-{st.session_state.sim["status"].lower()}">{st.session_state.sim["status"]}</div>', unsafe_allow_html=True)

    # 7. تصدير التقارير (PDF & Excel)
    st.header("3️⃣ تصدير التقارير")
    cp, ce = st.columns(2)
    with cp:
        if st.button("📄 تصدير تقرير PDF"):
            pdf = AcademicPDF(); pdf.add_page()
            pdf.add_section("1. Corrected Grammar", grammar=fixed_g)
            pdf.add_section("2. First & Follow Sets", df=ff_df.reset_index())
            pdf.add_section("3. M-Table", df=m_table.reset_index())
            if st.session_state.sim['trace']:
                pdf.add_section("4. Execution Trace", df=pd.DataFrame(st.session_state.sim['trace']))
            st.download_button("📥 تحميل ملف PDF", pdf.output(), "LL1_Parser_Report.pdf", "application/pdf")

    with ce:
        output = io.BytesIO()
        try:
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                ff_df.to_excel(writer, sheet_name='First_Follow')
                m_table.to_excel(writer, sheet_name='M_Table')
                if st.session_state.sim['trace']:
                    pd.DataFrame(st.session_state.sim['trace']).to_excel(writer, sheet_name='Trace', index=False)
            st.download_button("📥 تحميل ملف Excel", output.getvalue(), "LL1_Data.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        except:
            st.warning("يرجى التأكد من تثبيت مكتبة xlsxwriter لتصدير الإكسل.")

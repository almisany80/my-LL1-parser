import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import io
import os
from fpdf import FPDF

# 1. التنسيق الأكاديمي (RTL)
st.set_page_config(page_title="LL(1) Compiler Studio V5.7", layout="wide")
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

# 2. وظائف المعالجة النحوية
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
        if len(prods) <= 1: new_grammar[nt] = prods; continue
        prods.sort()
        prefix = os.path.commonprefix([tuple(p) for p in prods])
        if prefix:
            new_nt = f"{nt}f"
            new_grammar[nt] = [list(prefix) + [new_nt]]
            suffix = [p[len(prefix):] if p[len(prefix):] else ['ε'] for p in prods]
            new_grammar[new_nt] = suffix
        else: new_grammar[nt] = prods
    return new_grammar

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

# 3. إدارة الحالة (Session State)
if 'sim' not in st.session_state:
    st.session_state.sim = {'trace': [], 'dot': None, 'status': None, 'stack': [], 'idx': 0, 'node_id': 0, 'finished': False}
if 'input_val' not in st.session_state: st.session_state.input_val = "id + id * id $"

# 4. الواجهة الجانبية (Sidebar)
with st.sidebar:
    st.header("⚙️ لوحة التحكم")
    def_g = "E -> T E'\nE' -> + T E' | ε\nT -> F T'\nT' -> * F T' | ε\nF -> ( E ) | id"
    raw_in = st.text_area("القواعد النحوية:", def_g, height=180)
    
    # حقل الإدخال مع زر المسح
    u_input = st.text_input("الجملة المختبرة:", value=st.session_state.input_val, key="sentence_input")
    if st.button("🗑 مسح الجملة وإعادة ضبط"):
        st.session_state.input_val = ""
        st.session_state.sim = {'trace': [], 'dot': None, 'status': None, 'stack': [], 'idx': 0, 'node_id': 0, 'finished': False}
        st.rerun()

# 5. بناء الجداول
grammar_raw = OrderedDict()
for line in raw_in.strip().split('\n'):
    if '->' in line:
        lhs, rhs = line.split('->')
        grammar_raw[lhs.strip()] = [opt.strip().split() for opt in rhs.split('|')]

if grammar_raw:
    fixed_g = apply_left_factoring(remove_left_recursion(grammar_raw))
    f_sets, fo_sets = get_first_follow_stable(fixed_g)
    
    st.header("1️⃣ الجداول الرياضية")
    ff_df = pd.DataFrame({"First": [str(f_sets[n]) for n in fixed_g], "Follow": [str(fo_sets[n]) for n in fixed_g]}, index=fixed_g.keys())
    st.table(ff_df)

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

    st.subheader("M-Table")
    st.dataframe(m_table, use_container_width=True)

    # 6. محاكاة التتبع وإصلاح الرموز
    st.header("2️⃣ تتبع الجملة والشجرة")
    
    def run_step(stack, tokens, idx, node_id, dot, trace):
        if not stack: return idx, node_id, True, "Accepted"
        top, pid = stack.pop(); look = tokens[idx] if idx < len(tokens) else '$'
        # ظهور العلامات الرياضية بشكل سليم في المكدس
        step = {"Stack": " ".join([v for v, i in stack] + [top]), "Input": " ".join(tokens[idx:]), "Action": ""}
        
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
                    dot.node(nid, f'"{sym}"', style='filled', fillcolor='#C8E6C9') # الإصلاح البصري
                    dot.edge(pid, nid); temp.append((sym, nid))
                if not rhs:
                    node_id += 1; nid = str(node_id); dot.node(nid, '"ε"', style='filled', fillcolor='#F8BBD0'); dot.edge(pid, nid)
                for item in reversed(temp): stack.append(item)
                return idx, node_id, False, None
            else:
                step["Action"] = "Error"; trace.append(step); return idx, node_id, True, "Rejected"
        else:
            step["Action"] = "Error"; trace.append(step); return idx, node_id, True, "Rejected"

    if st.button("▶ تشغيل المحاكاة"):
        tokens = u_input.split(); stack = [('$', '0'), (list(fixed_g.keys())[0], '0')]
        idx, node_id, trace = 0, 0, []
        dot = Digraph(); dot.node('0', f'"{list(fixed_g.keys())[0]}"', style='filled', fillcolor='#BBDEFB')
        fin, stat = False, "Rejected"
        while not fin: idx, node_id, fin, stat = run_step(stack, tokens, idx, node_id, dot, trace)
        st.session_state.sim.update({'trace': trace, 'dot': dot, 'finished': True, 'status': stat})

    if st.session_state.sim['trace']:
        st.table(pd.DataFrame(st.session_state.sim['trace']))
        st.graphviz_chart(st.session_state.sim['dot'])
        st.markdown(f'<div class="status-{st.session_state.sim["status"].lower()}">{st.session_state.sim["status"]}</div>', unsafe_allow_html=True)

    # 7. تصدير التقارير (إصلاح ExcelWriter)
    st.header("3️⃣ تصدير التقارير")
    try:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            ff_df.to_excel(writer, sheet_name='First_Follow')
            m_table.to_excel(writer, sheet_name='M_Table')
            if st.session_state.sim['trace']:
                pd.DataFrame(st.session_state.sim['trace']).to_excel(writer, sheet_name='Tracing_Report', index=False)
        
        st.download_button(label="📥 تحميل تقرير Excel المتكامل", data=output.getvalue(), file_name="LL1_Academic_Report.xlsx", mime="application/vnd.ms-excel")
    except ModuleNotFoundError:
        st.error("⚠️ خطأ: يرجى إضافة 'xlsxwriter' إلى ملف requirements.txt لتفعيل ميزة تصدير الإكسل.")

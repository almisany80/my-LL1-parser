import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import io
import os
from fpdf import FPDF

# 1. التنسيق الأكاديمي (RTL & Styling)
st.set_page_config(page_title="LL(1) Compiler Studio V5", layout="wide")
st.markdown("""
    <style>
    .main { direction: RTL; text-align: right; }
    [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    .ltr-table { direction: LTR !important; text-align: left !important; font-family: 'Consolas', monospace; }
    .status-accepted { background-color: #2e7d32; color: white; padding: 15px; border-radius: 8px; text-align: center; font-weight: bold; }
    .status-rejected { background-color: #c62828; color: white; padding: 15px; border-radius: 8px; text-align: center; font-weight: bold; }
    .conflict-msg { background-color: #ffebee; color: #b71c1c; padding: 15px; border-left: 5px solid #b71c1c; margin: 10px 0; font-weight: bold; border-radius: 5px; }
    .grammar-box { background-color: #f8f9fa; padding: 10px; border-radius: 5px; border-right: 5px solid #d32f2f; margin: 10px 0; font-family: monospace; }
    </style>
    """, unsafe_allow_html=True)

# 2. الدوال البرمجية الأساسية
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

def highlight_conflicts(val):
    if "|" in str(val): return 'background-color: #ffcdd2; color: #b71c1c; font-weight: bold'
    return ''

# 3. إدارة الحالة
if 'sim' not in st.session_state:
    st.session_state.sim = {'trace': [], 'dot': None, 'status': None, 'stack': [], 'idx': 0, 'node_id': 0, 'finished': False, 'tokens': []}
if 'last_grammar' not in st.session_state: st.session_state.last_grammar = ""

# 4. الواجهة الجانبية
with st.sidebar:
    st.header("⚙️ المدخلات")
    raw_in = st.text_area("أدخل القواعد:", "S -> i e T S S' | a\nS' -> e S | ε\nT -> b", height=150)
    
    if raw_in != st.session_state.last_grammar:
        st.session_state.sim = {'trace': [], 'dot': None, 'status': None, 'stack': [], 'idx': 0, 'node_id': 0, 'finished': False, 'tokens': []}
        st.session_state.last_grammar = raw_in

    u_input = st.text_input("الجملة:", "i e b a $")
    if st.button("🔄 مسح الذاكرة وإعادة الضبط"):
        st.session_state.sim = {'trace': [], 'dot': None, 'status': None, 'stack': [], 'idx': 0, 'node_id': 0, 'finished': False, 'tokens': []}
        st.rerun()

# 5. معالجة القواعد (مع حل مشكلة الشاشة البيضاء)
grammar_raw = OrderedDict()
for line in raw_in.split('\n'):
    if '->' in line:
        lhs, rhs = line.split('->')
        grammar_raw[lhs.strip()] = [opt.strip().split() for opt in rhs.split('|')]

if grammar_raw:
    fixed_g = apply_left_factoring(remove_left_recursion(grammar_raw))
    
    # [هنا يتم عرض النتائج، الجدول، التتبع..]
    st.header("1️⃣ مراجعة القواعد")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("القواعد الأصلية")
        for k, v in grammar_raw.items(): st.markdown(f'<div class="grammar-box ltr-table">{k} → {" | ".join([" ".join(p) for p in v])}</div>', unsafe_allow_html=True)
    with c2:
        st.subheader("القواعد المعالجة")
        for k, v in fixed_g.items(): st.markdown(f'<div class="grammar-box ltr-table" style="border-right-color:#2e7d32">{k} → {" | ".join([" ".join(p) for p in v])}</div>', unsafe_allow_html=True)

    f_sets, fo_sets = get_first_follow_stable(fixed_g)
    
    # بناء M-Table
    terms = sorted(list({s for ps in fixed_g.values() for p in ps for s in p if s not in fixed_g and s != 'ε'})) + ['$']
    m_data = {nt: {t: [] for t in terms} for nt in fixed_g}
    is_ll1 = True

    for nt, prods in fixed_g.items():
        for p in prods:
            p_first = set()
            for s in p:
                sf = f_sets[s] if s in fixed_g else {s}
                p_first.update(sf - {'ε'})
                if 'ε' not in sf: break
            else: p_first.add('ε')
            for a in p_first:
                if a != 'ε': m_data[nt][a].append(f"{nt}->{''.join(p)}")
            if 'ε' in p_first:
                for b in fo_sets[nt]: m_data[nt][b].append(f"{nt}->{''.join(p)}")

    final_table = pd.DataFrame("", index=fixed_g.keys(), columns=terms)
    for nt in fixed_g:
        for t in terms:
            rules = list(set(m_data[nt][t]))
            if len(rules) > 1:
                is_ll1 = False
                final_table.at[nt, t] = " | ".join(rules)
            elif len(rules) == 1:
                final_table.at[nt, t] = rules[0]

    st.header("2️⃣ مصفوفة الإعراب (M-Table)")
    styled_table = final_table.style.applymap(highlight_conflicts)
    st.dataframe(styled_table, use_container_width=True)

    if not is_ll1:
        st.markdown('<div class="conflict-msg">⚠️ هذه القواعد ليست من نوع LL(1): يوجد تضارب في الخلايا المظللة باللون الأحمر.</div>', unsafe_allow_html=True)

    # المحاكاة الأكاديمية
    st.header("3️⃣ المحاكاة (Parsing Trace)")
    col_run, col_step = st.columns([1, 4])
    
    def get_rem_input(t, i): return " ".join(t[i:]) if i < len(t) else "$"

    if col_run.button("▶ تشغيل كامل"):
        # منطق التشغيل الكامل... (يمكنك استنساخ نفس منطق الخطوة التالية هنا)
        pass 
    
    if col_step.button("⏭ خطوة تالية"):
        if not st.session_state.sim['stack'] and not st.session_state.sim['finished']:
            st.session_state.sim['tokens'] = u_input.split()
            st.session_state.sim['stack'] = [('$', '0'), (list(fixed_g.keys())[0], '0')]
        
        if st.session_state.sim['stack'] and not st.session_state.sim['finished']:
            stack = st.session_state.sim['stack']; tokens = st.session_state.sim['tokens']
            idx = st.session_state.sim['idx']; top, pid = stack.pop()
            look = tokens[idx] if idx < len(tokens) else '$'
            
            step = {"Stack": " ".join([s for s, i in stack] + [top]), "Input": get_rem_input(tokens, idx), "Action": ""}
            
            if top == look:
                step["Action"] = f"Match {look}"; st.session_state.sim['idx'] += 1
                if top == '$': st.session_state.sim['finished'] = True; st.session_state.sim['status'] = "Accepted"
            elif top in fixed_g:
                rules = list(set(m_data[top][look]))
                if len(rules) == 1:
                    step["Action"] = f"Apply {rules[0]}"
                    rhs = rules[0].split('->')[1].replace('ε', '').strip()
                    for sym in reversed(list(rhs)): stack.append((sym, '0'))
                else: step["Action"] = "❌ Conflict"; st.session_state.sim['finished'] = True
            else: step["Action"] = "❌ Error"; st.session_state.sim['finished'] = True
            st.session_state.sim['trace'].append(step)

    if st.session_state.sim['trace']:
        st.table(pd.DataFrame(st.session_state.sim['trace']))

else:
    st.info("ℹ️ يرجى إدخال قواعد نحوية صحيحة في القائمة الجانبية للبدء (مثال: A -> B C).")

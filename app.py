import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import io
import os
from fpdf import FPDF

# 1. التنسيق العام (RTL) ودعم المظهر الأكاديمي
st.set_page_config(page_title="LL(1) Academic Studio V5", layout="wide")
st.markdown("""
    <style>
    .main { direction: RTL; text-align: right; }
    [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    .ltr-table { direction: LTR !important; text-align: left !important; font-family: 'Consolas', monospace; }
    .status-accepted { background-color: #2e7d32; color: white; padding: 15px; border-radius: 8px; text-align: center; font-weight: bold; }
    .status-rejected { background-color: #c62828; color: white; padding: 15px; border-radius: 8px; text-align: center; font-weight: bold; }
    .conflict-msg { background-color: #ffebee; color: #b71c1c; padding: 15px; border-left: 5px solid #b71c1c; margin: 10px 0; font-weight: bold; border-radius: 5px; }
    .grammar-box { background-color: #f8f9fa; padding: 10px; border-radius: 5px; border-right: 5px solid #d32f2f; margin: 10px 0; font-family: monospace; }
    .info-box { background-color: #e3f2fd; color: #0d47a1; padding: 20px; border-radius: 10px; border-right: 5px solid #2196f3; }
    </style>
    """, unsafe_allow_html=True)

# 2. وظائف المعالجة النحوية (Refactoring)
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

# 3. حساب First & Follow بطريقة الاستقرار
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

# 4. إدارة الحالة (Session State)
if 'sim' not in st.session_state:
    st.session_state.sim = {'trace': [], 'dot': None, 'status': None, 'stack': [], 'idx': 0, 'node_id': 0, 'finished': False, 'tokens': []}
if 'last_raw' not in st.session_state: st.session_state.last_raw = ""

# 5. الواجهة الجانبية (Sidebar)
with st.sidebar:
    st.header("⚙️ لوحة التحكم")
    default_grammar = "S -> i e T S S' | a\nS' -> e S | ε\nT -> b"
    raw_in = st.text_area("أدخل القواعد النحوية:", default_grammar, height=180)
    
    # تصفير البيانات عند تغيير القواعد لمنع الشاشة البيضاء
    if raw_in != st.session_state.last_raw:
        st.session_state.sim = {'trace': [], 'dot': None, 'status': None, 'stack': [], 'idx': 0, 'node_id': 0, 'finished': False, 'tokens': []}
        st.session_state.last_raw = raw_in

    u_input = st.text_input("الجملة المختبرة (مع مسافات):", "i e b a $")
    if st.button("🔄 إعادة ضبط السيرفر"):
        st.rerun()

# 6. المعالجة والعرض الرئيسي
grammar_raw = OrderedDict()
for line in raw_in.strip().split('\n'):
    if '->' in line:
        lhs, rhs = line.split('->')
        grammar_raw[lhs.strip()] = [opt.strip().split() for opt in rhs.split('|')]

if grammar_raw:
    fixed_g = apply_left_factoring(remove_left_recursion(grammar_raw))
    f_sets, fo_sets = get_first_follow_stable(fixed_g)
    
    st.header("1️⃣ مراجعة القواعد")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("القواعد الأصلية")
        for k, v in grammar_raw.items(): st.markdown(f'<div class="grammar-box ltr-table">{k} → {" | ".join([" ".join(p) for p in v])}</div>', unsafe_allow_html=True)
    with c2:
        st.subheader("القواعد المصححة")
        for k, v in fixed_g.items(): st.markdown(f'<div class="grammar-box ltr-table" style="border-right-color:#2e7d32">{k} → {" | ".join([" ".join(p) for p in v])}</div>', unsafe_allow_html=True)

    # حساب مصفوفة الإعراب وكشف التضارب
    terms = sorted(list({s for ps in fixed_g.values() for p in ps for s in p if s not in fixed_g and s != 'ε'})) + ['$']
    m_data = {nt: {t: [] for t in terms} for nt in fixed_g}
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

    m_table = pd.DataFrame("", index=fixed_g.keys(), columns=terms)
    is_ll1 = True
    for nt in fixed_g:
        for t in terms:
            rules = list(set(m_data[nt][t]))
            if len(rules) > 1:
                is_ll1 = False
                m_table.at[nt, t] = " | ".join(rules)
            elif len(rules) == 1:
                m_table.at[nt, t] = rules[0]

    st.header("2️⃣ جداول التحليل (Sets & Matrix)")
    st.table(pd.DataFrame({"First": [str(f_sets[n]) for n in fixed_g], "Follow": [str(fo_sets[n]) for n in fixed_g]}, index=fixed_g.keys()))
    
    st.subheader("Predictive Parsing Table (M-Table)")
    st.dataframe(m_table.style.applymap(highlight_conflicts), use_container_width=True)
    if not is_ll1:
        st.markdown('<div class="conflict-msg">⚠️ تنبيه: هذه القواعد ليست LL(1) بسبب التضارب الموضح باللون الأحمر.</div>', unsafe_allow_html=True)

    # 7. محاكاة تتبع الجملة (Academic Trace)
    st.header("3️⃣ تتبع الجملة (Tracing)")
    b1, b2 = st.columns([1, 4])
    
    def get_input_str(tokens, i): return " ".join(tokens[i:]) if i < len(tokens) else "$"

    if b1.button("▶ تشغيل تلقائي"):
        tokens = u_input.split(); idx, node_id, trace = 0, 0, []
        stack = [('$', '0'), (list(fixed_g.keys())[0], '0')]
        dot = Digraph(); dot.node('0', list(fixed_g.keys())[0], style='filled', fillcolor='#BBDEFB')
        while stack:
            top, pid = stack.pop(); look = tokens[idx] if idx < len(tokens) else '$'
            step = {"Stack": " ".join([s for s, i in stack] + [top]), "Input": get_input_str(tokens, idx), "Action": ""}
            if top == look:
                step["Action"] = f"Match {look}"; idx += 1
                if top == '$': st.session_state.sim['status'] = "Accepted"; trace.append(step); break
            elif top in fixed_g:
                rules = list(set(m_data[top][look]))
                if len(rules) == 1:
                    rhs = rules[0].split('->')[1].replace('ε', '').strip()
                    step["Action"] = f"Apply {rules[0]}"
                    for sym in reversed(list(rhs)):
                        node_id += 1; nid = str(node_id)
                        dot.node(nid, sym, style='filled', fillcolor='#C8E6C9')
                        dot.edge(pid, nid); stack.append((sym, nid))
                else: step["Action"] = "Error"; trace.append(step); break
            else: step["Action"] = "Error"; trace.append(step); break
            trace.append(step)
        st.session_state.sim.update({'trace': trace, 'dot': dot, 'finished': True})

    if b2.button("⏭ خطوة بخطوة"):
        if not st.session_state.sim['stack'] and not st.session_state.sim['finished']:
            st.session_state.sim.update({'tokens': u_input.split(), 'stack': [('$', '0'), (list(fixed_g.keys())[0], '0')], 
                                        'dot': Digraph(), 'node_id': 0, 'idx': 0})
            st.session_state.sim['dot'].node('0', list(fixed_g.keys())[0], style='filled', fillcolor='#BBDEFB')
        
        s = st.session_state.sim
        if s['stack'] and not s['finished']:
            top, pid = s['stack'].pop(); look = s['tokens'][s['idx']] if s['idx'] < len(s['tokens']) else '$'
            step = {"Stack": " ".join([v for v, i in s['stack']] + [top]), "Input": get_input_str(s['tokens'], s['idx']), "Action": ""}
            if top == look:
                step["Action"] = f"Match {look}"; s['idx'] += 1
                if top == '$': s['status'] = "Accepted"; s['finished'] = True
            elif top in fixed_g:
                rules = list(set(m_data[top][look]))
                if len(rules) == 1:
                    rhs = rules[0].split('->')[1].replace('ε', '').strip()
                    step["Action"] = f"Apply {rules[0]}"
                    for sym in reversed(list(rhs)):
                        s['node_id'] += 1; nid = str(s['node_id'])
                        s['dot'].node(nid, sym, style='filled', fillcolor='#C8E6C9')
                        s['dot'].edge(pid, nid); s['stack'].append((sym, nid))
                else: s['status'] = "Rejected"; s['finished'] = True
            else: s['status'] = "Rejected"; s['finished'] = True
            s['trace'].append(step)

    if st.session_state.sim['trace']:
        st.table(pd.DataFrame(st.session_state.sim['trace']))
        if st.session_state.sim['finished']:
            res = st.session_state.sim['status']
            st.markdown(f'<div class="status-{"accepted" if res=="Accepted" else "rejected"}">{res}</div>', unsafe_allow_html=True)
        st.graphviz_chart(st.session_state.sim['dot'])

else:
    # رسالة الحماية من الواجهة البيضاء
    st.markdown('<div class="info-box">👋 مرحباً بك دكتور حسنين. يرجى إدخال القواعد في القائمة الجانبية (مثال: E -> T E\') للبدء في التحليل.</div>', unsafe_allow_html=True)

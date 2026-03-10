import streamlit as st
import pandas as pd
import re
from collections import OrderedDict
from graphviz import Digraph
import io, os, tempfile
from fpdf import FPDF

# 1. الإعدادات والجماليات
st.set_page_config(page_title="LL(1) Pro Studio V7.0", layout="wide")
st.markdown("""
    <style>
    .main { direction: RTL; text-align: right; }
    [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    textarea, input[type="text"] { direction: LTR !important; text-align: left !important; font-family: 'monospace'; font-size: 16px; }
    .stTable td { white-space: pre !important; font-family: 'monospace'; }
    .welcome-card { background-color: #f8f9fa; padding: 20px; border-radius: 12px; border-right: 8px solid #28a745; margin-bottom: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    </style>
    """, unsafe_allow_html=True)

# 2. تهيئة الذاكرة
if 'state' not in st.session_state:
    st.session_state.state = {'done': False, 'status': "", 'trace': [], 'dot': None, 'n_id': 0, 'stack': []}

if "g_input" not in st.session_state:
    st.session_state.g_input = "A -> B a | b\nB -> A c | d" # مثال للتكرار غير المباشر
if "s_input" not in st.session_state:
    st.session_state.s_input = "d c a $"

# 3. محرك المعالجة المتقدم (إصلاح مشاكل الصورة image_a52bd3)
def robust_parse(raw_text):
    grammar = OrderedDict()
    lines = raw_text.strip().split('\n')
    for line in lines:
        # توحيد الأسهم والرموز
        line = line.replace("→", "->").replace("=>", "->").replace("/", "|").replace("ε", "epsilon")
        if '->' in line:
            lhs, rhs = line.split('->')
            lhs = lhs.strip()
            # تقسيم الخيارات بناءً على | ثم تقسيم الرموز داخل كل خيار بناءً على المسافات
            options = []
            for opt in rhs.split('|'):
                symbols = opt.strip().split()
                if symbols: options.append(symbols)
            if lhs in grammar: grammar[lhs].extend(options)
            else: grammar[lhs] = options
    return grammar

# 4. خوارزمية إزالة التكرار (المباشر وغير المباشر)
def eliminate_left_recursion(g):
    nts = list(g.keys())
    for i in range(len(nts)):
        for j in range(i):
            # معالجة التكرار غير المباشر (A_i -> A_j gamma)
            ai, aj = nts[i], nts[j]
            new_prods = []
            for prod in g[ai]:
                if prod and prod[0] == aj:
                    gamma = prod[1:]
                    for aj_prod in g[aj]:
                        new_prods.append(aj_prod + gamma)
                else: new_prods.append(prod)
            g[ai] = new_prods
        
        # معالجة التكرار المباشر (A_i -> A_i alpha)
        curr = nts[i]
        alphas = [p[1:] for p in g[curr] if p and p[0] == curr]
        betas = [p for p in g[curr] if not (p and p[0] == curr)]
        
        if alphas:
            new_nt = f"{curr}'"
            g[curr] = [p + [new_nt] for p in betas] if betas else [[new_nt]]
            g[new_nt] = [p + [new_nt] for p in alphas] + [['ε']]
    return g

# 5. الواجهة الجانبية
with st.sidebar:
    st.header("🛠 الإعدادات الأكاديمية")
    raw_in = st.text_area("أدخل القواعد (دعم / و | و التكرار غير المباشر):", key="g_input", height=200)
    sentence = st.text_input("الجملة المختبرة:", key="s_input")
    if st.button("🔄 إعادة ضبط النظام"):
        st.session_state.clear()
        st.rerun()

st.markdown('<div class="welcome-card"><h2>🎓 مختبر المترجمات المتطور V7.0</h2><p>بإشراف الدكتور حسنين - معالجة تلقائية للتكرار المباشر وغير المباشر</p></div>', unsafe_allow_html=True)

# تنفيذ المنطق
grammar = robust_parse(raw_in)

if not grammar:
    st.info("💡 بانتظار إدخال القواعد... جرب إدخال قواعد بها تكرار غير مباشر مثل: A -> B a | b ثم B -> A c | d")
else:
    # 1. إزالة التكرار
    fixed_g = eliminate_left_recursion(grammar)
    
    # 2. حساب First & Follow
    def get_first_follow(g):
        first = {nt: set() for nt in g}
        def get_s_first(seq):
            res = set()
            if not seq or seq == ['ε']: return {'ε'}
            for s in seq:
                f_s = first[s] if s in g else {s}
                res.update(f_s - {'ε'})
                if 'ε' not in f_s: break
            else: res.add('ε')
            return res
        
        for _ in range(10): # Iterative fixed point
            for nt, prods in g.items():
                for p in prods: first[nt].update(get_s_first(p))
        
        follow = {nt: set() for nt in g}; follow[list(g.keys())[0]].add('$')
        for _ in range(10):
            for nt, prods in g.items():
                for p in prods:
                    for i, B in enumerate(p):
                        if B in g:
                            beta = p[i+1:]
                            f_beta = get_s_first(beta)
                            follow[B].update(f_beta - {'ε'})
                            if 'ε' in f_beta: follow[B].update(follow[nt])
        return first, follow

    f_s, fo_s = get_first_follow(fixed_g)
    
    # 3. بناء الجدول (M-Table)
    terms = sorted(list({s for ps in fixed_g.values() for p in ps for s in p if s not in fixed_g and s != 'ε'})) + ['$']
    m_table = pd.DataFrame("", index=fixed_g.keys(), columns=terms)
    for nt, prods in fixed_g.items():
        for p in prods:
            p_first = set()
            for s in p:
                s_f = f_s[s] if s in fixed_g else {s}; p_first.update(s_f - {'ε'})
                if 'ε' not in s_f: break
            else: p_first.add('ε')
            for a in p_first:
                if a != 'ε': m_table.at[nt, a] = f"{nt}->{' '.join(p)}"
            if 'ε' in p_first:
                for b in fo_s[nt]: m_table.at[nt, b] = f"{nt}->{' '.join(p)}"

    # العرض
    st.subheader("📝 القواعد بعد المعالجة (Elimination of Left Recursion)")
    cols = st.columns(len(fixed_g))
    for i, (nt, prods) in enumerate(fixed_g.items()):
        cols[i % 3].code(f"{nt} -> {' | '.join([' '.join(p) for p in prods])}")

    st.subheader("📊 جداول التحليل الرياضي")
    c1, c2 = st.columns([1, 2])
    with c1: st.table(pd.DataFrame({"First": [str(f_s[n]) for n in fixed_g], "Follow": [str(fo_s[n]) for n in fixed_g]}, index=fixed_g.keys()))
    with c2: st.dataframe(m_table, use_container_width=True)

    # 4. المحاكاة (Trace)
    if st.button("▶ تشغيل التحليل بالكامل"):
        st.session_state.state['trace'] = []
        stack = [('$', '0'), (list(fixed_g.keys())[0], '0')]
        tokens = sentence.split()
        ptr = 0
        dot = Digraph(); dot.node('0', list(fixed_g.keys())[0])
        n_id = 0
        
        while stack:
            top, pid = stack.pop()
            look = tokens[ptr] if ptr < len(tokens) else '$'
            action = ""
            
            if top == look:
                action = f"Match {look}"; ptr += 1
                if top == '$': st.session_state.state['status'] = "✅ Accepted"
            elif top in fixed_g:
                rule = m_table.at[top, look]
                if rule:
                    action = f"Apply {rule}"
                    rhs = rule.split('->')[1].split()
                    if rhs != ['ε']:
                        tmp = []
                        for s in rhs:
                            n_id += 1; nid = str(n_id)
                            dot.node(nid, s); dot.edge(pid, nid)
                            tmp.append((s, nid))
                        for item in reversed(tmp): stack.append(item)
                    else:
                        n_id += 1; nid = f"e{n_id}"; dot.node(nid, "ε", shape="none"); dot.edge(pid, nid)
                else:
                    action = "❌ Error"; st.session_state.state['status'] = "❌ Rejected"; break
            else: action = "❌ Error"; st.session_state.state['status'] = "❌ Rejected"; break
            
            st.session_state.state['trace'].append({"Stack": [x[0] for x in stack] + [top], "Input": tokens[ptr:], "Action": action})
        
        st.session_state.state['dot'] = dot
        st.session_state.state['done'] = True

    if st.session_state.state['done']:
        st.table(pd.DataFrame(st.session_state.state['trace']))
        st.graphviz_chart(st.session_state.state['dot'])
        st.success(st.session_state.state['status'])

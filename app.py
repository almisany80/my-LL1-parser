import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import io
from fpdf import FPDF

# 1. التنسيق الأكاديمي (RTL & Styling)
st.set_page_config(page_title="LL(1) Conflict Detector Pro", layout="wide")
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

# 2. الدوال البرمجية الأساسية (Core Logic)
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

# دالة تلوين الخلايا المتضاربة
def highlight_conflicts(val):
    if "|" in str(val):
        return 'background-color: #ffcdd2; color: #b71c1c; font-weight: bold'
    return ''

# 3. إدارة الحالة (Session State)
if 'sim' not in st.session_state:
    st.session_state.sim = {'trace': [], 'dot': None, 'status': None, 'stack': [], 'idx': 0, 'node_id': 0, 'finished': False}
if 'last_grammar' not in st.session_state:
    st.session_state.last_grammar = ""

# 4. واجهة المستخدم (UI)
with st.sidebar:
    st.header("⚙️ المدخلات")
    # القواعد الافتراضية التي تحتوي على التضارب كما ذكرت
    default_text = "S -> i e T S S' | a\nS' -> e S | ε\nT -> b"
    raw_in = st.text_area("أدخل القواعد:", default_text, height=150)
    
    # تصفير الحالة عند تغيير القواعد لمنع الشاشة البيضاء
    if raw_in != st.session_state.last_grammar:
        st.session_state.sim = {'trace': [], 'dot': None, 'status': None, 'stack': [], 'idx': 0, 'node_id': 0, 'finished': False}
        st.session_state.last_grammar = raw_in

    u_input = st.text_input("الجملة المراد تتبعها:", "i e b a $")
    if st.button("🔄 مسح الذاكرة وإعادة الضبط"):
        st.rerun()

# معالجة النصوص
grammar = OrderedDict()
for line in raw_in.split('\n'):
    if '->' in line:
        lhs, rhs = line.split('->')
        grammar[lhs.strip()] = [opt.strip().split() for opt in rhs.split('|')]

if grammar:
    st.header("1️⃣ مراجعة القواعد")
    for k, v in grammar.items():
        st.markdown(f'<div class="grammar-box ltr-table">{k} → {" | ".join([" ".join(p) for p in v])}</div>', unsafe_allow_html=True)

    # حساب المجموعات
    f_sets, fo_sets = get_first_follow_stable(grammar)
    
    st.header("2️⃣ جداول First & Follow")
    ff_df = pd.DataFrame({
        "First": [", ".join(sorted(list(s))) for s in f_sets.values()],
        "Follow": [", ".join(sorted(list(s))) for s in fo_sets.values()]
    }, index=f_sets.keys())
    st.table(ff_df)

    # بناء M-Table مع كشف التضارب
    terms = sorted(list({s for ps in grammar.values() for p in ps for s in p if s not in grammar and s != 'ε'})) + ['$']
    m_data = {nt: {t: [] for t in terms} for nt in grammar}
    is_ll1 = True

    for nt, prods in grammar.items():
        for p in prods:
            p_first = set()
            for s in p:
                sf = f_sets[s] if s in grammar else {s}
                p_first.update(sf - {'ε'})
                if 'ε' not in sf: break
            else: p_first.add('ε')
            for a in p_first:
                if a != 'ε': m_data[nt][a].append(f"{nt}->{''.join(p)}")
            if 'ε' in p_first:
                for b in fo_sets[nt]: m_data[nt][b].append(f"{nt}->{''.join(p)}")

    # تحويل البيانات لجدول عرض مع تلوين
    final_table = pd.DataFrame("", index=grammar.keys(), columns=terms)
    for nt in grammar:
        for t in terms:
            rules = list(set(m_data[nt][t]))
            if len(rules) > 1:
                is_ll1 = False
                final_table.at[nt, t] = " | ".join(rules)
            elif len(rules) == 1:
                final_table.at[nt, t] = rules[0]

    st.header("3️⃣ مصفوفة الإعراب (M-Table)")
    # تطبيق التلوين
    styled_table = final_table.style.applymap(highlight_conflicts)
    st.dataframe(styled_table, use_container_width=True)

    if not is_ll1:
        st.markdown('<div class="conflict-msg">⚠️ هذه القواعد ليست من نوع LL(1): يوجد تضارب في الخلايا المظللة باللون الأحمر (Multiple Entries).</div>', unsafe_allow_html=True)

    # 4. المحاكاة (Simulation)
    st.header("4️⃣ التتبع والشجرة")
    col1, col2 = st.columns([1, 4])
    
    if col1.button("▶ تشغيل المحاكاة"):
        tokens = u_input.split()
        stack = [('$', '0'), (list(grammar.keys())[0], '0')]
        idx, node_id, trace = 0, 0, []
        dot = Digraph(); dot.attr(rankdir='TD')
        dot.node('0', list(grammar.keys())[0], style='filled', fillcolor='#BBDEFB')
        status = "Rejected"
        
        while stack:
            top, pid = stack.pop(); look = tokens[idx] if idx < len(tokens) else '$'
            step = {"Stack": " ".join([s for s, i in stack] + [top]), "Input": look, "Action": ""}
            
            if top == look:
                step["Action"] = f"Match {look}"; idx += 1
                if top == '$': status = "Accepted"; trace.append(step); break
            elif top in grammar:
                rules = list(set(m_data[top][look]))
                if len(rules) == 1:
                    rhs = rules[0].split('->')[1].replace('ε', '').strip()
                    step["Action"] = f"Apply {rules[0]}"
                    for sym in reversed(list(rhs)):
                        node_id += 1; nid = str(node_id)
                        dot.node(nid, sym, style='filled', fillcolor='#C8E6C9')
                        dot.edge(pid, nid)
                        stack.append((sym, nid))
                elif len(rules) > 1:
                    step["Action"] = "❌ Conflict Error"; trace.append(step); break
                else:
                    step["Action"] = "❌ No Rule"; trace.append(step); break
            else:
                step["Action"] = "❌ Error"; trace.append(step); break
            trace.append(step)
        st.session_state.sim = {'trace': trace, 'dot': dot, 'status': status, 'finished': True}

    if st.session_state.sim['trace']:
        st.table(pd.DataFrame(st.session_state.sim['trace']))
        if st.session_state.sim['finished']:
            color_class = "status-accepted" if st.session_state.sim['status'] == "Accepted" else "status-rejected"
            st.markdown(f'<div class="{color_class}">{st.session_state.sim["status"]}</div>', unsafe_allow_html=True)
        st.graphviz_chart(st.session_state.sim['dot'])

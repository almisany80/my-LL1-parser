import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import re
import time
import io
import copy

# --- 1. إعدادات الصفحة والتنسيق (RTL للأب والـ LTR للجداول التقنية) ---
st.set_page_config(page_title="LL(1) Professional Studio", layout="wide")

st.markdown("""
    <style>
    .main { direction: RTL; text-align: right; }
    [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    /* تنسيق الجداول لتظهر من اليسار لليمين LTR */
    .ltr-table { direction: LTR !important; text-align: left !important; }
    .stDataFrame, [data-testid="stTable"] { direction: LTR !important; text-align: left !important; }
    /* الحفاظ على اتجاه الكود */
    code, pre, .stCode { direction: LTR !important; text-align: left !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. محركات التصحيح والحسابات ---

def auto_fix_grammar(grammar):
    # إزالة التداخل اليساري (LR)
    temp_g = OrderedDict()
    for nt, prods in grammar.items():
        rec = [p[1:] for p in prods if p and p[0] == nt]
        non_rec = [p for p in prods if not (p and p[0] == nt)]
        if rec:
            new_nt = f"{nt}'"
            temp_g[nt] = [p + [new_nt] for p in non_rec] if non_rec else [[new_nt]]
            temp_g[new_nt] = [p + [new_nt] for p in rec] + [['ε']]
        else: temp_g[nt] = prods
    
    # إزالة العامل المشترك (LF)
    final_g = OrderedDict()
    for nt, prods in temp_g.items():
        if len(prods) <= 1: final_g[nt] = prods; continue
        prefixes = {}
        for p in prods:
            f = p[0] if p else 'ε'
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
                            for s in next_p: # تم تصحيح الخطأ هنا من next_part إلى next_p
                                sf = first[s] if s in grammar else {s}
                                fn.update(sf - {'ε'})
                                if 'ε' not in sf: break
                            else: fn.add('ε')
                            follow[sym].update(fn - {'ε'})
                            if 'ε' in fn: follow[sym].update(follow[nt])
                        else:
                            follow[sym].update(follow[nt])
    return first, follow

def build_m_table(grammar, first, follow):
    # ترتيب الأعمدة: الحروف أولاً ثم $ في النهاية (لجهة اليمين في LTR)
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
                if a != 'ε' and a in table[nt]: table[nt][a] = f"{nt} → {' '.join(p)}"
            if 'ε' in pf:
                for b in follow[nt]: 
                    if b in table[nt]: table[nt][b] = f"{nt} → {' '.join(p)}"
    return pd.DataFrame(table).T[terms] # ضمان ترتيب الأعمدة

# --- 3. منطق المحاكاة ---

def perform_step():
    s = st.session_state.sim
    grammar = st.session_state.fixed_grammar
    m_table = st.session_state.m_table
    tokens = st.session_state.tokens
    
    if s['stack'] and not s['done']:
        top, pid = s['stack'].pop()
        look = tokens[s['idx']]
        
        step = {"المكدس": " ".join([x for x, i in s['stack'] + [(top, pid)]]), "المؤشر": look, "الإجراء": ""}
        
        if top == look:
            step["الإجراء"] = f"✅ مطابقة {look}"
            s['idx'] += 1
        elif top in grammar:
            rule = m_table.at[top, look]
            if rule and rule != "":
                rhs = rule.split('→')[1].strip().split()
                new_nodes = []
                for sym in rhs:
                    s['node_id'] += 1
                    nid = s['node_id']
                    s['dot'].node(str(nid), sym, style='filled', fillcolor="#C8E6C9" if sym in grammar else "#FFF9C4")
                    s['dot'].edge(str(pid), str(nid))
                    if sym != 'ε': new_nodes.append((sym, nid))
                for n in reversed(new_nodes): s['stack'].append(n)
                step["الإجراء"] = f"تطبيق {rule}"
            else:
                s['done'] = True
                step["الإجراء"] = "❌ خطأ في الإعراب"
        
        if not s['stack'] or (top == '$' and look == '$'): s['done'] = True
        s['trace'].append(step)
        return True
    return False

# --- 4. واجهة التطبيق ---

with st.sidebar:
    st.header("📥 إدخال القواعد")
    raw_input = st.text_area("أدخل القواعد:", "E → E + T | T\nT → T * F | F\nF → ( E ) | id", height=150)
    speed = st.slider("⏱️ سرعة العرض (ثواني):", 0.1, 2.0, 0.5)

grammar_raw = {}
for line in raw_input.split('\n'):
    if '→' in line or '->' in line:
        parts = re.split(r'→|->|=', line)
        grammar_raw[parts[0].strip()] = [p.strip().split() for p in parts[1].split('|')]

if grammar_raw:
    # 1. القواعد المصححة
    st.header("1️⃣ القواعد المصححة")
    fixed_g = auto_fix_grammar(grammar_raw)
    st.session_state.fixed_grammar = fixed_g
    st.write(fixed_g)

    # 2. First & Follow
    st.header("2️⃣ مجموعات First & Follow")
    f_sets, fo_sets = get_analysis_sets(fixed_g)
    ff_df = pd.DataFrame({
        "Non-Terminal": list(f_sets.keys()),
        "First": [", ".join(list(s)) for s in f_sets.values()],
        "Follow": [", ".join(list(s)) for s in fo_sets.values()]
    })
    st.markdown('<div class="ltr-table">', unsafe_allow_html=True)
    st.table(ff_df)
    st.markdown('</div>', unsafe_allow_html=True)

    # 3. M-Table
    st.header("3️⃣ مصفوفة الإعراب (M-Table)")
    m_table = build_m_table(fixed_g, f_sets, fo_sets)
    st.session_state.m_table = m_table
    st.markdown('<div class="ltr-table">', unsafe_allow_html=True)
    st.dataframe(m_table, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # المحاكاة
    st.header("4️⃣ & 5️⃣ المحاكاة والشجرة")
    user_input = st.text_input("الجملة:", "id + id * id")
    st.session_state.tokens = user_input.split() + ['$']

    if 'sim' not in st.session_state:
        st.session_state.sim = {'stack': [], 'idx': 0, 'dot': Digraph(), 'trace': [], 'done': False, 'node_id': 0}

    col_btn1, col_btn2 = st.columns(2)
    
    if col_btn1.button("🔄 ضبط / إعادة تعيين"):
        start = list(fixed_g.keys())[0]
        st.session_state.sim = {'stack': [('$', 0), (start, 0)], 'idx': 0, 'dot': Digraph(), 'trace': [], 'done': False, 'node_id': 0}
        st.session_state.sim['dot'].attr(rankdir='TD')
        st.session_state.sim['dot'].node("0", start, style='filled', fillcolor="#BBDEFB")
        st.rerun()

    # الحاويات التفاعلية
    col_tree, col_trace = st.columns([2, 1])
    tree_area = col_tree.empty()
    trace_area = col_trace.empty()

    if col_btn2.button("▶️ تشغيل تلقائي"):
        while not st.session_state.sim['done']:
            if perform_step():
                tree_area.graphviz_chart(st.session_state.sim['dot'])
                trace_area.table(pd.DataFrame(st.session_state.sim['trace']))
                time.sleep(speed)
            else: break
    
    # ضمان بقاء العرض بعد الانتهاء
    if st.session_state.sim['trace']:
        tree_area.graphviz_chart(st.session_state.sim['dot'])
        trace_area.table(pd.DataFrame(st.session_state.sim['trace']))

    # 6. التقرير
    st.header("6️⃣ تحميل التقرير النهائي")
    if st.button("📄 توليد تقرير Excel"):
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            ff_df.to_excel(writer, sheet_name='First_Follow', index=False)
            m_table.to_excel(writer, sheet_name='M_Table')
            if st.session_state.sim['trace']:
                pd.DataFrame(st.session_state.sim['trace']).to_excel(writer, sheet_name='Trace', index=False)
        st.download_button("📥 تحميل الآن", out.getvalue(), "LL1_Studio_Report.xlsx")

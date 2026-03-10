import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import io, os, tempfile
from fpdf import FPDF

# 1. إعدادات الهوية البصرية والتنسيق الأكاديمي (RTL)
st.set_page_config(page_title="LL(1) Compiler Studio - Misan University", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Tajawal', sans-serif; direction: RTL; text-align: right; }
    .header-container { background-color: #ffffff; padding: 20px; border-radius: 10px; border-bottom: 4px solid #1E3A8A; margin-bottom: 25px; }
    .header-text { line-height: 1.3; color: #1E3A8A; }
    .main-title { font-size: 26px; font-weight: bold; }
    .sub-title { font-size: 19px; color: #4B5563; }
    .stTable td { white-space: pre !important; font-family: 'monospace' !important; text-align: center; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f8fafc; color: #1e3a8a;
              text-align: center; padding: 10px; font-weight: bold; border-top: 3px solid #1e3a8a; z-index: 1000; }
    .status-msg { padding: 15px; border-radius: 8px; text-align: center; font-weight: bold; font-size: 18px; margin: 15px 0; }
    .accepted { background-color: #d1fae5; color: #065f46; border: 1px solid #34d399; }
    .rejected { background-color: #fee2e2; color: #991b1b; border: 1px solid #f87171; }
    </style>
    <div class="footer">أ.م. حسنين رحيم كريم - مختبر المترجمات الذكي 2026 ©</div>
    """, unsafe_allow_html=True)

# 2. الهيدر الأكاديمي (الشعار في اليسار والنصوص في اليمين)
header_col_left, header_col_right = st.columns([1, 4])

with header_col_left:
    # حل مشكلة MediaFileStorageError: التأكد من وجود الملف
    logo_file = "logo.jpg"
    if os.path.exists(logo_file):
        st.image(logo_file, width=130)
    else:
        st.warning("⚠️ شعار logo.jpg غير موجود")

with header_col_right:
    st.markdown("""
        <div class="header-text">
            <div class="main-title">جامعة ميسان</div>
            <div class="sub-title">كلية التربية</div>
            <div class="sub-title">قسم علوم الحاسبات</div>
        </div>
        """, unsafe_allow_html=True)

st.divider()

# 3. محرك معالجة القواعد (Deep Factoring & Recursion)
def parse_rules(text):
    g = OrderedDict()
    for line in text.strip().split('\n'):
        if '->' in line:
            lhs, rhs = line.split('->')
            g[lhs.strip()] = [p.strip().split() for p in rhs.split('|')]
    return g

def fix_recursion(g):
    new_g = OrderedDict()
    for nt, prods in g.items():
        rec = [p[1:] for p in prods if p and p[0] == nt]
        non_rec = [p for p in prods if not (p and p[0] == nt)]
        if rec:
            nt_p = f"{nt}'"
            new_g[nt] = [p + [nt_p] for p in (non_rec if non_rec else [['ε']])]
            new_g[nt_p] = [p + [nt_p] for p in rec] + [['ε']]
        else: new_g[nt] = prods
    return new_g

def fix_factoring(g):
    res_g = OrderedDict()
    for nt, prods in g.items():
        curr = prods.copy()
        while True:
            prefixes = {}
            for p in curr:
                if p and p != ['ε']:
                    s = p[0]
                    prefixes[s] = prefixes.get(s, 0) + 1
            common = [s for s, c in prefixes.items() if c > 1]
            if not common: break
            
            target = common[0]
            new_nt = f"{nt}f"
            while new_nt in g or new_nt in res_g: new_nt += "f"
            
            rem_prods = []
            new_curr = []
            for p in curr:
                if p and p[0] == target:
                    rem_prods.append(p[1:] if p[1:] else ['ε'])
                else: new_curr.append(p)
            new_curr.append([target, new_nt])
            res_g[new_nt] = rem_prods
            curr = new_curr
        res_g[nt] = curr
    return res_g

def get_sets(g):
    first = {nt: set() for nt in g}
    def find_f(seq):
        res = set()
        if not seq or seq == ['ε']: return {'ε'}
        for s in seq:
            sf = first[s] if s in g else {s}
            res.update(sf - {'ε'})
            if 'ε' not in sf: break
        else: res.add('ε')
        return res
    for _ in range(10):
        for nt, prods in g.items():
            for p in prods: first[nt].update(find_f(p))
    follow = {nt: set() for nt in g}
    if g: follow[list(g.keys())[0]].add('$')
    for _ in range(10):
        for nt, prods in g.items():
            for p in prods:
                for i, B in enumerate(p):
                    if B in g:
                        nxt = p[i+1:]
                        if nxt:
                            fn = find_f(nxt); follow[B].update(fn - {'ε'})
                            if 'ε' in fn: follow[B].update(follow[nt])
                        else: follow[B].update(follow[nt])
    return first, follow

# 4. إدارة الجلسة (Session State)
if 'st' not in st.session_state:
    st.session_state.st = {'trace': [], 'stack': [], 'done': False, 'dot': Digraph(), 'id': 0, 'status': ""}

with st.sidebar:
    st.header("⚙️ الإعدادات")
    raw_input = st.text_area("أدخل القواعد:", "S -> i E t S | i E t S e S | a\nE -> b", height=150)
    input_str = st.text_input("الجملة المختبرة:", "i b t a e a $")
    if st.button("🔄 إعادة تصفير النظام"):
        st.session_state.st = {'trace': [], 'stack': [], 'done': False, 'dot': Digraph(), 'id': 0, 'status': ""}
        st.rerun()

# 5. بناء الجداول والعرض
orig_g = parse_rules(raw_input)
if orig_g:
    # المعالجة
    final_g = fix_factoring(fix_recursion(orig_g))
    first_s, follow_s = get_sets(final_g)
    
    # جدول التنبؤ
    terms = sorted(list({s for ps in final_g.values() for p in ps for s in p if s not in final_g and s != 'ε'})) + ['$']
    m_table = pd.DataFrame("", index=final_g.keys(), columns=terms)
    for nt, prods in final_g.items():
        for p in prods:
            pf = set()
            for s in p:
                sf = first_s[s] if s in final_g else {s}; pf.update(sf - {'ε'})
                if 'ε' not in sf: break
            else: pf.add('ε')
            for a in pf:
                if a != 'ε': m_table.at[nt, a] = f"{nt}->{' '.join(p)}"
            if 'ε' in pf:
                for b in follow_s[nt]: m_table.at[nt, b] = f"{nt}->{' '.join(p)}"

    # العرض المرئي
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("📋 القواعد الأصلية")
        for k, v in orig_g.items(): st.code(f"{k} → {' | '.join([' '.join(p) for p in v])}")
    with col_b:
        st.subheader("🛠 القواعد المعالجة (LL1)")
        for k, v in final_g.items(): st.code(f"{k} → {' | '.join([' '.join(p) for p in v])}")

    st.subheader("🔍 مجموعات First & Follow")
    ff_df = pd.DataFrame({"First": [str(sorted(list(first_s[n]))) for n in final_g], 
                          "Follow": [str(sorted(list(follow_s[n]))) for n in final_g]}, index=final_g.keys())
    st.table(ff_df)

    st.subheader("📊 جدول التنبؤ (Parsing Table)")
    st.dataframe(m_table, use_container_width=True)

    # 6. التتبع (Parsing Trace)
    st.divider()
    st.subheader("⏳ التتبع الحي للجملة")
    s_state = st.session_state.st
    
    if not s_state['stack']:
        s_state['stack'] = [('$', '0'), (list(final_g.keys())[0], '0')]
        s_state['dot'] = Digraph(); s_state['dot'].node('0', list(final_g.keys())[0], style='filled', fillcolor='lightblue')

    def execute_step():
        if s_state['done'] or not s_state['stack']: return
        tokens = input_str.split(); matched = sum(1 for x in s_state['trace'] if "Match" in x['Action'])
        look = tokens[matched] if matched < len(tokens) else '$'
        top, pid = s_state['stack'].pop()
        step_data = {"Stack": " ".join([v for v, i in s_state['stack']] + [top]), "Input": " ".join(tokens[matched:]), "Action": ""}
        
        if top == look:
            step_data["Action"] = f"Match {look}"
            if top == '$': s_state['done'], s_state['status'] = True, "✅ Accepted"
        elif top in final_g:
            rule = m_table.at[top, look]
            if rule:
                step_data["Action"] = f"Apply {rule}"; rhs = rule.split('->')[1].split()
                if rhs == ['ε']:
                    s_state['id'] += 1; eid = f"e{s_state['id']}"; s_state['dot'].node(eid, "ε", shape='plaintext'); s_state['dot'].edge(pid, eid)
                else:
                    nodes = []
                    for sym in rhs:
                        s_state['id'] += 1; nid = str(s_state['id'])
                        s_state['dot'].node(nid, sym, style='filled', fillcolor='#d4edda'); s_state['dot'].edge(pid, nid)
                        nodes.append((sym, nid))
                    for item in reversed(nodes): s_state['stack'].append(item)
            else: s_state['done'], s_state['status'] = True, "❌ Rejected (No Rule)"
        else: s_state['done'], s_state['status'] = True, "❌ Rejected (Mismatch)"
        s_state['trace'].append(step_data)

    trace_c1, trace_c2 = st.columns(2)
    if trace_c1.button("⏭ خطوة تالية (Step)"): execute_step(); st.rerun()
    if trace_c2.button("▶ تشغيل كامل (Run All)"):
        while not s_state['done']: execute_step()
        st.rerun()

    if s_state['trace']:
        st.table(pd.DataFrame(s_state['trace']))
        st.subheader("🌲 شجرة الاشتقاق (Parse Tree)")
        st.graphviz_chart(s_state['dot'])
        if s_state['done']:
            css_cls = "accepted" if "✅" in s_state['status'] else "rejected"
            st.markdown(f'<div class="status-msg {css_cls}">{s_state["status"]}</div>', unsafe_allow_html=True)

    # 7. التصدير
    st.divider()
    st.subheader("📥 تصدير التقارير النهائية")
    exp_col1, exp_col2 = st.columns(2)
    with exp_col1:
        if st.button("📄 تصدير PDF"):
            pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 14)
            pdf.cell(0, 10, "Academic Compiler Report - Misan University", 0, 1, 'C')
            st.download_button("📥 تحميل PDF", bytes(pdf.output()), "LL1_Report.pdf")
    with exp_col2:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
            ff_df.to_excel(wr, sheet_name='FF_Sets')
            m_table.to_excel(wr, sheet_name='M_Table')
            if s_state['trace']: pd.DataFrame(s_state['trace']).to_excel(wr, sheet_name='Trace')
        st.download_button("📥 تحميل Excel", buf.getvalue(), "Compiler_Analysis.xlsx")

import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import io, os
from fpdf import FPDF

# 1. إعدادات الصفحة والهوية البصرية
st.set_page_config(page_title="LL(1) Compiler Studio - University of Misan", layout="wide")

# CSS لتحسين الخطوط وتنسيق الهيدر والجداول
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Tajawal', sans-serif; direction: RTL; text-align: right; }
    .header-text { line-height: 1.2; color: #1E3A8A; }
    .main-title { font-size: 24px; font-weight: bold; margin-bottom: 0; }
    .sub-title { font-size: 18px; color: #4B5563; }
    .stTable td { white-space: pre !important; font-family: 'monospace' !important; text-align: center; }
    .status-box { padding: 15px; border-radius: 10px; text-align: center; font-weight: bold; margin: 10px 0; border: 2px solid; }
    .accepted { background-color: #D1FAE5; color: #065F46; border-color: #34D399; }
    .rejected { background-color: #FEE2E2; color: #991B1B; border-color: #F87171; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f8fafc; color: #1e3a8a;
              text-align: center; padding: 8px; font-weight: bold; border-top: 3px solid #1e3a8a; z-index: 100; }
    </style>
    <div class="footer">أ.م. حسنين رحيم كريم - مختبر المترجمات الذكي 2026 ©</div>
    """, unsafe_allow_html=True)

# 2. الهيدر (الشعار والنصوص)
h_col1, h_col2 = st.columns([1, 3])
with h_col1:
    # عرض الشعار في أقصى اليسار
    st.image("شعار الكلية الجديد.jpg", width=120)
with h_col2:
    # النصوص في أقصى اليمين بتنسيق أكاديمي
    st.markdown("""
        <div style="text-align: right;" class="header-text">
            <div class="main-title">جامعة ميسان</div>
            <div class="sub-title">كلية التربية</div>
            <div class="sub-title">قسم علوم الحاسبات</div>
        </div>
        """, unsafe_allow_html=True)

st.divider()

# 3. محرك المعالجة المتقدم (Recursion & Factoring)
def parse_grammar(text):
    g = OrderedDict()
    for line in text.strip().split('\n'):
        if '->' in line:
            lhs, rhs = line.split('->')
            g[lhs.strip()] = [p.strip().split() for p in rhs.split('|')]
    return g

def fix_left_recursion(g):
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

def fix_left_factoring(g):
    res_g = OrderedDict()
    for nt, prods in g.items():
        curr = prods.copy()
        while True:
            prefixes = {}
            for p in curr:
                if not p: continue
                first_sym = p[0]
                prefixes[first_sym] = prefixes.get(first_sym, 0) + 1
            
            common = [s for s, count in prefixes.items() if count > 1 and s != 'ε']
            if not common: break
            
            best_s = common[0]
            new_nt = f"{nt}f" # حرف f للدلالة على Factoring
            while new_nt in g or new_nt in res_g: new_nt += "f"
            
            new_curr = []
            factored_prods = []
            for p in curr:
                if p and p[0] == best_s:
                    rem = p[1:] if p[1:] else ['ε']
                    factored_prods.append(rem)
                else: new_curr.append(p)
            
            new_curr.append([best_s, new_nt])
            res_g[new_nt] = factored_prods
            curr = new_curr
        res_g[nt] = curr
    return res_g

def calculate_sets(g):
    first = {nt: set() for nt in g}
    def get_f(seq):
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
            for p in prods: first[nt].update(get_f(p))
    follow = {nt: set() for nt in g}
    if g: follow[list(g.keys())[0]].add('$')
    for _ in range(10):
        for nt, prods in g.items():
            for p in prods:
                for i, B in enumerate(p):
                    if B in g:
                        beta = p[i+1:]
                        if beta:
                            fb = get_f(beta); follow[B].update(fb - {'ε'})
                            if 'ε' in fb: follow[B].update(follow[nt])
                        else: follow[B].update(follow[nt])
    return first, follow

# 4. إدارة الجلسة والمدخلات
if 'st_trace' not in st.session_state:
    st.session_state.update({'st_trace': [], 'st_stack': [], 'st_done': False, 'st_dot': Digraph(), 'st_id': 0, 'st_status': ""})

with st.sidebar:
    st.header("⚙️ لوحة التحكم")
    grammar_input = st.text_area("أدخل القواعد الأكاديمية:", "S -> i E t S | i E t S e S | a\nE -> b", height=150)
    input_str = st.text_input("الجملة المراد فحصها:", "i b t a e a $")
    if st.button("🗑 إعادة ضبط النظام"):
        st.session_state.clear(); st.rerun()

# 5. التنفيذ والعرض
orig_g = parse_grammar(grammar_input)
if orig_g:
    # المعالجة المتسلسلة
    processed_g = fix_left_factoring(fix_left_recursion(orig_g))
    f_set, l_set = calculate_sets(processed_g)
    
    # جدول التنبؤ
    terms = sorted(list({s for ps in processed_g.values() for p in ps for s in p if s not in processed_g and s != 'ε'})) + ['$']
    m_table = pd.DataFrame("", index=processed_g.keys(), columns=terms)
    for nt, prods in processed_g.items():
        for p in prods:
            pf = set()
            for s in p:
                sf = f_set[s] if s in processed_g else {s}; pf.update(sf - {'ε'})
                if 'ε' not in sf: break
            else: pf.add('ε')
            for a in pf:
                if a != 'ε': m_table.at[nt, a] = f"{nt}->{' '.join(p)}"
            if 'ε' in pf:
                for b in l_set[nt]: m_table.at[nt, b] = f"{nt}->{' '.join(p)}"

    # عرض القواعد
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📋 القواعد الأصلية")
        for k, v in orig_g.items(): st.code(f"{k} → {' | '.join([' '.join(p) for p in v])}")
    with c2:
        st.subheader("🛠 القواعد بعد التصحيح")
        for k, v in processed_g.items(): st.code(f"{k} → {' | '.join([' '.join(p) for p in v])}")

    st.subheader("🔍 مجموعات First & Follow")
    ff_df = pd.DataFrame({"First": [str(sorted(list(f_set[n]))) for n in processed_g], 
                          "Follow": [str(sorted(list(l_set[n]))) for n in processed_g]}, index=processed_g.keys())
    st.table(ff_df)

    st.subheader("📊 جدول التنبؤ (Parsing Table)")
    st.dataframe(m_table, use_container_width=True)

    # 6. المحاكاة (Trace)
    st.divider()
    st.subheader("⏳ تتبع الجملة ورسم الشجرة")
    s = st.session_state
    if not s.st_stack:
        s.st_stack = [('$', '0'), (list(processed_g.keys())[0], '0')]
        s.st_dot = Digraph(); s.st_dot.node('0', list(processed_g.keys())[0], style='filled', fillcolor='lightblue')

    def run_step():
        if s.st_done or not s.st_stack: return
        tokens = input_str.split(); matches = sum(1 for x in s.st_trace if "Match" in x['Action'])
        look = tokens[matches] if matches < len(tokens) else '$'
        top, pid = s.st_stack.pop()
        rec = {"Stack": " ".join([v for v, i in s.st_stack] + [top]), "Input": " ".join(tokens[matches:]), "Action": ""}
        if top == look:
            rec["Action"] = f"Match {look}"
            if top == '$': s.st_done, s.st_status = True, "Accepted"
        elif top in processed_g:
            rule = m_table.at[top, look]
            if rule:
                rec["Action"] = f"Apply {rule}"; rhs = rule.split('->')[1].split()
                if rhs == ['ε']:
                    s.st_id += 1; eid = f"e{s.st_id}"; s.st_dot.node(eid, "ε", shape='plaintext'); s.st_dot.edge(pid, eid)
                else:
                    tmp = []
                    for sym in rhs:
                        s.st_id += 1; nid = str(s.st_id); s.st_dot.node(nid, sym, style='filled', fillcolor='lightgreen')
                        s.st_dot.edge(pid, nid); tmp.append((sym, nid))
                    for item in reversed(tmp): s.st_stack.append(item)
            else: s.st_done, s.st_status = True, "Rejected"
        else: s.st_done, s.st_status = True, "Rejected"
        s.st_trace.append(rec)

    b1, b2 = st.columns(2)
    if b1.button("⏭ خطوة تالية"): run_step(); st.rerun()
    if b2.button("▶ تشغيل كامل"):
        while not s.st_done: run_step()
        st.rerun()

    if s.st_trace:
        st.table(pd.DataFrame(s.st_trace))
        st.graphviz_chart(s.st_dot)
        if s.st_done:
            st.markdown(f'<div class="status-box {"accepted" if "Acc" in s.st_status else "rejected"}">{s.st_status}</div>', unsafe_allow_html=True)

    # 7. التصدير
    st.divider()
    st.subheader("📥 تصدير التقارير النهائية")
    ex1, ex2 = st.columns(2)
    with ex1:
        if st.button("📄 تصدير PDF"):
            pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, "University of Misan - Compiler Report", 0, 1, 'C')
            st.download_button("📥 تحميل PDF", bytes(pdf.output()), "Report.pdf")
    with ex2:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
            ff_df.to_excel(wr, sheet_name='Sets'); m_table.to_excel(wr, sheet_name='Table')
            if s.st_trace: pd.DataFrame(s.st_trace).to_excel(wr, sheet_name='Trace')
        st.download_button("📥 تحميل Excel", buf.getvalue(), "Compiler_Data.xlsx")

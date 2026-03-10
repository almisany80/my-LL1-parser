import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import io, os
from fpdf import FPDF

# 1. الإعدادات البصرية والهوية الأكاديمية
st.set_page_config(page_title="LL(1) Advanced Studio - University of Misan", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Tajawal', sans-serif; direction: RTL; text-align: right; }
    .header-box { background-color: #f8fafc; padding: 20px; border-radius: 15px; border-right: 10px solid #1E3A8A; margin-bottom: 20px; }
    .main-title { font-size: 28px; font-weight: bold; color: #1E3A8A; margin: 0; }
    .sub-title { font-size: 20px; color: #4B5563; margin: 0; }
    .stTable td { white-space: pre !important; font-family: 'monospace' !important; text-align: center; font-size: 14px; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #ffffff; color: #1e3a8a;
              text-align: center; padding: 10px; font-weight: bold; border-top: 2px solid #1e3a8a; z-index: 1000; }
    .status-msg { padding: 15px; border-radius: 10px; text-align: center; font-weight: bold; font-size: 18px; margin-top: 20px; }
    .success { background-color: #d1fae5; color: #065f46; border: 2px solid #34d399; }
    .error { background-color: #fee2e2; color: #991b1b; border: 2px solid #f87171; }
    </style>
    <div class="footer">أ.م. حسنين رحيم كريم - مختبر تصميم المترجمات ذكاء اصطناعي 2026 ©</div>
    """, unsafe_allow_html=True)

# 2. الهيدر (الشعار والنصوص)
h_left, h_right = st.columns([1, 4])
with h_left:
    logo_path = "logo.jpg" # تأكد من إعادة تسمية الشعار لـ logo.jpg
    if os.path.exists(logo_path):
        st.image(logo_path, width=140)
    else:
        st.info("📷 شعار الكلية")

with h_right:
    st.markdown("""
        <div class="header-box">
            <div class="main-title">جامعة ميسان</div>
            <div class="sub-title">كلية التربية - قسم علوم الحاسبات</div>
            <div style="color: #6B7280; font-weight: bold;">مختبر تصميم المترجمات المتقدم</div>
        </div>
        """, unsafe_allow_html=True)

# 3. محرك المعالجة المطور (Left Factoring & Recursion)
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
            nt_p = f"{nt}1" # استخدام ترقيم بدلاً من f لتجنب مشاكل الرموز
            new_g[nt] = [p + [nt_p] for p in (non_rec if non_rec else [['ε']])]
            new_g[nt_p] = [p + [nt_p] for p in rec] + [['ε']]
        else: new_g[nt] = prods
    return new_g

def fix_left_factoring(g):
    res_g = OrderedDict()
    for nt, prods in g.items():
        curr_prods = prods.copy()
        while True:
            # البحث عن أطول بادئة مشتركة
            prefixes = {}
            for p in curr_prods:
                if p and p != ['ε']:
                    s = p[0]
                    prefixes[s] = prefixes.get(s, 0) + 1
            
            common = [s for s, count in prefixes.items() if count > 1]
            if not common: break
            
            best_prefix = common[0]
            new_nt = f"{nt}_sub" # تسمية واضحة للرموز الفرعية
            while new_nt in g or new_nt in res_g: new_nt += "s"
            
            factored = []
            remaining = []
            for p in curr_prods:
                if p and p[0] == best_prefix:
                    factored.append(p[1:] if p[1:] else ['ε'])
                else:
                    remaining.append(p)
            
            remaining.append([best_prefix, new_nt])
            res_g[new_nt] = factored
            curr_prods = remaining
        res_g[nt] = curr_prods
    return res_g

def compute_sets(g):
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
        for nt, ps in g.items():
            for p in ps: first[nt].update(get_f(p))
    
    follow = {nt: set() for nt in g}
    if g: follow[list(g.keys())[0]].add('$')
    for _ in range(10):
        for nt, ps in g.items():
            for p in ps:
                for i, B in enumerate(p):
                    if B in g:
                        beta = p[i+1:]
                        if beta:
                            fb = get_f(beta); follow[B].update(fb - {'ε'})
                            if 'ε' in fb: follow[B].update(follow[nt])
                        else: follow[B].update(follow[nt])
    return first, follow

# 4. إدارة الحالة (Session State)
if 'st' not in st.session_state:
    st.session_state.st = {'trace': [], 'stack': [], 'done': False, 'dot': Digraph(), 'id': 0, 'status': ""}

# 5. الواجهة الجانبية (Sidebar)
with st.sidebar:
    st.header("⚙️ لوحة التحكم")
    # القواعد التي تسببت في المشكلة
    default_g = "S -> i E t S | i E t S e S | a\nE -> b"
    grammar_txt = st.text_area("أدخل القواعد الأكاديمية:", default_g, height=150)
    test_input = st.text_input("الجملة المراد فحصها:", "i b t a e a $")
    if st.button("🗑 مسح الذاكرة وإعادة الضبط"):
        st.session_state.st = {'trace': [], 'stack': [], 'done': False, 'dot': Digraph(), 'id': 0, 'status': ""}
        st.rerun()

# 6. المعالجة والعرض
orig_g = parse_grammar(grammar_txt)
if orig_g:
    # تطبيق التحسينات بالترتيب
    processed_g = fix_left_factoring(fix_left_recursion(orig_g))
    f_set, l_set = compute_sets(processed_g)
    
    # بناء جدول M
    terms = sorted(list({s for ps in processed_g.values() for p in ps for s in p if s not in processed_g and s != 'ε'})) + ['$']
    m_table = pd.DataFrame("", index=processed_g.keys(), columns=terms)
    for nt, ps in processed_g.items():
        for p in ps:
            pf = set()
            for s in p:
                sf = f_set[s] if s in processed_g else {s}; pf.update(sf - {'ε'})
                if 'ε' not in sf: break
            else: pf.add('ε')
            for a in pf:
                if a != 'ε': m_table.at[nt, a] = f"{nt}->{' '.join(p)}"
            if 'ε' in pf:
                for b in l_set[nt]: m_table.at[nt, b] = f"{nt}->{' '.join(p)}"

    # عرض النتائج
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📋 القواعد الأصلية")
        for k, v in orig_g.items(): st.code(f"{k} → {' | '.join([' '.join(p) for p in v])}")
    with c2:
        st.subheader("🛠 القواعد بعد التصحيح (Factored)")
        for k, v in processed_g.items(): st.code(f"{k} → {' | '.join([' '.join(p) for p in v])}")

    st.subheader("🔍 مجموعات First & Follow")
    ff_df = pd.DataFrame({"First": [str(sorted(list(f_set[n]))) for n in processed_g], 
                          "Follow": [str(sorted(list(l_set[n]))) for n in processed_g]}, index=processed_g.keys())
    st.table(ff_df)

    st.subheader("📊 جدول التنبؤ (Parsing Table)")
    st.dataframe(m_table, use_container_width=True)

    # 7. التتبع وشجرة الاشتقاق
    st.divider()
    st.subheader("⏳ تتبع الجملة وشجرة الاشتقاق")
    s = st.session_state.st
    if not s['stack']:
        s['stack'] = [('$', '0'), (list(processed_g.keys())[0], '0')]
        s['dot'] = Digraph(); s['dot'].node('0', list(processed_g.keys())[0], style='filled', fillcolor='#E0F2FE')

    def run_step():
        if s['done'] or not s['stack']: return
        tokens = test_input.split(); matched = sum(1 for x in s['trace'] if "Match" in x['Action'])
        lookahead = tokens[matched] if matched < len(tokens) else '$'
        top, pid = s['stack'].pop()
        row = {"Stack": " ".join([v for v, i in s['stack']] + [top]), "Input": " ".join(tokens[matched:]), "Action": ""}
        
        if top == lookahead:
            row["Action"] = f"Match {lookahead}"
            if top == '$': s['done'], s['status'] = True, "Accepted ✅"
        elif top in processed_g:
            rule = m_table.at[top, lookahead]
            if rule:
                row["Action"] = f"Apply {rule}"; rhs = rule.split('->')[1].split()
                if rhs == ['ε']:
                    s['id'] += 1; eid = f"e{s['id']}"; s['dot'].node(eid, "ε", shape='plaintext'); s['dot'].edge(pid, eid)
                else:
                    nodes = []
                    for sym in rhs:
                        s['id'] += 1; nid = str(s['id'])
                        s['dot'].node(nid, sym, style='filled', fillcolor='#DCFCE7'); s['dot'].edge(pid, nid)
                        nodes.append((sym, nid))
                    for item in reversed(nodes): s['stack'].append(item)
            else: s['done'], s['status'] = True, "Rejected ❌ (No Rule)"
        else: s['done'], s['status'] = True, "Rejected ❌ (Mismatch)"
        s['trace'].append(row)

    b1, b2 = st.columns(2)
    if b1.button("⏭ خطوة تالية (Step)"): run_step(); st.rerun()
    if b2.button("▶ تشغيل كامل (Run All)"):
        while not s['done']: run_step()
        st.rerun()

    if s['trace']:
        st.table(pd.DataFrame(s['trace']))
        st.graphviz_chart(s['dot'])
        if s['done']:
            cls = "success" if "Accepted" in s['status'] else "error"
            st.markdown(f'<div class="status-msg {cls}">{s["status"]}</div>', unsafe_allow_html=True)

    # 8. التصدير
    st.divider()
    st.subheader("📥 تصدير التقارير النهائية")
    ex1, ex2 = st.columns(2)
    with ex1:
        if st.button("📄 تحميل PDF"):
            pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 12)
            pdf.cell(200, 10, txt="Compiler Lab Report - University of Misan", ln=1, align='C')
            st.download_button("📥 اضغط للتحميل", bytes(pdf.output()), "Report.pdf")
    with ex2:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
            ff_df.to_excel(wr, sheet_name='Sets'); m_table.to_excel(wr, sheet_name='ParsingTable')
            if s['trace']: pd.DataFrame(s['trace']).to_excel(wr, sheet_name='Trace')
        st.download_button("📥 تحميل ملف Excel", buf.getvalue(), "Compiler_Data.xlsx")

import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import io
import os
from fpdf import FPDF

# 1. الإعدادات البصرية والهوية الأكاديمية لجامعة ميسان
st.set_page_config(page_title="LL(1) Compiler Studio - University of Misan", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Tajawal', sans-serif; direction: RTL; text-align: right; }
    .header-box { background-color: #ffffff; padding: 20px; border-radius: 10px; border-bottom: 4px solid #1E3A8A; margin-bottom: 25px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .main-title { font-size: 26px; font-weight: bold; color: #1E3A8A; margin-bottom: 5px; }
    .sub-title { font-size: 19px; color: #4B5563; }
    .stTable td { white-space: pre !important; font-family: 'monospace' !important; text-align: center; font-size: 15px; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f8fafc; color: #1e3a8a;
              text-align: center; padding: 10px; font-weight: bold; border-top: 3px solid #1e3a8a; z-index: 1000; }
    .status-box { padding: 15px; border-radius: 8px; text-align: center; font-weight: bold; font-size: 18px; margin: 15px 0; }
    .accepted { background-color: #d1fae5; color: #065f46; border: 1px solid #34d399; }
    .rejected { background-color: #fee2e2; color: #991b1b; border: 1px solid #f87171; }
    </style>
    <div class="footer">أ.م. حسنين رحيم كريم - مختبر تصميم المترجمات 2026 ©</div>
    """, unsafe_allow_html=True)

# 2. الهيدر الأكاديمي
h_col1, h_col2 = st.columns([1, 4])
with h_col1:
    logo_path = "logo.jpg"
    if os.path.exists(logo_path):
        st.image(logo_path, width=130)
    else:
        st.warning("⚠️ يرجى التأكد من تسمية الشعار بـ logo.jpg")

with h_col2:
    st.markdown("""
        <div class="header-box">
            <div class="main-title">جامعة ميسان</div>
            <div class="sub-title">كلية التربية - قسم علوم الحاسبات</div>
            <div class="sub-title" style="color: #10B981; font-weight: bold; margin-top: 5px;">مختبر المترجمات الذكي - LL(1) Parser</div>
        </div>
        """, unsafe_allow_html=True)

# 3. فئة تقارير PDF
class AcademicPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.add_page()
        self.set_font("Arial", 'B', 14)
        self.cell(0, 10, 'University of Misan - Compiler Design Report', 0, 1, 'C')
        self.ln(5)

    def write_table(self, title, df):
        self.set_font("Arial", 'B', 12)
        self.cell(0, 10, title, 1, 1, 'C')
        self.set_font("Arial", '', 10)
        col_width = self.epw / len(df.columns)
        for col in df.columns: self.cell(col_width, 8, str(col), 1, 0, 'C')
        self.ln()
        for row in df.values:
            for item in row: self.cell(col_width, 8, str(item), 1, 0, 'C')
            self.ln()
        self.ln(5)

# 4. محرك المعالجة المتقدم (الخوارزميات المصححة)
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
    """خوارزمية أطول سلسلة مشتركة لحل مشكلة التداخل المتقدمة (Dangling Else)"""
    final_g = OrderedDict()
    nts_to_process = list(g.keys())
    
    for nt in nts_to_process: final_g[nt] = g[nt].copy()
        
    while nts_to_process:
        nt = nts_to_process.pop(0)
        curr_prods = final_g[nt]
        
        max_len = 0
        longest_prefix = []
        # البحث عن أطول سلسلة مشتركة بين أي قاعدتين
        for i in range(len(curr_prods)):
            for j in range(i + 1, len(curr_prods)):
                p1, p2 = curr_prods[i], curr_prods[j]
                if not p1 or not p2 or p1 == ['ε'] or p2 == ['ε']: continue
                k = 0
                while k < len(p1) and k < len(p2) and p1[k] == p2[k]: k += 1
                if k > max_len:
                    max_len = k
                    longest_prefix = p1[:k]
        
        if max_len > 0:
            factored = []
            remaining = []
            for p in curr_prods:
                if p[:max_len] == longest_prefix:
                    rem = p[max_len:]
                    factored.append(rem if rem else ['ε'])
                else: remaining.append(p)
            
            # استخدام شرطة رئيسية (') لإنشاء رمز جديد نقي برمجياً
            new_nt = f"{nt}'"
            while new_nt in final_g: new_nt += "'"
            
            remaining.append(longest_prefix + [new_nt])
            final_g[nt] = remaining
            final_g[new_nt] = factored
            
            nts_to_process.insert(0, nt)
            nts_to_process.insert(1, new_nt)
            
    return final_g

def compute_sets(grammar):
    first = {nt: set() for nt in grammar}
    def get_f(seq):
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
            old = len(first[nt])
            for p in prods: first[nt].update(get_f(p))
            if len(first[nt]) > old: changed = True
        if not changed: break

    follow = {nt: set() for nt in grammar}
    if grammar: follow[list(grammar.keys())[0]].add('$')
    while True:
        changed = False
        for nt, prods in grammar.items():
            for p in prods:
                for i, B in enumerate(p):
                    if B in grammar:
                        old = len(follow[B])
                        beta = p[i+1:]
                        if beta:
                            fb = get_f(beta)
                            follow[B].update(fb - {'ε'})
                            if 'ε' in fb: follow[B].update(follow[nt])
                        else: follow[B].update(follow[nt])
                        if len(follow[B]) > old: changed = True
        if not changed: break
    return first, follow

# 5. إدارة الذاكرة (Session State)
if 'st' not in st.session_state:
    st.session_state.st = {'trace': [], 'stack': [], 'done': False, 'dot': Digraph(), 'id': 0, 'status': ""}

# 6. الواجهة الجانبية (Sidebar)
with st.sidebar:
    st.header("⚙️ لوحة الإعدادات")
    grammar_txt = st.text_area("أدخل القواعد:", "S -> i E t S | i E t S e S | a\nE -> b", height=150)
    test_input = st.text_input("الجملة المختبرة:", "i b t a e a $")
    if st.button("🔄 إعادة ضبط النظام"):
        st.session_state.st = {'trace': [], 'stack': [], 'done': False, 'dot': Digraph(), 'id': 0, 'status': ""}
        st.rerun()

# 7. معالجة القواعد وبناء الجداول
orig_g = parse_grammar(grammar_txt)
if orig_g:
    # تطبيق المعالجة المتقدمة
    processed_g = fix_left_factoring(fix_left_recursion(orig_g))
    f_set, l_set = compute_sets(processed_g)
    
    # بناء جدول التنبؤ M-Table
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

    # العرض الأكاديمي
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📋 القواعد الأصلية")
        for k, v in orig_g.items(): st.code(f"{k} → {' | '.join([' '.join(p) for p in v])}")
    with c2:
        st.subheader("🛠 القواعد بعد المعالجة (Factored & Non-Recursive)")
        for k, v in processed_g.items(): st.code(f"{k} → {' | '.join([' '.join(p) for p in v])}")

    st.subheader("🔍 مجموعات First & Follow")
    ff_df = pd.DataFrame({"First": [str(sorted(list(f_set[n]))) for n in processed_g], 
                          "Follow": [str(sorted(list(l_set[n]))) for n in processed_g]}, index=processed_g.keys())
    st.table(ff_df)

    st.subheader("📊 جدول التنبؤ (Parsing Table)")
    st.dataframe(m_table, use_container_width=True)

    # 8. التتبع وشجرة الاشتقاق (Parsing Trace)
    st.divider()
    st.subheader("⏳ التتبع الحي للجملة")
    s = st.session_state.st
    if not s['stack']:
        s['stack'] = [('$', '0'), (list(processed_g.keys())[0], '0')]
        s['dot'] = Digraph(); s['dot'].node('0', list(processed_g.keys())[0], style='filled', fillcolor='#DBEAFE')

    def run_step():
        if s['done'] or not s['stack']: return
        tokens = test_input.split(); matched = sum(1 for x in s['trace'] if "Match" in x['Action'])
        lookahead = tokens[matched] if matched < len(tokens) else '$'
        top, pid = s['stack'].pop()
        row = {"Stack": " ".join([v for v, i in s['stack']] + [top]), "Input": " ".join(tokens[matched:]), "Action": ""}
        
        if top == lookahead:
            row["Action"] = f"Match {lookahead}"
            if top == '$': s['done'], s['status'] = True, "✅ الجملة مقبولة (Accepted)"
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
                        s['dot'].node(nid, sym, style='filled', fillcolor='#D1FAE5' if sym not in processed_g else '#F3F4F6')
                        s['dot'].edge(pid, nid)
                        nodes.append((sym, nid))
                    for item in reversed(nodes): s['stack'].append(item)
            else: s['done'], s['status'] = True, "❌ مرفوضة (لا توجد قاعدة - Blank Cell)"
        else: s['done'], s['status'] = True, "❌ مرفوضة (عدم تطابق - Mismatch)"
        s['trace'].append(row)

    b1, b2 = st.columns(2)
    if b1.button("⏭ خطوة تالية (Step)"): run_step(); st.rerun()
    if b2.button("▶ تشغيل كامل (Run All)"):
        while not s['done']: run_step()
        st.rerun()

    if s['trace']:
        st.table(pd.DataFrame(s['trace']))
        st.subheader("🌲 شجرة الاشتقاق (Parse Tree)")
        st.graphviz_chart(s['dot'])
        if s['done']:
            cls = "accepted" if "✅" in s['status'] else "rejected"
            st.markdown(f'<div class="status-box {cls}">{s["status"]}</div>', unsafe_allow_html=True)

    # 9. التصدير (PDF & Excel)
    st.divider()
    st.subheader("📥 تصدير التقارير النهائية")
    ex1, ex2 = st.columns(2)
    with ex1:
        if st.button("📄 تصدير تقرير PDF"):
            try:
                pdf = AcademicPDF()
                pdf.write_table("First & Follow Sets", ff_df.reset_index())
                pdf.write_table("Parsing Table", m_table.reset_index())
                if s['trace']: pdf.write_table("Parsing Trace", pd.DataFrame(s['trace']))
                st.download_button("📥 تحميل PDF", bytes(pdf.output()), "LL1_Report.pdf", "application/pdf")
            except Exception as e:
                st.error(f"خطأ أثناء توليد الـ PDF: {e}")
    with ex2:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
            ff_df.to_excel(wr, sheet_name='Sets'); m_table.to_excel(wr, sheet_name='Table')
            if s['trace']: pd.DataFrame(s['trace']).to_excel(wr, sheet_name='Trace')
        st.download_button("📥 تحميل Excel", buf.getvalue(), "Compiler_Data.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

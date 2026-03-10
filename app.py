import streamlit as st
import pandas as pd
import re
from collections import OrderedDict
from graphviz import Digraph
import io
import os
from fpdf import FPDF

# 1. إعدادات الواجهة (RTL بالكامل)
st.set_page_config(page_title="LL(1) Academic Studio V10", layout="wide")
st.markdown("""
    <style>
    .main { direction: RTL; text-align: right; }
    div.stButton > button { width: 100%; border-radius: 5px; }
    .stTable td { white-space: pre !important; font-family: 'monospace'; }
    .status-box { padding: 15px; border-radius: 8px; text-align: center; font-weight: bold; }
    .conflict-alert { background-color: #fff3cd; color: #856404; padding: 15px; border-radius: 10px; border-right: 6px solid #ffc107; margin: 10px 0; }
    /* محاذاة الصندوق الجانبي */
    [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    </style>
    """, unsafe_allow_html=True)

# 2. فئة PDF المتقدمة (حل مشكلة الرموز والباينري)
class ScholarPDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 12)
        self.cell(0, 10, 'LL(1) Academic Analysis Report - University of Misan', 0, 1, 'C')
        self.ln(5)

    def safe_encode(self, text):
        # تحويل الرموز غير المدعومة في هيلفيتيكا إلى نصوص مفهومة
        return str(text).replace('ε', 'epsilon').replace('→', '->').replace('∩', 'intersect')

    def add_table(self, title, df):
        self.set_font('Helvetica', 'B', 10)
        self.cell(0, 8, self.safe_encode(title), 1, 1, 'L')
        self.set_font('Helvetica', '', 9)
        col_width = self.epw / len(df.columns)
        for col in df.columns: self.cell(col_width, 7, self.safe_encode(col), 1, 0, 'C')
        self.ln()
        for row in df.values:
            for item in row: self.cell(col_width, 7, self.safe_encode(item), 1, 0, 'C')
            self.ln()
        self.ln(5)

# 3. محرك القواعد المتطور (Logic Engine)
def get_seq_first(seq, first_set, grammar):
    res = set()
    if not seq or seq == ['ε']: return {'ε'}
    for s in seq:
        sf = first_set[s] if s in grammar else {s}
        res.update(sf - {'ε'})
        if 'ε' not in sf: break
    else: res.add('ε')
    return res

def auto_fix_conflicts(grammar):
    # تطبيق الـ Left Factoring المتقدم لحل تصادمات FIRST/FIRST
    new_g = OrderedDict()
    for nt, prods in grammar.items():
        if len(prods) <= 1:
            new_g[nt] = prods; continue
        
        # البحث عن بادئات مشتركة
        first_map = {}
        for p in prods:
            lead = p[0] if p else 'ε'
            if lead not in first_map: first_map[lead] = []
            first_map[lead].append(p)
        
        needs_factoring = any(len(group) > 1 for lead, group in first_map.items() if lead != 'ε')
        
        if needs_factoring:
            new_g[nt] = []
            for lead, group in first_map.items():
                if len(group) > 1 and lead != 'ε':
                    new_nt = f"{nt}''"
                    new_g[nt].append([lead, new_nt])
                    new_g[new_nt] = [p[1:] if len(p) > 1 else ['ε'] for p in group]
                else:
                    new_g[nt].extend(group)
        else:
            new_g[nt] = prods
    return new_g

def calculate_ff(grammar):
    first = {nt: set() for nt in grammar}
    while True:
        changed = False
        for nt, prods in grammar.items():
            old = len(first[nt])
            for p in prods: first[nt].update(get_seq_first(p, first, grammar))
            if len(first[nt]) > old: changed = True
        if not changed: break
    
    follow = {nt: set() for nt in grammar}; follow[list(grammar.keys())[0]].add('$')
    while True:
        changed = False
        for nt, prods in grammar.items():
            for p in prods:
                for i, B in enumerate(p):
                    if B in grammar:
                        old = len(follow[B])
                        beta = p[i+1:]
                        fb = get_seq_first(beta, first, grammar)
                        follow[B].update(fb - {'ε'})
                        if 'ε' in fb: follow[B].update(follow[nt])
                        if len(follow[B]) > old: changed = True
        if not changed: break
    return first, follow

# 4. إدارة الجلسة والواجهة
if 'stack' not in st.session_state:
    st.session_state.update({'trace': [], 'stack': [], 'done': False, 'status': "", 'dot': Digraph(), 'n_id': 0})

with st.sidebar:
    st.header("⚙️ لوحة التحكم")
    raw_in = st.text_area("أدخل القواعد:", value="E -> T E'\nE' -> + T E' | ε\nT -> F T'\nT' -> * F T' | ε\nF -> ( E ) | id", height=180)
    sentence = st.text_input("الجملة المختبرة:", "id + id * id $")
    if st.button("🗑 مسح الذاكرة"): st.session_state.clear(); st.rerun()

# المعالجة الأساسية
original_g = OrderedDict()
for line in raw_in.strip().split('\n'):
    if '->' in line:
        l, r = line.split('->')
        original_g[l.strip()] = [p.strip().split() for p in r.split('|')]

if original_g:
    st.title("🎓 مختبر المحلل القواعدي (LL1) - جامعة ميسان")
    
    # محاكاة قرار المستخدم للحل الذكي
    is_ll1 = True # افتراض مبدئي
    current_g = original_g
    
    # كشف التصادمات (FIRST/FIRST & FIRST/FOLLOW)
    f_sets, fol_sets = calculate_ff(current_g)
    conflicts_found = False
    for nt, prods in current_g.items():
        if len(prods) > 1:
            all_firsts = [get_seq_first(p, f_sets, current_g) for p in prods]
            for i in range(len(all_firsts)):
                for j in range(i+1, len(all_firsts)):
                    if all_firsts[i] & all_firsts[j]: conflicts_found = True

    if conflicts_found:
        st.markdown(f'<div class="conflict-alert">⚠️ تم اكتشاف تصادم في القواعد (ليست LL1). هل ترغب في تفعيل الحل الأوتوماتيكي؟</div>', unsafe_allow_html=True)
        if st.checkbox("نعم، قم بتفعيل الحل الأوتوماتيكي للتصادمات"):
            current_g = auto_fix_conflicts(current_g)
            f_sets, fol_sets = calculate_ff(current_g)
            st.info("✅ تم تطبيق خوارزمية فك التصادم بنجاح.")

    # عرض النتائج
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📋 القواعد الأصلية")
        for k, v in original_g.items(): st.code(f"{k} → {' | '.join([' '.join(p) for p in v])}")
    with col2:
        st.subheader("🛠 القواعد بعد المعالجة")
        for k, v in current_g.items(): st.code(f"{k} → {' | '.join([' '.join(p) for p in v])}")

    st.divider()
    st.subheader("🔍 مجموعات First & Follow")
    ff_df = pd.DataFrame({"First": [str(f_sets[n]) for n in current_g], "Follow": [str(fol_sets[n]) for n in current_g]}, index=current_g.keys())
    st.table(ff_df)

    # بناء الجدول
    terms = sorted(list({s for ps in current_g.values() for p in ps for s in p if s not in current_g and s != 'ε'})) + ['$']
    m_table = pd.DataFrame("", index=current_g.keys(), columns=terms)
    for nt, prods in current_g.items():
        for p in prods:
            pf = get_seq_first(p, f_sets, current_g)
            for a in pf:
                if a != 'ε': m_table.at[nt, a] = f"{nt}->{' '.join(p)}"
            if 'ε' in pf:
                for b in fol_sets[nt]: m_table.at[nt, b] = f"{nt}->{' '.join(p)}"

    st.subheader("📊 جدول التنبؤ (Parsing Table)")
    st.dataframe(m_table.style.highlight_null(color='red'), use_container_width=True)

    # تتبع الجملة
    st.divider()
    st.subheader("⏳ تتبع الجملة (Parsing Trace)")
    
    def run_step():
        s = st.session_state
        if not s.stack:
            s.stack = [('$', '0'), (list(current_g.keys())[0], '0')]
            s.dot = Digraph(); s.dot.node('0', list(current_g.keys())[0], style='filled', fillcolor='lightblue')
        
        tokens = sentence.split()
        matched = sum(1 for x in s.trace if "Match" in x['Action'])
        lookahead = tokens[matched] if matched < len(tokens) else '$'
        
        top, pid = s.stack.pop()
        step = {"Stack": " ".join([v for v, i in s.stack] + [top]), "Input": " ".join(tokens[matched:]), "Action": ""}
        
        if top == lookahead:
            step["Action"] = f"Match {lookahead}"
            if top == '$': s.done, s.status = "Accepted"
        elif top in current_g:
            rule = m_table.at[top, lookahead]
            if rule:
                step["Action"] = f"Apply {rule}"
                rhs = rule.split('->')[1].split()
                if rhs != ['ε']:
                    for sym in reversed(rhs):
                        s.n_id += 1; nid = str(s.n_id)
                        s.dot.node(nid, sym, style='filled', fillcolor='lightgreen')
                        s.dot.edge(pid, nid)
                        s.stack.append((sym, nid))
                else:
                    s.n_id += 1; nid = f"e{s.n_id}"
                    s.dot.node(nid, "ε", shape='plaintext'); s.dot.edge(pid, nid)
            else: step["Action"] = "❌ Error"; s.done = True; s.status = "Rejected"
        else: step["Action"] = "❌ Error"; s.done = True; s.status = "Rejected"
        s.trace.append(step)

    b1, b2 = st.columns(2)
    if b1.button("⏭ خطوة تالية"): run_step()
    if b2.button("▶ تشغيل كامل"):
        while not st.session_state.done and len(st.session_state.trace) < 50: run_step()

    if st.session_state.trace:
        st.table(pd.DataFrame(st.session_state.trace))
        st.graphviz_chart(st.session_state.dot)

    # التصدير
    st.divider()
    st.subheader("📥 تصدير التقارير النهائية")
    ex1, ex2 = st.columns(2)
    with ex1:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            ff_df.to_excel(writer, sheet_name='FF_Sets')
            m_table.to_excel(writer, sheet_name='M_Table')
        st.download_button("📊 تحميل ملف Excel", buf.getvalue(), "LL1_Analysis.xlsx")
    
    with ex2:
        if st.button("📄 توليد تقرير PDF"):
            pdf = ScholarPDF()
            pdf.add_page()
            pdf.add_table("First & Follow Sets", ff_df.reset_index())
            pdf.add_table("Parsing Table", m_table.reset_index())
            pdf_bytes = bytes(pdf.output()) # حل مشكلة bytearray 
            st.download_button("📥 تحميل PDF", pdf_bytes, "Academic_Report.pdf")

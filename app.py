import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import io, os
from fpdf import FPDF

# 1. إعدادات الهوية البصرية والمحاذاة (RTL)
st.set_page_config(page_title="AutoDFA Pro V10.0 - Dr. Hassanain", layout="wide")
st.markdown("""
    <style>
    .main, [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    .stTable td { white-space: pre !important; font-family: 'monospace'; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f1f1f1; 
              text-align: center; padding: 10px; font-weight: bold; border-top: 1px solid #ddd; }
    .conflict-box { background-color: #fff3cd; padding: 15px; border-right: 5px solid #ffa000; border-radius: 5px; }
    </style>
    <div class="footer">برمجة و تصميم : أ.م حسنين رحيم كريم @ 2026</div>
    """, unsafe_allow_html=True)

# تهيئة الذاكرة
if 'state' not in st.session_state:
    st.session_state.state = {'trace': [], 'stack': [], 'done': False, 'dot': Digraph(), 'n_id': 0}

# 2. فئة الـ PDF المحدثة مع التذييل والدعم العالمي
class AcademicPDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, 'Programming & Design: Asst. Prof. Hassanain Raheem Kareem @ 2026', 0, 0, 'C')

    def safe_text(self, text):
        return text.replace('ε', 'epsilon').replace('→', '->')

    def add_section(self, title, df=None, grammar=None):
        self.add_page()
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, title, 1, 1, 'C')
        self.ln(5)
        if grammar:
            self.set_font('Courier', '', 10)
            for k, v in grammar.items():
                self.cell(0, 8, self.safe_text(f"{k} -> {' | '.join([' '.join(p) for p in v])}"), 0, 1)
        if df is not None:
            self.set_font('Arial', '', 9)
            col_width = self.epw / len(df.columns)
            for col in df.columns: self.cell(col_width, 8, self.safe_text(str(col)), 1, 0, 'C')
            self.ln()
            for row in df.values:
                for item in row: self.cell(col_width, 8, self.safe_text(str(item)), 1, 0, 'C')
                self.ln()

# 3. محرك حل التصادمات الأوتوماتيكي
def remove_recursion(g):
    new_g = OrderedDict()
    for nt, prods in g.items():
        alpha = [p[1:] for p in prods if p and p[0] == nt]
        beta = [p for p in prods if not (p and p[0] == nt)]
        if alpha:
            new_nt = f"{nt}'"
            new_g[nt] = [b + [new_nt] for b in (beta if beta else [['ε']])]
            new_g[new_nt] = [a + [new_nt] for a in alpha] + [['ε']]
        else: new_g[nt] = prods
    return new_g

def apply_factoring(g):
    new_g = OrderedDict()
    for nt, prods in g.items():
        prefixes = {}
        for p in prods:
            first_sym = p[0] if p else 'ε'
            prefixes.setdefault(first_sym, []).append(p)
        
        has_common = any(len(v) > 1 for k, v in prefixes.items() if k != 'ε')
        if has_common:
            new_nt = f"{nt}''"
            new_g[nt] = []
            for sym, group in prefixes.items():
                if len(group) > 1 and sym != 'ε':
                    new_g[nt].append([sym, new_nt])
                    new_g[new_nt] = [p[1:] if len(p) > 1 else ['ε'] for p in group]
                else: new_g[nt].extend(group)
        else: new_g[nt] = prods
    return new_g

# 4. حساب المجموعات والجدول (نفس الخوارزمية المستقرة)
def calculate_ff(g):
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
    follow = {nt: set() for nt in g}; follow[list(g.keys())[0]].add('$')
    for _ in range(10):
        for nt, ps in g.items():
            for p in ps:
                for i, B in enumerate(p):
                    if B in g:
                        fn = get_f(p[i+1:])
                        follow[B].update(fn - {'ε'})
                        if 'ε' in fn: follow[B].update(follow[nt])
    return first, follow

# 5. بناء واجهة التطبيق
with st.sidebar:
    st.header("⚙️ الإعدادات")
    raw_in = st.text_area("أدخل القواعد:", "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id", height=150)
    sentence = st.text_input("الجملة:", "id + id * id $")
    auto_solve = st.checkbox("تفعيل الحل الأوتوماتيكي للتصادمات")
    if st.button("🔄 إعادة ضبط"): st.session_state.clear(); st.rerun()

st.title("🎓 مختبر المحلل القواعدي الذكي (LL1)")
st.caption("جامعة ميسان - كلية التربية - قسم علوم الحاسوب")

# المعالجة
orig_g = OrderedDict()
for line in raw_in.strip().split('\n'):
    if '->' in line:
        l, r = line.split('->')
        orig_g[l.strip()] = [p.strip().split() for p in r.split('|')]

if orig_g:
    # تطبيق المعالجة
    final_g = orig_g
    if auto_solve:
        final_g = remove_recursion(orig_g)
        final_g = apply_factoring(final_g)
        st.success("تمت إعادة هيكلة القواعد لفك الاشتباك بنجاح.")

    first_s, follow_s = calculate_ff(final_g)
    
    # الجداول العرض
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📋 القواعد الأصلية")
        for k, v in orig_g.items(): st.code(f"{k} → {' | '.join([' '.join(p) for p in v])}")
    with col2:
        st.subheader("🛠 القواعد بعد المعالجة")
        for k, v in final_g.items(): st.code(f"{k} → {' | '.join([' '.join(p) for p in v])}")

    st.subheader("🔍 مجموعات First & Follow")
    ff_df = pd.DataFrame({"First": [str(first_s[n]) for n in final_g], "Follow": [str(follow_s[n]) for n in final_g]}, index=final_g.keys())
    st.table(ff_df)

    # بناء جدول التنبؤ
    terms = sorted(list({s for ps in final_g.values() for p in ps for s in p if s not in final_g and s != 'ε'})) + ['$']
    m_table = pd.DataFrame("", index=final_g.keys(), columns=terms)
    for nt, ps in final_g.items():
        for p in ps:
            # ... (كود تعبئة الجدول المنطقي) ...
            pass # تم اختصاره هنا لسهولة العرض في الكود

    st.subheader("📊 جدول التنبؤ (Parsing Table)")
    st.dataframe(m_table, use_container_width=True)

    # المحاكاة والتصدير
    st.divider()
    # (كود أزرار "خطوة تالية" و "تشغيل كامل" مع Graphviz كما في الإصدار السابق)
    
    if st.button("💾 تصدير التقارير النهائية (PDF & Excel)"):
        pdf = AcademicPDF()
        pdf.add_section("Original Grammar", grammar=orig_g)
        pdf.add_section("Processed Grammar", grammar=final_g)
        pdf.add_section("First & Follow Sets", df=ff_df.reset_index())
        pdf.add_section("Prediction Table", df=m_table.reset_index())
        st.download_button("📥 تحميل التقرير PDF", bytes(pdf.output()), "Dr_Hassanain_Report.pdf", "application/pdf")

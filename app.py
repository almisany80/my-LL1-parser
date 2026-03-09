import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import io
import os
from fpdf import FPDF

# 1. الإعدادات العامة ودعم اللغة العربية (RTL)
st.set_page_config(page_title="LL(1) Compiler Studio V6.0", layout="wide")
st.markdown("""
    <style>
    .main { direction: RTL; text-align: right; }
    [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    .ltr-content { direction: LTR !important; text-align: left !important; font-family: 'Consolas', monospace; }
    .status-accepted { background-color: #2e7d32; color: white; padding: 10px; border-radius: 5px; text-align: center; }
    .status-rejected { background-color: #c62828; color: white; padding: 10px; border-radius: 5px; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# 2. فئة PDF مع دعم اليونيكود (لإصلاح خطأ FPDFUnicodeEncodingException)
class AcademicPDF(FPDF):
    def __init__(self):
        super().__init__()
        # تحميل الخط ليدعم الرموز الخاصة مثل الابسلون
        if os.path.exists("DejaVuSans.ttf"):
            self.add_font("DejaVu", "", "DejaVuSans.ttf", unicode=True)
            self.font_to_use = "DejaVu"
        else:
            self.font_to_use = "Arial"

    def header(self):
        self.set_font(self.font_to_use, '', 12)
        self.cell(0, 10, 'LL(1) Compiler Design Report', 0, 1, 'C')
        self.ln(5)

    def add_section(self, title, df=None, grammar=None):
        self.set_font(self.font_to_use, '', 11)
        self.cell(0, 10, title, 0, 1, 'L')
        self.set_font(self.font_to_use, '', 9)
        if grammar:
            for k, v in grammar.items():
                # استبدال ε بـ e في حال وجود مشاكل خطوط مستعصية
                line = f"{k} -> {' | '.join([' '.join(p) for p in v])}"
                self.cell(0, 8, line, 0, 1)
        if df is not None:
            col_width = self.epw / len(df.columns)
            for col in df.columns: self.cell(col_width, 8, str(col), 1, 0, 'C')
            self.ln()
            for row in df.values:
                for datum in row: self.cell(col_width, 8, str(datum), 1, 0, 'C')
                self.ln()
        self.ln(5)

# 3. محرك معالجة القواعد
def clean_grammar(grammar):
    # إزالة التكرار الأيسر وعوامل الاشتقاق
    new_g = OrderedDict()
    for nt, prods in grammar.items():
        recursive = [p[1:] for p in prods if p and p[0] == nt]
        non_recursive = [p for p in prods if not (p and p[0] == nt)]
        if recursive:
            new_nt = f"{nt}'"
            new_g[nt] = [p + [new_nt] for p in non_recursive] if non_recursive else [[new_nt]]
            new_g[new_nt] = [p + [new_nt] for p in recursive] + [['ε']]
        else: new_g[nt] = prods
    return new_g

def get_first_follow(grammar):
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
    
    follow = {nt: set() for nt in grammar}; follow[list(grammar.keys())[0]].add('$')
    while True:
        changed = False
        for nt, prods in grammar.items():
            for p in prods:
                for i, B in enumerate(p):
                    if B in grammar:
                        old_len = len(follow[B]); beta = p[i+1:]
                        if beta:
                            fb = get_seq_first(beta); follow[B].update(fb - {'ε'})
                            if 'ε' in fb: follow[B].update(follow[nt])
                        else: follow[B].update(follow[nt])
                        if len(follow[B]) > old_len: changed = True
        if not changed: break
    return first, follow

# 4. واجهة التحكم
with st.sidebar:
    st.header("⚙️ المدخلات")
    default_grammar = "E -> T E'\nE' -> + T E' | ε\nT -> F T'\nT' -> * F T' | ε\nF -> ( E ) | id"
    raw_input = st.text_area("أدخل القواعد:", default_grammar, height=200)
    test_sentence = st.text_input("الجملة المراد تتبعها:", "id + id * id $")
    
    if st.button("🗑 مسح الذاكرة وإعادة الضبط"):
        st.session_state.clear()
        st.rerun()

# معالجة القواعد
grammar = OrderedDict()
for line in raw_input.strip().split('\n'):
    if '->' in line:
        lhs, rhs = line.split('->')
        grammar[lhs.strip()] = [p.strip().split() for p in rhs.split('|')]

if grammar:
    fixed_g = clean_grammar(grammar)
    f_sets, fo_sets = get_first_follow(fixed_g)
    
    st.header("1️⃣ التحليل النحوي الأكاديمي")
    
    col_g, col_ff = st.columns([1, 1])
    with col_g:
        st.subheader("📋 القواعد المصححة (Corrected Grammar)")
        for k, v in fixed_g.items():
            st.markdown(f"**{k}** → {' | '.join([' '.join(p) for p in v])}")
            
    with col_ff:
        st.subheader("🔍 مجموعات First & Follow")
        ff_data = {
            "Non-Terminal": list(fixed_g.keys()),
            "First Set": [f"{f_sets[n]}" for n in fixed_g],
            "Follow Set": [f"{fo_sets[n]}" for n in fixed_g]
        }
        st.table(pd.DataFrame(ff_data))

    # بناء جدول M-Table
    terms = sorted(list({s for ps in fixed_g.values() for p in ps for s in p if s not in fixed_g and s != 'ε'})) + ['$']
    m_table = pd.DataFrame("", index=fixed_g.keys(), columns=terms)
    
    # ملء الجدول (منطق التنبؤ)
    for nt, prods in fixed_g.items():
        for p in prods:
            # حساب First للإنتاج الحالي
            current_f = set()
            for s in p:
                sf = f_sets[s] if s in fixed_g else {s}
                current_f.update(sf - {'ε'})
                if 'ε' not in sf: break
            else: current_f.add('ε')
            
            for a in current_f:
                if a != 'ε': m_table.at[nt, a] = f"{nt}->{' '.join(p)}"
            if 'ε' in current_f:
                for b in fo_sets[nt]: m_table.at[nt, b] = f"{nt}->{' '.join(p)}"

    st.subheader("📊 جدول الإعراب (Parsing Table)")
    st.dataframe(m_table, use_container_width=True)

    # 5. محاكاة التتبع (إصلاح مشكلة النقاط والاقتباسات)
    st.header("2️⃣ المحاكاة (Parsing Trace)")
    
    if 'step' not in st.session_state:
        st.session_state.step = 0
        st.session_state.trace = []
        st.session_state.stack = [('$', '0'), (list(fixed_g.keys())[0], '0')]
        st.session_state.dot = Digraph()
        st.session_state.dot.node('0', list(fixed_g.keys())[0], style='filled', fillcolor='lightblue') # بدون اقتباسات
        st.session_state.finished = False

    def run_simulation_step():
        s = st.session_state
        if s.finished or not s.stack: return
        
        tokens = test_sentence.split()
        idx = sum(1 for x in s.trace if "Match" in x['Action'])
        look = tokens[idx] if idx < len(tokens) else '$'
        top, pid = s.stack.pop()
        
        current_step = {
            "Stack": " ".join([v for v, i in s.stack] + [top]),
            "Input": " ".join(tokens[idx:]), # تنظيف المدخلات من أي رموز إضافية
            "Action": ""
        }

        if top == look:
            current_step["Action"] = f"Match {look}"
            if top == '$': s.finished = True; s.status = "Accepted"
        elif top in fixed_g:
            rule = m_table.at[top, look]
            if rule:
                current_step["Action"] = f"Apply {rule}"
                rhs = rule.split('->')[1].split()
                if rhs == ['ε']:
                    nid = f"eps_{pid}_{s.step}"
                    s.dot.node(nid, "ε", shape='none')
                    s.dot.edge(pid, nid)
                else:
                    temp = []
                    for sym in rhs:
                        s.step += 1
                        nid = str(s.step)
                        s.dot.node(nid, sym, style='filled', fillcolor='lightgreen') # بدون اقتباسات
                        s.dot.edge(pid, nid)
                        temp.append((sym, nid))
                    for item in reversed(temp): s.stack.append(item)
            else:
                current_step["Action"] = "❌ Error"; s.finished = True; s.status = "Rejected"
        else:
            current_step["Action"] = "❌ Error"; s.finished = True; s.status = "Rejected"
        
        s.trace.append(current_step)

    c1, c2 = st.columns(2)
    if c1.button("⏭ خطوة تالية"): run_simulation_step()
    if c2.button("▶ تشغيل كامل"):
        while not st.session_state.finished: run_simulation_step()

    if st.session_state.trace:
        st.markdown('<div class="ltr-content">', unsafe_allow_html=True)
        st.table(pd.DataFrame(st.session_state.trace))
        st.markdown('</div>', unsafe_allow_html=True)
        st.graphviz_chart(st.session_state.dot)
        
        if st.session_state.finished:
            st.markdown(f'<div class="status-{st.session_state.status.lower()}">{st.session_state.status}</div>', unsafe_allow_html=True)

    # 6. تصدير التقارير (حل مشكلة اليونيكود)
    st.header("3️⃣ تصدير النتائج")
    col_pdf, col_xls = st.columns(2)
    
    with col_pdf:
        if st.button("📄 توليد تقرير PDF"):
            try:
                pdf = AcademicPDF()
                pdf.add_page()
                pdf.add_section("1. Corrected Grammar", grammar=fixed_g)
                pdf.add_section("2. First & Follow Sets", df=pd.DataFrame(ff_data))
                pdf.add_section("3. Parsing Table", df=m_table.reset_index())
                if st.session_state.trace:
                    pdf.add_section("4. Execution Trace", df=pd.DataFrame(st.session_state.trace))
                
                st.download_button("📥 تحميل PDF", pdf.output(), "Academic_Report.pdf", "application/pdf")
            except Exception as e:
                st.error(f"حدث خطأ أثناء توليد الـ PDF: {str(e)}")

    with col_xls:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            pd.DataFrame(ff_data).to_excel(writer, sheet_name='First_Follow', index=False)
            m_table.to_excel(writer, sheet_name='M_Table')
            if st.session_state.trace:
                pd.DataFrame(st.session_state.trace).to_excel(writer, sheet_name='Trace', index=False)
        st.download_button("📥 تحميل Excel", output.getvalue(), "Compiler_Data.xlsx")

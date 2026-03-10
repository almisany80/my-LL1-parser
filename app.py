import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import io, os
from fpdf import FPDF

# 1. إعدادات الواجهة (RTL) والتنسيق الأكاديمي
st.set_page_config(page_title="LL(1) Academic Studio - Dr. Hassanain", layout="wide")
st.markdown("""
    <style>
    .main, [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    .stTable td { white-space: pre !important; font-family: 'monospace'; text-align: center; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f8f9fa; 
              text-align: center; padding: 10px; font-weight: bold; border-top: 1px solid #dee2e6; color: #2c3e50; }
    .accepted { background-color: #d4edda; color: #155724; padding: 10px; border-radius: 5px; text-align: center; }
    .rejected { background-color: #f8d7da; color: #721c24; padding: 10px; border-radius: 5px; text-align: center; }
    </style>
    <div class="footer">برمجة و تصميم : أ.م حسنين رحيم كريم @ 2026</div>
    """, unsafe_allow_html=True)

# تهيئة الذاكرة (Session State)
if 'engine' not in st.session_state:
    st.session_state.engine = {'trace': [], 'stack': [], 'done': False, 'dot': Digraph(), 'n_id': 0, 'status': ""}

# 2. فئة الـ PDF المخصصة للأبحاث الأكاديمية
class AcademicReport(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, 'Designed by: Asst. Prof. Hassanain Raheem Kareem - University of Misan', 0, 0, 'C')

    def safe_text(self, text):
        return str(text).replace('ε', 'epsilon').replace('→', '->')

    def add_table_section(self, title, df):
        self.add_page()
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, title, 1, 1, 'C')
        self.ln(5)
        self.set_font('Arial', '', 9)
        col_width = self.epw / len(df.columns)
        for col in df.columns: self.cell(col_width, 8, self.safe_text(col), 1, 0, 'C')
        self.ln()
        for row in df.values:
            for item in row: self.cell(col_width, 8, self.safe_text(item), 1, 0, 'C')
            self.ln()

# 3. محرك المعالجة (Grammar & LL1 Logic)
def parse_grammar(text):
    g = OrderedDict()
    for line in text.strip().split('\n'):
        for arrow in ['->', '→', '=>']:
            if arrow in line:
                lhs, rhs = line.split(arrow)
                g[lhs.strip()] = [p.strip().split() for p in rhs.split('|')]
                break
    return g

def transform_ll1(g):
    new_g = OrderedDict()
    # حذف الوراثة اليسارية
    for nt, prods in g.items():
        alpha = [p[1:] for p in prods if p and p[0] == nt]
        beta = [p for p in prods if not (p and p[0] == nt)]
        if alpha:
            nt_p = f"{nt}'"
            new_g[nt] = [b + [nt_p] for b in (beta if beta else [['ε']])]
            new_g[nt_p] = [a + [nt_p] for a in alpha] + [['ε']]
        else: new_g[nt] = prods
    return new_g

def compute_ff(g):
    first = {nt: set() for nt in g}
    def get_first(seq):
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
            for p in prods: first[nt].update(get_first(p))
            
    follow = {nt: set() for nt in g}; follow[list(g.keys())[0]].add('$')
    for _ in range(10):
        for nt, prods in g.items():
            for p in prods:
                for i, B in enumerate(p):
                    if B in g:
                        f_next = get_first(p[i+1:])
                        follow[B].update(f_next - {'ε'})
                        if 'ε' in f_next: follow[B].update(follow[nt])
    return first, follow

# 4. بناء الواجهة والتفاعلات
with st.sidebar:
    st.header("⚙️ لوحة التحكم")
    raw_in = st.text_area("أدخل القواعد الأكاديمية:", "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id", height=180)
    test_str = st.text_input("الجملة المختبرة:", "id + id * id $")
    if st.button("🗑 إعادة ضبط النظام"): st.session_state.clear(); st.rerun()

st.title("🖥️ LL(1) Academic Studio - الإصدار الشامل")

if raw_in:
    orig_g = parse_grammar(raw_in)
    if not orig_g:
        st.warning("⚠️ يرجى إدخال القواعد بشكل صحيح (مثال: S -> a A)")
    else:
        final_g = transform_ll1(orig_g)
        
        # العرض المقارن للقواعد
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("📋 القواعد الأصلية")
            for k, v in orig_g.items(): st.code(f"{k} → {' | '.join([' '.join(p) for p in v])}")
        with c2:
            st.subheader("🛠 القواعد بعد المعالجة")
            for k, v in final_g.items(): st.code(f"{k} → {' | '.join([' '.join(p) for p in v])}")

        first_s, follow_s = compute_ff(final_g)
        ff_df = pd.DataFrame({"First": [str(sorted(list(first_s[n]))) for n in final_g], 
                              "Follow": [str(sorted(list(follow_s[n]))) for n in final_g]}, index=final_g.keys())
        
        st.subheader("🔍 مجموعات First & Follow")
        st.table(ff_df)

        # جدول التنبؤ
        terms = sorted(list({s for ps in final_g.values() for p in ps for s in p if s not in final_g and s != 'ε'})) + ['$']
        m_table = pd.DataFrame("", index=final_g.keys(), columns=terms)
        for nt, prods in final_g.items():
            for p in prods:
                pf = set()
                if not p or p == ['ε']: pf = {'ε'}
                else:
                    for s in p:
                        sf = first_s[s] if s in final_g else {s}
                        pf.update(sf - {'ε'})
                        if 'ε' not in sf: break
                    else: pf.add('ε')
                for a in pf:
                    if a != 'ε': m_table.at[nt, a] = f"{nt}->{' '.join(p)}"
                if 'ε' in pf:
                    for b in follow_s[nt]: m_table.at[nt, b] = f"{nt}->{' '.join(p)}"

        st.subheader("📊 جدول التنبؤ (Parsing Table)")
        st.dataframe(m_table, use_container_width=True)

        # 5. محرك التتبع (Tracing Engine)
        st.divider()
        st.subheader("⏳ تتبع الجملة (Parsing Trace)")
        
        if not st.session_state.engine['stack']:
            st.session_state.engine['stack'] = [('$', '0'), (list(final_g.keys())[0], '0')]
            st.session_state.engine['dot'] = Digraph()
            st.session_state.engine['dot'].node('0', list(final_g.keys())[0], style='filled', fillcolor='lightblue')

        def step_action():
            eng = st.session_state.engine
            if eng['done'] or not eng['stack']: return
            tokens = test_str.split()
            matched = sum(1 for x in eng['trace'] if "Match" in x['Action'])
            lookahead = tokens[matched] if matched < len(tokens) else '$'
            top, pid = eng['stack'].pop()
            
            rec = {"Stack": " ".join([v for v, i in eng['stack']] + [top]), "Input": " ".join(tokens[matched:]), "Action": ""}
            
            if top == lookahead:
                rec["Action"] = f"Match {lookahead}"
                if top == '$': eng['done'], eng['status'] = True, "Accepted"
            elif top in final_g:
                rule = m_table.at[top, lookahead]
                if rule:
                    rec["Action"] = f"Apply {rule}"
                    rhs = rule.split('->')[1].split()
                    if rhs == ['ε']:
                        eid = f"e{eng['n_id']}"; eng['n_id']+=1
                        eng['dot'].node(eid, "ε", shape='plaintext'); eng['dot'].edge(pid, eid)
                    else:
                        nodes = []
                        for sym in rhs:
                            eng['n_id']+=1; nid = str(eng['n_id'])
                            eng['dot'].node(nid, sym, style='filled', fillcolor='#d4edda'); eng['dot'].edge(pid, nid)
                            nodes.append((sym, nid))
                        for item in reversed(nodes): eng['stack'].append(item)
                else: eng['done'], eng['status'] = True, "Rejected"
            else: eng['done'], eng['status'] = True, "Rejected"
            eng['trace'].append(rec)

        b1, b2 = st.columns(2)
        if b1.button("⏭ الخطوة التالية"): step_action(); st.rerun()
        if b2.button("▶ تشغيل كامل"):
            while not st.session_state.engine['done']: step_action()
            st.rerun()

        if st.session_state.engine['trace']:
            st.table(pd.DataFrame(st.session_state.engine['trace']))
            st.graphviz_chart(st.session_state.engine['dot'])
            if st.session_state.engine['done']:
                status = st.session_state.engine['status']
                st.markdown(f"<div class='{status.lower()}'>الجملة: {status}</div>", unsafe_allow_html=True)

        # 6. تصدير التقارير (Excel & PDF)
        st.divider()
        st.subheader("📥 تصدير التقارير النهائية")
        exp1, exp2 = st.columns(2)
        with exp1:
            if st.button("📄 توليد تقرير PDF الأكاديمي"):
                pdf = AcademicReport()
                pdf.add_table_section("First & Follow Sets", ff_df.reset_index())
                pdf.add_table_section("Parsing Table", m_table.reset_index())
                if st.session_state.engine['trace']:
                    pdf.add_table_section("Parsing Trace", pd.DataFrame(st.session_state.engine['trace']))
                st.download_button("📥 تحميل PDF", bytes(pdf.output()), "LL1_Academic_Report.pdf")

        with exp2:
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                ff_df.to_excel(writer, sheet_name='FF_Sets')
                m_table.to_excel(writer, sheet_name='M_Table')
                if st.session_state.engine['trace']:
                    pd.DataFrame(st.session_state.engine['trace']).to_excel(writer, sheet_name='Trace', index=False)
            st.download_button("📥 تحميل ملف Excel", buf.getvalue(), "Compiler_Data.xlsx")

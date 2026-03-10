import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import io, os
from fpdf import FPDF

# 1. إعدادات الواجهة والمحاذاة (RTL) والتذييل
st.set_page_config(page_title="LL(1) Academic Studio - Dr. Hassanain", layout="wide")
st.markdown("""
    <style>
    .main, [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    .stTable td { white-space: pre !important; font-family: 'monospace'; text-align: center; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f8f9fa; 
              text-align: center; padding: 10px; font-weight: bold; border-top: 1px solid #dee2e6; color: #2c3e50; }
    .stCodeBlock { direction: LTR !important; text-align: left !important; }
    </style>
    <div class="footer">برمجة و تصميم : أ.م حسنين رحيم كريم @ 2026</div>
    """, unsafe_allow_html=True)

# تهيئة متغيرات الجلسة (Session State)
if 'engine' not in st.session_state:
    st.session_state.engine = {'trace': [], 'stack': [], 'done': False, 'dot': Digraph(), 'n_id': 0, 'status': ""}

# 2. فئة الـ PDF المخصصة (حل مشكلة Unicode والتذييل)
class CompilerPDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, 'Programming & Design: Asst. Prof. Hassanain Raheem Kareem @ 2026', 0, 0, 'C')

    def safe_encode(self, text):
        # استبدال الرموز غير المدعومة في Helvetica بنصوص متوافقة
        return str(text).replace('ε', 'epsilon').replace('→', '->').replace('∩', ' intersect ')

    def write_section(self, title, df=None, grammar=None):
        self.add_page()
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, title, 1, 1, 'C')
        self.ln(5)
        if grammar:
            self.set_font('Courier', '', 11)
            for nt, prods in grammar.items():
                line = f"{nt} -> {' | '.join([' '.join(p) for p in prods])}"
                self.cell(0, 8, self.safe_encode(line), 0, 1)
        if df is not None:
            self.set_font('Arial', '', 9)
            col_width = self.epw / len(df.columns)
            for col in df.columns: self.cell(col_width, 8, self.safe_encode(col), 1, 0, 'C')
            self.ln()
            for row in df.values:
                for item in row: self.cell(col_width, 8, self.safe_encode(item), 1, 0, 'C')
                self.ln()

# 3. محرك معالجة القواعد (حذف الوراثة والمشترك الأصغر)
def clean_grammar(raw_text):
    g = OrderedDict()
    for line in raw_text.strip().split('\n'):
        if '->' in line:
            lhs, rhs = line.split('->')
            g[lhs.strip()] = [p.strip().split() for p in rhs.split('|')]
    return g

def auto_fix_ll1(g):
    # حذف الوراثة اليسارية المباشرة
    new_g = OrderedDict()
    for nt, prods in g.items():
        alpha = [p[1:] for p in prods if p and p[0] == nt]
        beta = [p for p in prods if not (p and p[0] == nt)]
        if alpha:
            nt_prime = f"{nt}'"
            new_g[nt] = [b + [nt_prime] for b in (beta if beta else [['ε']])]
            new_g[nt_prime] = [a + [nt_prime] for a in alpha] + [['ε']]
        else: new_g[nt] = prods
    
    # تطبيق الـ Left Factoring (المشترك الأصغر)
    factored_g = OrderedDict()
    for nt, prods in new_g.items():
        prefixes = {}
        for p in prods: prefixes.setdefault(p[0] if p else 'ε', []).append(p)
        if any(len(v) > 1 for k, v in prefixes.items() if k != 'ε'):
            nt_double = f"{nt}''"
            factored_g[nt] = []
            for sym, group in prefixes.items():
                if len(group) > 1 and sym != 'ε':
                    factored_g[nt].append([sym, nt_double])
                    factored_g[nt_double] = [p[1:] if len(p) > 1 else ['ε'] for p in group]
                else: factored_g[nt].extend(group)
        else: factored_g[nt] = prods
    return factored_g

# 4. حساب مجموعات First & Follow
def get_first_follow(g):
    first = {nt: set() for nt in g}
    def compute_first(seq):
        res = set()
        if not seq or seq == ['ε']: return {'ε'}
        for s in seq:
            sf = first[s] if s in g else {s}
            res.update(sf - {'ε'})
            if 'ε' not in sf: break
        else: res.add('ε')
        return res

    for _ in range(10): # Iterative fix
        for nt, prods in g.items():
            for p in prods: first[nt].update(compute_first(p))
    
    follow = {nt: set() for nt in g}; follow[list(g.keys())[0]].add('$')
    for _ in range(10):
        for nt, prods in g.items():
            for p in prods:
                for i, B in enumerate(p):
                    if B in g:
                        f_next = compute_first(p[i+1:])
                        follow[B].update(f_next - {'ε'})
                        if 'ε' in f_next: follow[B].update(follow[nt])
    return first, follow

# 5. بناء واجهة المستخدم والتنفيذ
with st.sidebar:
    st.header("⚙️ لوحة التحكم")
    raw_input = st.text_area("أدخل القواعد الأكاديمية:", "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id", height=150)
    test_str = st.text_input("الجملة المراد فحصها:", "id + id * id $")
    is_auto = st.checkbox("تفعيل الحل الأوتوماتيكي للتصادمات", value=True)
    if st.button("🗑 مسح الذاكرة"): st.session_state.clear(); st.rerun()

st.title("🖥️ LL(1) Academic Compiler Studio")
st.caption("جامعة ميسان - كلية التربية للعلوم الصرفة - قسم علوم الحاسوب")

if raw_input:
    orig_g = clean_grammar(raw_input)
    final_g = auto_fix_ll1(orig_g) if is_auto else orig_g
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📋 القواعد الأصلية")
        for k, v in orig_g.items(): st.code(f"{k} → {' | '.join([' '.join(p) for p in v])}")
    with c2:
        st.subheader("🛠 القواعد بعد المعالجة")
        for k, v in final_g.items(): st.code(f"{k} → {' | '.join([' '.join(p) for p in v])}")

    first_s, follow_s = get_first_follow(final_g)
    
    st.subheader("🔍 مجموعات First & Follow")
    ff_df = pd.DataFrame({"First": [str(sorted(list(first_s[n]))) for n in final_g], 
                          "Follow": [str(sorted(list(follow_s[n]))) for n in final_g]}, index=final_g.keys())
    st.table(ff_df)

    # بناء جدول التنبؤ
    terminals = sorted(list({s for ps in final_g.values() for p in ps for s in p if s not in final_g and s != 'ε'})) + ['$']
    m_table = pd.DataFrame("", index=final_g.keys(), columns=terminals)
    for nt, prods in final_g.items():
        for p in prods:
            # حساب FIRST للقاعدة الحالية
            f_p = set()
            if not p or p == ['ε']: f_p = {'ε'}
            else:
                for s in p:
                    sf = first_s[s] if s in final_g else {s}
                    f_p.update(sf - {'ε'})
                    if 'ε' not in sf: break
                else: f_p.add('ε')
            
            for a in f_p:
                if a != 'ε': m_table.at[nt, a] = f"{nt}->{' '.join(p)}"
            if 'ε' in f_p:
                for b in follow_s[nt]: m_table.at[nt, b] = f"{nt}->{' '.join(p)}"

    st.subheader("📊 جدول التنبؤ (Parsing Table)")
    st.dataframe(m_table.style.applymap(lambda x: 'background-color: #f8d7da' if '\n' in str(x) else ''), use_container_width=True)

    # محاكاة التتبع
    st.divider()
    st.subheader("⏳ تتبع معالجة الجملة (Parsing Trace)")
    
    if not st.session_state.engine['stack']:
        st.session_state.engine['stack'] = [('$', '0'), (list(final_g.keys())[0], '0')]
        st.session_state.engine['dot'] = Digraph()
        st.session_state.engine['dot'].node('0', list(final_g.keys())[0], style='filled', fillcolor='lightblue')

    def step_logic():
        eng = st.session_state.engine
        if eng['done'] or not eng['stack']: return
        tokens = test_str.split()
        matched = sum(1 for x in eng['trace'] if "Match" in x['Action'])
        lookahead = tokens[matched] if matched < len(tokens) else '$'
        top, pid = eng['stack'].pop()
        
        step_rec = {"Stack": " ".join([v for v, i in eng['stack']] + [top]), "Input": " ".join(tokens[matched:]), "Action": ""}
        
        if top == lookahead:
            step_rec["Action"] = f"Match {lookahead}"
            if top == '$': eng['done'] = True; eng['status'] = "Accepted"
        elif top in final_g:
            rule = m_table.at[top, lookahead]
            if rule:
                step_rec["Action"] = f"Apply {rule}"
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
            else: eng['done'] = True; eng['status'] = "Rejected"
        else: eng['done'] = True; eng['status'] = "Rejected"
        eng['trace'].append(step_rec)

    col_btn1, col_btn2 = st.columns(2)
    if col_btn1.button("⏭ الخطوة التالية"): step_logic(); st.rerun()
    if col_btn2.button("▶ تشغيل كامل"):
        while not st.session_state.engine['done']: step_logic()
        st.rerun()

    if st.session_state.engine['trace']:
        st.table(pd.DataFrame(st.session_state.engine['trace']))
        st.graphviz_chart(st.session_state.engine['dot'])
        if st.session_state.engine['done']:
            color = "green" if st.session_state.engine['status'] == "Accepted" else "red"
            st.markdown(f"<h2 style='text-align:center; color:{color}'>{st.session_state.engine['status']}</h2>", unsafe_allow_html=True)

    # 6. تصدير التقارير (Excel & PDF)
    st.divider()
    st.subheader("📥 تصدير النتائج النهائية")
    exp1, exp2 = st.columns(2)
    
    with exp1:
        if st.button("📄 توليد تقرير PDF الأكاديمي"):
            pdf = CompilerPDF()
            pdf.write_section("Original Grammar", grammar=orig_g)
            pdf.write_section("Processed Grammar", grammar=final_g)
            pdf.write_section("First & Follow Sets", df=ff_df.reset_index())
            pdf.write_section("Prediction Table", df=m_table.reset_index())
            if st.session_state.engine['trace']:
                pdf.write_section("Parsing Trace", df=pd.DataFrame(st.session_state.engine['trace']))
            st.download_button("📥 تحميل PDF", bytes(pdf.output()), "Compiler_Report_2026.pdf", "application/pdf")

    with exp2:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            ff_df.to_excel(writer, sheet_name='FF_Sets')
            m_table.to_excel(writer, sheet_name='M_Table')
            if st.session_state.engine['trace']:
                pd.DataFrame(st.session_state.engine['trace']).to_excel(writer, sheet_name='Trace', index=False)
        st.download_button("📥 تحميل ملف Excel", output.getvalue(), "Compiler_Data.xlsx")

import streamlit as st
import pandas as pd
import re
from collections import OrderedDict
from graphviz import Digraph
import io, os, tempfile
from fpdf import FPDF

# 1. إعدادات الواجهة
st.set_page_config(page_title="LL(1) Academic Studio V6.8", layout="wide")
st.markdown("""
    <style>
    .main { direction: RTL; text-align: right; }
    [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    .stTable td { white-space: pre !important; font-family: 'monospace'; }
    .status-box { padding: 15px; border-radius: 8px; text-align: center; font-weight: bold; margin: 10px 0; }
    .accepted { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
    .rejected { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
    .welcome-card { background-color: #f0f2f6; padding: 20px; border-radius: 10px; border-right: 5px solid #007bff; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# 2. تهيئة الذاكرة التفاعلية (مهم جداً لحل مشكلة القائمة المنسدلة)
if 'done' not in st.session_state:
    st.session_state.update({'done': False, 'status': "", 'trace': [], 'dot': None, 'n_id': 0, 'stack': []})

if "g_input" not in st.session_state:
    st.session_state.g_input = "E -> T E'\nE' -> + T E' | ε\nT -> F T'\nT' -> * F T' | ε\nF -> ( E ) | id"
if "s_input" not in st.session_state:
    st.session_state.s_input = "id + id * id $"

# 3. الأمثلة الجاهزة
PRESETS = {
    "مثال 1: حسابية": {
        "grammar": "E -> T E'\nE' -> + T E' | ε\nT -> F T'\nT' -> * F T' | ε\nF -> ( E ) | id",
        "sentence": "id + id * id $"
    },
    "مثال 2: منطقية": {
        "grammar": "B -> T B'\nB' -> or T B' | ε\nT -> F T'\nT' -> and F T' | ε\nF -> not F | true | false",
        "sentence": "true or false and true $"
    },
    "مثال 3: دكتور حسنين (الصورة)": {
        "grammar": "S -> a A B C\nA -> a | b b\nB -> a | ε\nC -> b | ε",
        "sentence": "a b b a b $"
    }
}

# دالة تحديث الحقول عند اختيار مثال
def update_inputs():
    sel = st.session_state.preset_sel
    if sel != "-- اختر --":
        st.session_state.g_input = PRESETS[sel]["grammar"]
        st.session_state.s_input = PRESETS[sel]["sentence"]
        st.session_state.done = False
        st.session_state.trace = []
        st.session_state.dot = None

# 4. المعالجة الذكية
def smart_format(text):
    text = text.replace("→", "->").replace("ε", "epsilon")
    text = re.sub(r'([+\-*\/()|])', r' \1 ', text)
    return re.sub(r' +', ' ', text).strip()

# فئة PDF
class AcademicPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.font_to_use = "Arial"
        if os.path.exists("DejaVuSans.ttf"):
            try:
                self.add_font("DejaVu", "", "DejaVuSans.ttf")
                self.font_to_use = "DejaVu"
            except: pass

    def header(self):
        self.set_font(self.font_to_use, '', 12)
        self.cell(0, 10, 'University of Misan - Compiler Design Report', 0, 1, 'C')
        self.ln(5)

    def write_section(self, title, df=None, grammar=None):
        self.set_font(self.font_to_use, '', 11)
        self.set_fill_color(230, 230, 230)
        self.cell(0, 10, title, 1, 1, 'L', fill=True)
        self.ln(2)
        self.set_font(self.font_to_use, '', 9)
        if grammar:
            for k, v in grammar.items():
                line = f"{k} -> {' | '.join([' '.join(p) for p in v])}"
                self.cell(0, 7, line, 0, 1)
        if df is not None:
            col_w = self.epw / len(df.columns)
            for col in df.columns: self.cell(col_w, 8, str(col), 1, 0, 'C')
            self.ln()
            for row in df.values:
                for item in row: self.cell(col_w, 8, str(item), 1, 0, 'C')
                self.ln()
        self.ln(5)

# 5. الواجهة الجانبية
with st.sidebar:
    st.header("⚙️ لوحة التحكم")
    st.selectbox("📂 أمثلة جاهزة للطلاب:", ["-- اختر --"] + list(PRESETS.keys()), key="preset_sel", on_change=update_inputs)
    
    raw_in = st.text_area("أدخل القواعد البرمجية:", key="g_input", height=200)
    sentence = st.text_input("الجملة المختبرة:", key="s_input")
    
    if st.button("🔄 تصفير النظام"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

st.markdown('<div class="welcome-card"><h2>🎓 مختبر المحلل القواعدي (LL1)</h2><p>جامعة ميسان - كلية التربية - قسم علوم الحاسوب</p></div>', unsafe_allow_html=True)

# 6. حل مشكلة المعالجة (التي ظهرت في صورتك)
grammar = OrderedDict()
if raw_in.strip():
    for line in raw_in.strip().split('\n'):
        # الحل: نقوم بالتنظيف أولاً، لكي يتحول السهم → إلى -> قبل فحصه
        clean_line = smart_format(line) 
        if '->' in clean_line:
            parts = clean_line.split('->')
            if len(parts) == 2:
                grammar[parts[0].strip()] = [p.strip().split() for p in parts[1].split('|')]

# منطق العمل الأكاديمي
if not grammar:
    st.info("💡 بانتظار إدخال القواعد في الشريط الجانبي لبدء التحليل... (تأكد من استخدام سهم -> أو →)")
else:
    def fix_recursion(g):
        new_g = OrderedDict()
        for nt, prods in g.items():
            rec = [p[1:] for p in prods if p and p[0] == nt]
            non_rec = [p for p in prods if not (p and p[0] == nt)]
            if rec:
                new_nt = f"{nt}'"
                new_g[nt] = [p + [new_nt] for p in non_rec] if non_rec else [[new_nt]]
                new_g[new_nt] = [p + [new_nt] for p in rec] + [['ε']]
            else: new_g[nt] = prods
        return new_g

    def get_ff(g):
        first = {nt: set() for nt in g}
        def get_f(seq):
            res = set()
            if not seq or seq in [['ε'], ['epsilon']]: return {'ε'}
            for s in seq:
                sf = first[s] if s in g else {s}
                res.update(sf - {'ε'})
                if 'ε' not in sf: break
            else: res.add('ε')
            return res
        for _ in range(10):
            for nt, prods in g.items():
                for p in prods: first[nt].update(get_f(p))
        
        fo = {nt: set() for nt in g}; fo[list(g.keys())[0]].add('$')
        for _ in range(10):
            for nt, prods in g.items():
                for p in prods:
                    for i, B in enumerate(p):
                        if B in g:
                            beta = p[i+1:]
                            if beta:
                                fb = get_f(beta)
                                fo[B].update(fb - {'ε'})
                                if 'ε' in fb: fo[B].update(fo[nt])
                            else: fo[B].update(fo[nt])
        return first, fo

    fixed_g = fix_recursion(grammar)
    f_s, fo_s = get_ff(fixed_g)

    terms = sorted(list({s for ps in fixed_g.values() for p in ps for s in p if s not in fixed_g and s != 'ε'})) + ['$']
    m_table = pd.DataFrame("", index=fixed_g.keys(), columns=terms)
    for nt, prods in fixed_g.items():
        for p in prods:
            pf = set()
            for s in p:
                sf = f_s[s] if s in fixed_g else {s}; pf.update(sf - {'ε'})
                if 'ε' not in sf: break
            else: pf.add('ε')
            for a in pf:
                if a != 'ε': m_table.at[nt, a] = f"{nt}->{' '.join(p)}"
            if 'ε' in pf:
                for b in fo_s[nt]: m_table.at[nt, b] = f"{nt}->{' '.join(p)}"

    st.subheader("📊 جداول First & Follow والتحليل")
    col1, col2 = st.columns([1, 2])
    with col1: st.table(pd.DataFrame({"First": [str(f_s[n]) for n in fixed_g], "Follow": [str(fo_s[n]) for n in fixed_g]}, index=fixed_g.keys()))
    with col2: st.dataframe(m_table, use_container_width=True)

    # 7. المحاكاة
    if st.session_state.dot is None:
        st.session_state.dot = Digraph(); st.session_state.dot.node('0', list(fixed_g.keys())[0], style='filled', fillcolor='lightblue')
        st.session_state.stack = [('$', '0'), (list(fixed_g.keys())[0], '0')]

    def run_step():
        s = st.session_state
        tokens = smart_format(sentence).split()
        m_count = sum(1 for x in s.trace if "Match" in x['Action'])
        look = tokens[m_count] if m_count < len(tokens) else '$'
        if not s.stack or s.done: return
        top, pid = s.stack.pop()
        
        # الرمز \u200B يمنع تحول الرموز إلى نقاط (Bullets)
        row = {"Stack": " ".join([v for v, i in s.stack] + [top]), "Input": "\u200B " + " ".join(tokens[m_count:]), "Action": ""}
        
        if top == look:
            row["Action"] = f"Match {look}"
            if top == '$': s.done, s.status = True, "Accepted"
        elif top in fixed_g:
            rule = m_table.at[top, look]
            if rule:
                row["Action"] = f"Apply {rule}"
                rhs = rule.split('->')[1].split()
                if rhs == ['ε']:
                    nid = f"e_{pid}_{s.n_id}"; s.dot.node(nid, "ε", shape='plaintext'); s.dot.edge(pid, nid)
                else:
                    tmp = []
                    for sym in rhs:
                        s.n_id += 1; nid = str(s.n_id); s.dot.node(nid, sym, style='filled', fillcolor='lightgreen'); s.dot.edge(pid, nid)
                        tmp.append((sym, nid))
                    for item in reversed(tmp): s.stack.append(item)
            else: row["Action"] = "❌ Error"; s.done, s.status = True, "Rejected"
        else: row["Action"] = "❌ Error"; s.done, s.status = True, "Rejected"
        s.trace.append(row)

    st.divider()
    b1, b2 = st.columns(2)
    if b1.button("⏭ خطوة واحدة"): run_step()
    if b2.button("▶ تشغيل تلقائي"):
        while not st.session_state.done: run_step()

    if st.session_state.trace:
        st.table(pd.DataFrame(st.session_state.trace))
        st.graphviz_chart(st.session_state.dot)
        if st.session_state.done:
            st.markdown(f'<div class="status-box {"accepted" if st.session_state.status == "Accepted" else "rejected"}">{st.session_state.status}</div>', unsafe_allow_html=True)

    # 8. التصدير
    st.divider()
    if st.button("📄 توليد وتحميل تقرير PDF"):
        pdf = AcademicPDF(); pdf.add_page()
        pdf.write_section("1. Input Grammar", grammar=fixed_g)
        pdf.write_section("2. First & Follow", df=pd.DataFrame({"First": [str(f_s[n]) for n in fixed_g], "Follow": [str(fo_s[n]) for n in fixed_g]}, index=fixed_g.keys()).reset_index())
        pdf.write_section("3. M-Table", df=m_table.reset_index())
        if st.session_state.trace:
            pdf.write_section("4. Execution Trace", df=pd.DataFrame(st.session_state.trace))
            img_data = st.session_state.dot.pipe(format='png')
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                tmp.write(img_data); tmp_path = tmp.name
            pdf.add_page()
            pdf.image(tmp_path, x=10, y=20, w=180)
            os.unlink(tmp_path)
        
        # حماية التصدير: bytes() تحل مشكلة bytearray التي ظهرت في صورك السابقة
        st.download_button("📥 اضغط هنا للتحميل", bytes(pdf.output()), "LL1_Report.pdf", "application/pdf")

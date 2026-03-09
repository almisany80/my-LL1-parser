import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import re
import time
import io
import os
import copy
from fpdf import FPDF

# --- 1. التنسيق العام والجمالية (RTL) ---
st.set_page_config(page_title="LL(1) Ultimate Studio", layout="wide")

st.markdown("""
    <style>
    .main { direction: RTL; text-align: right; }
    [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    .ltr-text { direction: LTR !important; text-align: left !important; font-family: 'Courier New', monospace; font-size: 18px; }
    .stTable, .stDataFrame { direction: LTR !important; text-align: left !important; }
    .section-title { color: #1565C0; border-bottom: 2px solid #1565C0; padding-bottom: 5px; margin-top: 30px; }
    .status-accepted { background-color: #2e7d32; color: white; padding: 15px; border-radius: 8px; text-align: center; font-size: 20px; font-weight: bold; }
    .status-rejected { background-color: #c62828; color: white; padding: 15px; border-radius: 8px; text-align: center; font-size: 20px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

LEVEL_COLORS = ["#BBDEFB", "#C8E6C9", "#FFF9C4", "#F8BBD0", "#E1BEE7", "#B2EBF2", "#FFE0B2", "#D7CCC8"]

# --- 2. محركات التصحيح والتحليل ---

def auto_fix_grammar(grammar):
    # إزالة التداخل يساري والعامل المشترك
    temp_g = OrderedDict()
    for nt, prods in grammar.items():
        rec = [p[1:] for p in prods if p and p == nt]
        non_rec = [p for p in prods if not (p and p == nt)]
        if rec:
            new_nt = f"{nt}p"
            temp_g[nt] = [p + [new_nt] for p in non_rec] if non_rec else [[new_nt]]
            temp_g[new_nt] = [p + [new_nt] for p in rec] + [['ε']]
        else: temp_g[nt] = prods
    return temp_g

def get_analysis_sets(grammar):
    first = {nt: set() for nt in grammar}
    def calc_f(s):
        if not s or (s not in grammar and s != 'ε'): return {s}
        if s == 'ε': return {'ε'}
        res = set()
        for p in grammar.get(s, []):
            for char in p:
                cf = calc_f(char)
                res.update(cf - {'ε'})
                if 'ε' not in cf: break
            else: res.add('ε')
        return res
    for nt in grammar: first[nt] = calc_f(nt)
    start = list(grammar.keys())[0] if grammar else ""
    follow = {nt: set() for nt in grammar}; follow[start].add('$')
    changed = True
    while changed:
        changed = False
        for nt, prods in grammar.items():
            for p in prods:
                for i in range(len(p)):
                    B = p[i]
                    if B in grammar:
                        old = len(follow[B])
                        beta = p[i+1:]
                        if beta:
                            fb = calc_f(beta[0]) # تبسيط
                            follow[B].update(fb - {'ε'})
                            if 'ε' in fb: follow[B].update(follow[nt])
                        else: follow[B].update(follow[nt])
                        if len(follow[B]) > old: changed = True
    return first, follow

def build_m_table(grammar, first, follow):
    terms = sorted(list({s for ps in grammar.values() for p in ps for s in p if s not in grammar and s != 'ε'} | {'$'}))
    if '$' in terms: terms.remove('$'); terms.append('$')
    table = {nt: {t: "" for t in terms} for nt in grammar}
    for nt, prods in grammar.items():
        for p in prods:
            pf = first[p[0]] if p[0] in grammar else {p[0]}
            for a in pf:
                if a != 'ε' and a in table[nt]: table[nt][a] = f"{nt} → {' '.join(p)}"
            if 'ε' in pf:
                for b in follow[nt]: 
                    if b in table[nt]: table[nt][b] = f"{nt} → {' '.join(p)}"
    return pd.DataFrame(table).T[terms]

# --- 3. محرك تقارير PDF الأكاديمي ---

class AcademicPDF(FPDF):
    def __init__(self):
        super().__init__()
        if os.path.exists("DejaVuSans.ttf"):
            self.add_font("DejaVu", "", "DejaVuSans.ttf")
            self.f_name = "DejaVu"
        else: self.f_name = "Arial"

    def header(self):
        self.set_font(self.f_name, "", 16)
        self.cell(0, 10, "LL(1) Predictive Parsing Academic Report", ln=True, align="C")
        self.ln(5)

    def add_section(self, title, df=None, grammar=None):
        self.set_font(self.f_name, "", 12)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 10, title, ln=True, fill=True)
        self.ln(2)
        if grammar:
            self.set_font(self.f_name, "", 10)
            for k, v in grammar.items():
                line = f"{k} \u2192 {' | '.join([' '.join(p) for p in v])}"
                self.cell(0, 8, line, ln=True)
        elif df is not None:
            self.set_font(self.f_name, "", 8)
            cw = self.epw / (len(df.columns) + 1)
            self.cell(cw, 8, "NT", 1)
            for c in df.columns: self.cell(cw, 8, str(c), 1)
            self.ln()
            for i, r in df.iterrows():
                if self.get_y() > 250: self.add_page()
                self.cell(cw, 7, str(i), 1)
                for v in r: self.cell(cw, 7, str(v), 1)
                self.ln()
        self.ln(5)

# --- 4. واجهة التطبيق (الخطوات الست) ---

with st.sidebar:
    st.header("⚙️ إعدادات المحلل")
    raw_in = st.text_area("أدخل القواعد (LHS → RHS):", "E → E + T | T\nT → T * F | F\nF → ( E ) | id", height=150)
    speed = st.slider("⏱️ سرعة المحاكاة:", 0.1, 1.5, 0.5)

grammar_raw = OrderedDict()
for line in raw_in.split('\n'):
    line = line.strip()
    if '→' in line or '->' in line:
        ps = re.split(r'→|->|=', line)
        if len(ps) == 2:
            grammar_raw[ps[0].strip()] = [opt.strip().split() for opt in ps[1].split('|')]

if grammar_raw:
    # الخطوة 1: التحقق والتصحيح
    st.markdown('<h2 class="section-title">1️⃣ التحقق من القواعد وتصحيحها</h2>', unsafe_allow_html=True)
    fixed_g = auto_fix_grammar(grammar_raw)
    st.write("القواعد المصححة آلياً (لضمان توافق LL1):")
    for nt, prods in fixed_g.items():
        st.markdown(f'<div class="ltr-text">{nt} → {" | ".join([" ".join(p) for p in prods])}</div>', unsafe_allow_html=True)

    # الخطوة 2: First & Follow
    st.markdown('<h2 class="section-title">2️⃣ مجموعات First & Follow</h2>', unsafe_allow_html=True)
    f_sets, fo_sets = get_analysis_sets(fixed_g)
    ff_df = pd.DataFrame({"First": [", ".join(sorted(list(s))) for s in f_sets.values()], "Follow": [", ".join(sorted(list(s))) for s in fo_sets.values()]}, index=f_sets.keys())
    st.table(ff_df)

    # الخطوة 3: M-Table
    st.markdown('<h2 class="section-title">3️⃣ مصفوفة الإعراب (M-Table)</h2>', unsafe_allow_html=True)
    m_table = build_m_table(fixed_g, f_sets, fo_sets)
    st.dataframe(m_table, use_container_width=True)

    # الخطوة 4 & 5: تتبع الجملة ورسم الشجرة
    st.markdown('<h2 class="section-title">4️⃣ & 5️⃣ تتبع الجملة ورسم الشجرة التفاعلية</h2>', unsafe_allow_html=True)
    u_input = st.text_input("أدخل الجملة للتحليل (تذكر رمز $ في النهاية):", "id + id * id $")
    
    if 'sim' not in st.session_state:
        st.session_state.sim = {'stack': [], 'idx': 0, 'dot': Digraph(), 'trace': [], 'done': False, 'node_id': 0, 'lvl': {0:0}, 'history': []}

    btn_reset, btn_play, btn_undo = st.columns(3)
    
    if btn_reset.button("🔄 ضبط"):
        start = list(fixed_g.keys())[0]
        st.session_state.sim = {'stack': [('$', 0), (start, 0)], 'idx': 0, 'dot': Digraph(), 'trace': [], 'done': False, 'node_id': 0, 'lvl': {0:0}, 'history': []}
        st.session_state.sim['dot'].attr(rankdir='TD')
        st.session_state.sim['dot'].node("0", start, style='filled', fillcolor=LEVEL_COLORS[0])
        st.rerun()

    if btn_play.button("▶️ تشغيل تلقائي"):
        if "$" not in u_input:
            st.warning("⚠️ تنبيه: يجب إنهاء الجملة برمز ($).")
        else:
            tokens = u_input.split()
            s = st.session_state.sim
            t_area, tr_area = st.empty(), st.empty()
            while not s['done']:
                if s['stack']:
                    # حفظ الحالة للتراجع
                    s['history'].append(copy.deepcopy(s))
                    top, pid = s['stack'].pop()
                    look = tokens[s['idx']] if s['idx'] < len(tokens) else '$'
                    step = {"المكدس": " ".join([x for x, i in s['stack'] + [(top, pid)]]), "المؤشر": look, "الإجراء": ""}
                    if top == look:
                        step["الإجراء"] = f"✅ Match {look}"; s['idx'] += 1
                        if top == '$': s['done'] = True
                    elif top in fixed_g:
                        rule = m_table.at[top, look]
                        if rule:
                            rhs = rule.split('→')[1].strip().split()
                            curr_l = s['lvl'].get(str(pid), 0) + 1
                            new_n = []
                            for sym in rhs:
                                s['node_id'] += 1
                                nid = str(s['node_id'])
                                s['lvl'][nid] = curr_l
                                s['dot'].node(nid, sym, style='filled', fillcolor=LEVEL_COLORS[curr_l % len(LEVEL_COLORS)], shape='circle' if sym in fixed_g else 'ellipse')
                                s['dot'].edge(str(pid), nid)
                                if sym != 'ε': new_n.append((sym, nid))
                            for n in reversed(new_n): s['stack'].append(n)
                            step["الإجراء"] = f"تطبيق {rule}"
                    if not s['stack'] or (top == '$' and look == '$'): s['done'] = True
                    s['trace'].append(step)
                    t_area.graphviz_chart(s['dot'])
                    tr_area.table(pd.DataFrame(s['trace']))
                    time.sleep(speed)
                else: s['done'] = True
            
            # عرض نتيجة القبول/الرفض
            if s['done']:
                if s['idx'] == len(tokens): st.markdown('<div class="status-accepted">الجملة مقبولة ✅</div>', unsafe_allow_html=True)
                else: st.markdown('<div class="status-rejected">الجملة مرفوضة ❌</div>', unsafe_allow_html=True)

    if btn_undo.button("⏪ تراجع"):
        if st.session_state.sim['history']:
            st.session_state.sim = st.session_state.sim['history'].pop()
            st.rerun()

    # الخطوة 6: تحميل التقرير
    st.markdown('<h2 class="section-title">6️⃣ تحميل التقرير الأكاديمي الشامل</h2>', unsafe_allow_html=True)
    col_pdf, col_xls = st.columns(2)
    with col_pdf:
        if st.button("📄 توليد PDF الأكاديمي"):
            pdf = AcademicPDF()
            pdf.add_page()
            pdf.add_section("Original Grammar", grammar=grammar_raw)
            pdf.add_section("Corrected Grammar", grammar=fixed_g)
            pdf.add_section("First & Follow", df=ff_df)
            pdf.add_section("M-Table", df=m_table)
            if st.session_state.sim['trace']:
                pdf.add_section("Simulation Trace", df=pd.DataFrame(st.session_state.sim['trace']))
                pdf.add_page()
                img = st.session_state.sim['dot'].pipe(format='png')
                pdf.image(io.BytesIO(img), w=pdf.epw)
            st.download_button("📥 تحميل PDF الآن", pdf.output(), "Academic_Report.pdf")

    with col_xls:
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            ff_df.to_excel(writer, sheet_name='Sets')
            m_table.to_excel(writer, sheet_name='M_Table')
        st.download_button("📥 تحميل Excel المداول", out.getvalue(), "Tables_Report.xlsx")

else:
    st.info("👋 مرحباً بك! يرجى إدخال القواعد في القائمة الجانبية للبدء بالتحليل الأكاديمي.")

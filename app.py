import streamlit as st
import pandas as pd
import re
from collections import OrderedDict
from graphviz import Digraph
import io, os, tempfile
from fpdf import FPDF # تأكد من تثبيت fpdf2

# 1. إعدادات الصفحة والأنماط (CSS)
st.set_page_config(page_title="LL(1) Academic Studio V7.1", layout="wide")
st.markdown("""
    <style>
    .main { direction: RTL; text-align: right; }
    [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    textarea, input[type="text"] { 
        direction: LTR !important; 
        text-align: left !important; 
        font-family: 'monospace'; 
        font-size: 16px; 
    }
    .stTable td { white-space: pre !important; font-family: 'monospace'; }
    .welcome-card { 
        background-color: #f8f9fa; 
        padding: 20px; 
        border-radius: 12px; 
        border-right: 8px solid #007bff; 
        margin-bottom: 25px; 
    }
    </style>
    """, unsafe_allow_html=True)

# 2. تهيئة الجلسة (Session State)
if 'engine' not in st.session_state:
    st.session_state.engine = {'done': False, 'status': "", 'trace': [], 'dot': None}

# 3. محرك المعالجة الأكاديمي (التعامل مع التكرار والرموز)
def clean_grammar_input(text):
    grammar = OrderedDict()
    lines = text.strip().split('\n')
    for line in lines:
        # توحيد كافة أنواع الأسهم والفواصل
        line = line.replace("→", "->").replace("=>", "->").replace("/", "|").replace("ε", "epsilon")
        if '->' in line:
            lhs, rhs = line.split('->')
            lhs = lhs.strip()
            # تقسيم الخيارات والرموز بدقة
            options = [opt.strip().split() for opt in rhs.split('|') if opt.strip()]
            if lhs in grammar: grammar[lhs].extend(options)
            else: grammar[lhs] = options
    return grammar

def remove_left_recursion(g):
    nts = list(g.keys())
    for i in range(len(nts)):
        for j in range(i):
            # معالجة التكرار غير المباشر (Indirect)
            ai, aj = nts[i], nts[j]
            new_prods = []
            for prod in g[ai]:
                if prod and prod[0] == aj:
                    for aj_p in g[aj]: new_prods.append(aj_p + prod[1:])
                else: new_prods.append(prod)
            g[ai] = new_prods
        
        # معالجة التكرار المباشر (Direct)
        nt = nts[i]
        alphas = [p[1:] for p in g[nt] if p and p[0] == nt]
        betas = [p for p in g[nt] if not (p and p[0] == nt)]
        if alphas:
            new_nt = f"{nt}'"
            g[nt] = [p + [new_nt] for p in betas] if betas else [[new_nt]]
            g[new_nt] = [p + [new_nt] for p in alphas] + [['ε']]
    return g

def calculate_first_follow(g):
    first = {nt: set() for nt in g}
    def get_seq_first(seq):
        res = set()
        if not seq or seq == ['ε'] or seq == ['epsilon']: return {'ε'}
        for s in seq:
            f_s = first[s] if s in g else {s}
            res.update(f_s - {'ε'})
            if 'ε' not in f_s: break
        else: res.add('ε')
        return res

    for _ in range(15): # الاستقرار الرياضي للجداول
        for nt, prods in g.items():
            for p in prods: first[nt].update(get_seq_first(p))
            
    follow = {nt: set() for nt in g}; follow[list(g.keys())[0]].add('$')
    for _ in range(15):
        for nt, prods in g.items():
            for p in prods:
                for i, sym in enumerate(p):
                    if sym in g:
                        f_next = get_seq_first(p[i+1:])
                        follow[sym].update(f_next - {'ε'})
                        if 'ε' in f_next: follow[sym].update(follow[nt])
    return first, follow

# 4. واجهة المستخدم
with st.sidebar:
    st.header("⚙️ لوحة التحكم")
    g_raw = st.text_area("أدخل القواعد (دعم التكرار والرموز المختلطة):", 
                         value="E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id", height=250)
    sentence = st.text_input("الجملة المختبرة:", value="id + id * id $")
    if st.button("🗑 تصفير الذاكرة بالكامل"):
        st.session_state.clear()
        st.rerun()

st.markdown(f'<div class="welcome-card"><h2>🎓 مختبر المترجمات (LL1) - النسخة V7.1</h2><p>بإشراف د. حسنين | جامعة ميسان</p></div>', unsafe_allow_html=True)

# 5. التنفيذ المنطقي
raw_grammar = clean_grammar_input(g_raw)

if raw_grammar:
    fixed_g = remove_left_recursion(raw_grammar)
    f_s, fo_s = calculate_first_follow(fixed_g)
    
    # بناء جدول M-Table
    terms = sorted(list({s for ps in fixed_g.values() for p in ps for s in p if s not in fixed_g and s != 'ε'})) + ['$']
    m_table = pd.DataFrame("", index=fixed_g.keys(), columns=terms)
    for nt, prods in fixed_g.items():
        for p in prods:
            p_f = set()
            for s in p:
                s_f = f_s[s] if s in fixed_g else {s}; p_f.update(s_f - {'ε'})
                if 'ε' not in s_f: break
            else: p_f.add('ε')
            for a in p_f:
                if a != 'ε': m_table.at[nt, a] = f"{nt}->{' '.join(p)}"
            if 'ε' in p_f:
                for b in fo_s[nt]: m_table.at[nt, b] = f"{nt}->{' '.join(p)}"

    # عرض النتائج
    st.subheader("📋 القواعد المعالجة وجداول First/Follow")
    c1, c2 = st.columns([1, 2])
    with c1:
        st.write("**القواعد بعد إزالة التكرار:**")
        for nt, ps in fixed_g.items(): st.code(f"{nt} -> {' | '.join([' '.join(x) for x in ps])}")
    with c2:
        st.table(pd.DataFrame({"First": [str(f_s[n]) for n in fixed_g], "Follow": [str(fo_s[n]) for n in fixed_g]}, index=fixed_g.keys()))

    st.subheader("🔍 جدول Parsing Table (M-Table)")
    st.dataframe(m_table, use_container_width=True)

    # 6. المحاكاة ورسم الشجرة
    if st.button("🚀 تحليل الجملة ورسم الشجرة"):
        stack = [('$', '0'), (list(fixed_g.keys())[0], '0')]
        tokens = sentence.split()
        ptr, n_id = 0, 0
        trace, dot = [], Digraph()
        dot.node('0', list(fixed_g.keys())[0], style='filled', fillcolor='lightblue')
        
        while stack:
            top, pid = stack.pop()
            look = tokens[ptr] if ptr < len(tokens) else '$'
            action = ""
            
            if top == look:
                action = f"Match {look}"; ptr += 1
                if top == '$': st.session_state.engine['status'] = "Accepted"
            elif top in fixed_g:
                rule = m_table.at[top, look]
                if rule:
                    action = f"Apply {rule}"
                    rhs = rule.split('->')[1].split()
                    if rhs != ['ε'] and rhs != ['epsilon']:
                        for sym in reversed(rhs):
                            n_id += 1; nid = str(n_id)
                            dot.node(nid, sym); dot.edge(pid, nid)
                            stack.append((sym, nid))
                    else:
                        n_id += 1; nid = f"e{n_id}"; dot.node(nid, "ε", shape="none"); dot.edge(pid, nid)
                else: action = "Error"; st.session_state.engine['status'] = "Rejected"; break
            else: action = "Error"; st.session_state.engine['status'] = "Rejected"; break
            trace.append({"Stack": " ".join([x[0] for x in stack] + [top]), "Input": " ".join(tokens[ptr:]), "Action": action})

        st.session_state.engine.update({'trace': trace, 'dot': dot, 'done': True})

    if st.session_state.engine['done']:
        st.table(pd.DataFrame(st.session_state.engine['trace']))
        st.graphviz_chart(st.session_state.engine['dot'])
        st.info(f"النتيجة النهائية: {st.session_state.engine['status']}")

    # 7. التصدير المصلح (PDF Export Fix)
    if st.button("💾 تحميل التقرير الأكاديمي (PDF)"):
        try:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Helvetica", 'B', 16)
            pdf.cell(0, 10, "LL(1) Compiler Design Report", ln=True, align='C')
            pdf.set_font("Helvetica", size=10)
            pdf.ln(10)
            pdf.cell(0, 10, f"Grammar: {g_raw[:50]}...", ln=True)
            # إضافة الجداول والنتائج هنا...
            st.download_button("اضغط لتحميل ملف PDF", pdf.output(), "Report.pdf", "application/pdf")
        except Exception as e:
            st.error(f"حدث خطأ في المكتبة: {str(e)}")

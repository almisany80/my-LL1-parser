import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import io, os, tempfile
from fpdf import FPDF

# 1. إعدادات الواجهة والمحاذاة والتذييل
st.set_page_config(page_title="LL(1) Academic Studio V14.0", layout="wide")
st.markdown("""
    <style>
    .main, [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    .stTable td { white-space: pre !important; font-family: 'monospace'; text-align: center; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f8f9fa; 
              text-align: center; padding: 10px; font-weight: bold; border-top: 2px solid #007bff; color: #2c3e50; z-index: 999;}
    .conflict-cell { background-color: #f8d7da !important; color: #721c24 !important; font-weight: bold; }
    </style>
    <div class="footer">برمجة و تصميم : أ.م حسنين رحيم كريم @ 2026</div>
    """, unsafe_allow_html=True)

if 'engine' not in st.session_state:
    st.session_state.engine = {'trace': [], 'stack': [], 'done': False, 'dot': Digraph(), 'n_id': 0, 'status': ""}

# 2. فئة الـ PDF الأكاديمية المطورة
class CompilerPDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'B', 10)
        self.cell(0, 10, 'Programming & Design: Asst. Prof. Hassanain Raheem Kareem @ 2026', 0, 0, 'C')

    def safe_text(self, text):
        return str(text).replace('ε', 'epsilon').replace('→', '->')

    def add_section(self, title, df=None, grammar=None):
        self.add_page()
        self.set_font('Arial', 'B', 14)
        self.set_fill_color(230, 240, 255)
        self.cell(0, 10, title, 1, 1, 'C', fill=True)
        self.ln(5)
        if grammar:
            self.set_font('Courier', 'B', 11)
            for nt, prods in grammar.items():
                line = f"{nt} -> {' | '.join([' '.join(p) for p in prods])}"
                self.cell(0, 8, self.safe_text(line), 0, 1)
        if df is not None:
            self.set_font('Arial', '', 9)
            col_width = self.epw / len(df.columns)
            for col in df.columns: self.cell(col_width, 8, self.safe_text(col), 1, 0, 'C')
            self.ln()
            for row in df.values:
                for item in row: 
                    # تنظيف الخلايا التي تحتوي على تصادمات لملف الـ PDF
                    clean_item = str(item).replace('\n', ' || ')
                    self.cell(col_width, 8, self.safe_text(clean_item), 1, 0, 'C')
                self.ln()

# 3. محرك معالجة القواعد (المحلل الذكي)
def parse_grammar(raw_text):
    g = OrderedDict()
    for line in raw_text.strip().split('\n'):
        for arrow in ['->', '→', '=>']:
            if arrow in line:
                lhs, rhs = line.split(arrow, 1)
                g[lhs.strip()] = [p.strip().split() for p in rhs.split('|')]
                break
    return g

def get_common_prefix(p1, p2):
    i = 0
    while i < len(p1) and i < len(p2) and p1[i] == p2[i]: i += 1
    return p1[:i]

def auto_fix_grammar(g):
    # 1. إزالة الوراثة اليسارية (Left Recursion)
    no_lr_g = OrderedDict()
    for nt, prods in g.items():
        alpha = [p[1:] for p in prods if p and p[0] == nt]
        beta = [p for p in prods if not (p and p[0] == nt)]
        if alpha:
            nt_prime = f"{nt}'"
            no_lr_g[nt] = [b + [nt_prime] for b in (beta if beta else [['ε']])]
            no_lr_g[nt_prime] = [a + [nt_prime] for a in alpha] + [['ε']]
        else:
            no_lr_g[nt] = prods

    # 2. استخراج العامل المشترك (Left Factoring) - يحل مشكلة الصورة الأخيرة
    factored_g = OrderedDict()
    for nt, prods in no_lr_g.items():
        changed = True
        curr_prods = prods.copy()
        while changed:
            changed = False
            groups = {}
            for p in curr_prods:
                sym = p[0] if p and p != ['ε'] else 'ε'
                groups.setdefault(sym, []).append(p)
            
            new_curr = []
            for sym, grp in groups.items():
                if len(grp) > 1 and sym != 'ε':
                    prefix = grp[0]
                    for p in grp[1:]: prefix = get_common_prefix(prefix, p)
                    
                    if prefix:
                        changed = True
                        new_nt = f"{nt}'"
                        while new_nt in factored_g or new_nt in no_lr_g: new_nt += "'"
                        new_curr.append(prefix + [new_nt])
                        
                        rem_prods = []
                        for p in grp:
                            rem = p[len(prefix):]
                            rem_prods.append(rem if rem else ['ε'])
                        factored_g[new_nt] = rem_prods
                    else: new_curr.extend(grp)
                else: new_curr.extend(grp)
            curr_prods = new_curr
        factored_g[nt] = curr_prods
        
    # إعادة ترتيب القاموس ليكون المتغير الأصلي أولاً
    final_g = OrderedDict()
    for nt in no_lr_g.keys():
        if nt in factored_g: final_g[nt] = factored_g[nt]
        for k in factored_g.keys():
            if k.startswith(nt) and k != nt: final_g[k] = factored_g[k]
    return final_g

def compute_first_follow(g):
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
        for nt, prods in g.items():
            for p in prods: first[nt].update(get_f(p))
            
    follow = {nt: set() for nt in g}
    if g: follow[list(g.keys())[0]].add('$')
    
    for _ in range(10):
        for nt, prods in g.items():
            for p in prods:
                for i, B in enumerate(p):
                    if B in g:
                        f_next = get_f(p[i+1:])
                        follow[B].update(f_next - {'ε'})
                        if 'ε' in f_next: follow[B].update(follow[nt])
    return first, follow

# 4. بناء الواجهة
with st.sidebar:
    st.header("⚙️ لوحة التحكم")
    default_rules = "S -> i E t S | i E t S e S | a\nE -> b"
    raw_in = st.text_area("أدخل القواعد الأكاديمية:", default_rules, height=180)
    test_str = st.text_input("الجملة المختبرة:", "i b t a e a $")
    is_auto = st.checkbox("تفعيل الحل الأوتوماتيكي للتصادمات", value=True)
    if st.button("🔄 إعادة ضبط النظام"): 
        st.session_state.engine = {'trace': [], 'stack': [], 'done': False, 'dot': Digraph(), 'n_id': 0, 'status': ""}
        st.rerun()

st.title("🖥️ LL(1) Academic Studio - الإصدار الشامل")

orig_g = parse_grammar(raw_in)

if not orig_g:
    st.info("💡 بانتظار إدخال القواعد في الشريط الجانبي... تأكد من استخدام سهم (-> أو →)")
else:
    final_g = auto_fix_grammar(orig_g) if is_auto else orig_g
    
    # 1. عرض القواعد (المقارنة)
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📋 القواعد الأصلية")
        for k, v in orig_g.items(): st.code(f"{k} → {' | '.join([' '.join(p) for p in v])}")
    with c2:
        st.subheader("🛠 القواعد بعد المعالجة")
        for k, v in final_g.items(): st.code(f"{k} → {' | '.join([' '.join(p) for p in v])}")

    # 2. حساب First & Follow
    first_s, follow_s = compute_first_follow(final_g)
    st.subheader("🔍 مجموعات First & Follow")
    ff_df = pd.DataFrame({
        "First": [str(sorted(list(first_s[n]))) for n in final_g], 
        "Follow": [str(sorted(list(follow_s[n]))) for n in final_g]
    }, index=final_g.keys())
    st.table(ff_df)

    # 3. بناء جدول التنبؤ وكشف التصادمات
    terms = sorted(list({s for ps in final_g.values() for p in ps for s in p if s not in final_g and s != 'ε'})) + ['$']
    m_table = pd.DataFrame("", index=final_g.keys(), columns=terms)
    has_conflict = False
    
    for nt, prods in final_g.items():
        for p in prods:
            pf = set()
            if not p or p == ['ε']: pf = {'ε'}
            else:
                for s in p:
                    sf = first_s.get(s, {s})
                    pf.update(sf - {'ε'})
                    if 'ε' not in sf: break
                else: pf.add('ε')
            
            rule_str = f"{nt}->{' '.join(p)}"
            for a in pf:
                if a != 'ε':
                    old = m_table.at[nt, a]
                    if old and old != rule_str: has_conflict = True
                    m_table.at[nt, a] = (old + "\n" + rule_str) if old else rule_str
            if 'ε' in pf:
                for b in follow_s[nt]:
                    old = m_table.at[nt, b]
                    if old and old != rule_str: has_conflict = True
                    m_table.at[nt, b] = (old + "\n" + rule_str) if old else rule_str

    if has_conflict:
        st.error("⚠️ تحذير: تم اكتشاف تصادم في جدول التنبؤ (القواعد ليست LL1). الخلايا المتضاربة مميزة باللون الأحمر.")
    
    st.subheader("📊 جدول التنبؤ (Parsing Table)")
    st.dataframe(m_table.style.applymap(lambda x: 'background-color: #f8d7da; color: #721c24; font-weight: bold;' if '\n' in str(x) else ''), use_container_width=True)

    # 4. محرك التتبع التفاعلي (Trace Engine)
    st.divider()
    st.subheader("⏳ تتبع الجملة ورسم الشجرة")
    
    if has_conflict:
        st.warning("تم إيقاف المحاكاة بسبب وجود تصادم في الجدول يمنع التحليل الحتمي.")
    else:
        eng = st.session_state.engine
        if not eng['stack']:
            eng['stack'] = [('$', '0'), (list(final_g.keys())[0], '0')]
            eng['dot'] = Digraph()
            eng['dot'].node('0', list(final_g.keys())[0], style='filled', fillcolor='lightblue')

        def run_step():
            if eng['done'] or not eng['stack']: return
            tokens = test_str.split()
            matched = sum(1 for x in eng['trace'] if "Match" in x['Action'])
            lookahead = tokens[matched] if matched < len(tokens) else '$'
            top, pid = eng['stack'].pop()
            
            # مسافة صفرية لمنع مشاكل العرض في الجداول
            disp_input = "\u200B " + " ".join(tokens[matched:]) 
            step_record = {"Stack": " ".join([v for v, i in eng['stack']] + [top]), "Input": disp_input, "Action": ""}
            
            if top == lookahead:
                step_record["Action"] = f"Match {lookahead}"
                if top == '$': eng['done'], eng['status'] = True, "✅ Accepted"
            elif top in final_g:
                rule = m_table.at[top, lookahead]
                if rule:
                    step_record["Action"] = f"Apply {rule}"
                    rhs = rule.split('->')[1].split()
                    if rhs == ['ε']:
                        eng['n_id'] += 1; eid = f"e{eng['n_id']}"
                        eng['dot'].node(eid, "ε", shape='plaintext'); eng['dot'].edge(pid, eid)
                    else:
                        temp_nodes = []
                        for sym in rhs:
                            eng['n_id'] += 1; nid = str(eng['n_id'])
                            eng['dot'].node(nid, sym, style='filled', fillcolor='#d4edda'); eng['dot'].edge(pid, nid)
                            temp_nodes.append((sym, nid))
                        for item in reversed(temp_nodes): eng['stack'].append(item)
                else: eng['done'], eng['status'] = True, "❌ Rejected (No Rule)"
            else: eng['done'], eng['status'] = True, "❌ Rejected (Mismatch)"
            
            eng['trace'].append(step_record)

        col_b1, col_b2 = st.columns(2)
        if col_b1.button("⏭ خطوة واحدة (Step)"): run_step(); st.rerun()
        if col_b2.button("▶ تشغيل كامل (Run All)"):
            while not eng['done']: run_step()
            st.rerun()

        if eng['trace']:
            st.table(pd.DataFrame(eng['trace']))
            
            # عرض الشجرة
            st.subheader("🌲 شجرة الاشتقاق (Parse Tree)")
            st.graphviz_chart(eng['dot'])
            
            if eng['done']:
                box_color = "#d4edda" if "Accepted" in eng['status'] else "#f8d7da"
                text_color = "#155724" if "Accepted" in eng['status'] else "#721c24"
                st.markdown(f"<div style='background-color:{box_color}; color:{text_color}; padding:15px; border-radius:8px; text-align:center; font-weight:bold; font-size:18px;'>النتيجة: {eng['status']}</div>", unsafe_allow_html=True)

    # 5. التصدير (PDF & Excel)
    st.divider()
    st.subheader("📥 تصدير التقارير النهائية")
    exp1, exp2 = st.columns(2)
    
    with exp1:
        if st.button("📄 توليد وتحميل تقرير PDF"):
            pdf = CompilerPDF()
            pdf.add_section("1. Original Grammar", grammar=orig_g)
            pdf.add_section("2. Processed Grammar", grammar=final_g)
            pdf.add_section("3. First & Follow Sets", df=ff_df.reset_index())
            pdf.add_section("4. Parsing Table (M-Table)", df=m_table.reset_index())
            
            if not has_conflict and st.session_state.engine['trace']:
                pdf.add_section("5. Parsing Trace", df=pd.DataFrame(st.session_state.engine['trace']))
                # إضافة الشجرة
                try:
                    pdf.add_page()
                    pdf.set_font('Arial', 'B', 14)
                    pdf.cell(0, 10, "6. Parse Tree", 1, 1, 'C', fill=True)
                    img_data = st.session_state.engine['dot'].pipe(format='png')
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                        tmp.write(img_data); tmp_path = tmp.name
                    pdf.image(tmp_path, x=10, y=None, w=180)
                    os.unlink(tmp_path)
                except: pass
                
            st.download_button("📥 اضغط هنا لتحميل PDF", bytes(pdf.output()), "LL1_Final_Report.pdf", "application/pdf")

    with exp2:
        output_buffer = io.BytesIO()
        with pd.ExcelWriter(output_buffer, engine='xlsxwriter') as writer:
            ff_df.to_excel(writer, sheet_name='FF_Sets')
            m_table.to_excel(writer, sheet_name='M_Table')
            if not has_conflict and st.session_state.engine['trace']:
                pd.DataFrame(st.session_state.engine['trace']).to_excel(writer, sheet_name='Trace', index=False)
        st.download_button("📥 اضغط هنا لتحميل Excel", output_buffer.getvalue(), "Compiler_Data_Analysis.xlsx")

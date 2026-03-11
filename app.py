import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import io
import os
import re
from fpdf import FPDF

# 1. الإعدادات البصرية والهوية الأكاديمية
st.set_page_config(page_title="LL(1) Compiler Studio - University of Misan", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Tajawal', sans-serif; direction: RTL; text-align: right; }
    .header-box { background-color: #ffffff; padding: 20px; border-radius: 10px; border-bottom: 4px solid #1E3A8A; margin-bottom: 25px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .main-title { font-size: 26px; font-weight: bold; color: #1E3A8A; margin-bottom: 5px; }
    .sub-title { font-size: 19px; color: #4B5563; }
    
    /* فرض محاذاة اليسار (LTR) للقواعد والجداول بشكل صارم */
    div[data-testid="stTable"], div[data-testid="stDataFrame"], .stCodeBlock { 
        direction: ltr !important; 
    }
    div[data-testid="stTable"] th, div[data-testid="stTable"] td, 
    div[data-testid="stDataFrame"] th, div[data-testid="stDataFrame"] td {
        text-align: left !important;
        direction: ltr !important;
    }
    .stTable td { white-space: pre !important; font-family: 'monospace' !important; font-size: 15px; }
    
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

with h_col2:
    st.markdown("""
        <div class="header-box">
            <div class="main-title">جامعة ميسان</div>
            <div class="sub-title">كلية التربية - قسم علوم الحاسبات</div>
            <div class="sub-title" style="color: #10B981; font-weight: bold; margin-top: 5px;">مختبر المترجمات الذكي - LL(1) Parser Analyzer</div>
        </div>
        """, unsafe_allow_html=True)

# 3. فئة تقارير PDF المجهزة للحماية من أخطاء الخطوط
class AcademicPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.add_page()
        self.has_unicode = False
        font_path = "DejaVuSans.ttf"
        
        # التحقق من وجود خط يدعم اليونيكود
        if os.path.exists(font_path):
            try:
                self.add_font('DejaVu', '', font_path, uni=True)
                self.set_font('DejaVu', '', 12)
                self.has_unicode = True
            except:
                self.set_font("Arial", 'B', 14)
        else:
            self.set_font("Arial", 'B', 14)
            
        self.cell(0, 10, 'University of Misan - Compiler Design Report', 0, 1, 'C')
        self.ln(5)

    def safe_text(self, text):
        text = str(text).replace('→', '->')
        if not self.has_unicode:
            # حماية لمنع الخطأ إذا لم يكن خط اليونيكود متوفراً
            text = text.replace('ε', 'eps')
        return text

    def write_grammar(self, title, grammar_dict):
        self.set_font("Arial", 'B', 12) if not self.has_unicode else self.set_font('DejaVu', '', 12)
        self.cell(0, 10, title, 0, 1, 'L')
        self.set_font("Arial", '', 11) if not self.has_unicode else self.set_font('DejaVu', '', 11)
        for k, v in grammar_dict.items():
            rule = f"{k} -> {' | '.join([' '.join(p) for p in v])}"
            self.cell(0, 8, self.safe_text(rule), 0, 1, 'L')
        self.ln(5)

    def write_table(self, title, df):
        self.set_font("Arial", 'B', 12) if not self.has_unicode else self.set_font('DejaVu', '', 12)
        self.cell(0, 10, title, 1, 1, 'C')
        self.set_font("Arial", '', 10) if not self.has_unicode else self.set_font('DejaVu', '', 10)
        col_width = self.epw / len(df.columns)
        for col in df.columns: 
            self.cell(col_width, 8, self.safe_text(str(col)), 1, 0, 'C')
        self.ln()
        for row in df.values:
            for item in row:
                clean_item = str(item).replace('\n', ' || ')
                self.cell(col_width, 8, self.safe_text(clean_item), 1, 0, 'L')
            self.ln()
        self.ln(5)

# 4. محرك المعالجة
def smart_tokenize(rule_str):
    rule_str = rule_str.replace("→", "->").replace("=>", "->").replace("epsilon", "ε")
    rule_str = rule_str.replace("->", " -> ").replace("|", " | ")
    tokens = []
    for part in rule_str.split():
        if part in ['->', '|', 'ε', 'id']:
            tokens.append(part)
        else:
            matches = re.findall(r"id|ε|[A-Z][0-9]*|[a-z]|[^ \w]", part)
            tokens.extend(matches)
    return " ".join(tokens)

def parse_grammar(text):
    g = OrderedDict()
    for line in text.strip().split('\n'):
        clean_line = smart_tokenize(line)
        if '->' in clean_line:
            lhs, rhs = clean_line.split('->')
            g[lhs.strip()] = [p.strip().split() for p in rhs.split('|')]
    return g

def get_new_nt(base, existing_keys):
    i = 1
    while f"{base}{i}" in existing_keys: i += 1
    return f"{base}{i}"

def fix_left_recursion(g):
    new_g = OrderedDict()
    for nt, prods in g.items():
        rec = [p[1:] for p in prods if p and p[0] == nt]
        non_rec = [p for p in prods if not (p and p[0] == nt)]
        if rec:
            nt_new = get_new_nt(nt, list(new_g.keys()) + list(g.keys()))
            new_g[nt] = [p + [nt_new] for p in (non_rec if non_rec else [['ε']])]
            new_g[nt_new] = [p + [nt_new] for p in rec] + [['ε']]
        else: new_g[nt] = prods
    return new_g

def fix_left_factoring(g):
    final_g = OrderedDict()
    nts_to_process = list(g.keys())
    for nt in nts_to_process: final_g[nt] = g[nt].copy()
    while nts_to_process:
        nt = nts_to_process.pop(0)
        curr_prods = final_g[nt]
        max_len = 0
        longest_prefix = []
        for i in range(len(curr_prods)):
            for j in range(i + 1, len(curr_prods)):
                p1, p2 = curr_prods[i], curr_prods[j]
                if not p1 or not p2 or p1 == ['ε'] or p2 == ['ε']: continue
                k = 0
                while k < len(p1) and k < len(p2) and p1[k] == p2[k]: k += 1
                if k > max_len:
                    max_len = k; longest_prefix = p1[:k]
        if max_len > 0:
            factored, remaining = [], []
            for p in curr_prods:
                if p[:max_len] == longest_prefix:
                    rem = p[max_len:]
                    factored.append(rem if rem else ['ε'])
                else: remaining.append(p)
            new_nt = get_new_nt(nt, list(final_g.keys()))
            remaining.append(longest_prefix + [new_nt])
            final_g[nt] = remaining
            final_g[new_nt] = factored
            nts_to_process.insert(0, nt); nts_to_process.insert(1, new_nt)
    return final_g

def compute_sets(grammar):
    first = {nt: set() for nt in grammar}
    def get_f(seq):
        res = set()
        if not seq or seq == ['ε']: return {'ε'}
        for s in seq:
            sf = first[s] if s in grammar else {s}; res.update(sf - {'ε'})
            if 'ε' not in sf: break
        else: res.add('ε')
        return res
    for _ in range(15):
        for nt, prods in grammar.items():
            for p in prods: first[nt].update(get_f(p))
    follow = {nt: set() for nt in grammar}
    if grammar: follow[list(grammar.keys())[0]].add('$')
    for _ in range(15):
        for nt, prods in grammar.items():
            for p in prods:
                for i, B in enumerate(p):
                    if B in grammar:
                        beta = p[i+1:]
                        if beta:
                            fb = get_f(beta); follow[B].update(fb - {'ε'})
                            if 'ε' in fb: follow[B].update(follow[nt])
                        else: follow[B].update(follow[nt])
    return first, follow

# 5. الذاكرة (معالجة شجرة الإعراب للحفظ الدائم)
if 'st' not in st.session_state:
    st.session_state.st = {
        'trace': [], 'stack': [], 'done': False, 'id': 0, 'status': "",
        'tree_nodes': [], 'tree_edges': [] # تخزين العقد والروابط خام لتجنب ضياعها
    }

# 6. لوحة التحكم الجانبية
with st.sidebar:
    st.header("⚙️ لوحة الإعدادات")
    grammar_txt = st.text_area("أدخل القواعد (يسمح بالتلاصق مثل aABC):", "A -> a | a b\nB -> c | c d", height=150)
    test_input = st.text_input("الجملة المختبرة:", "a b $")
    if st.button("🔄 تصفير الذاكرة"):
        st.session_state.st = {'trace': [], 'stack': [], 'done': False, 'id': 0, 'status': "", 'tree_nodes': [], 'tree_edges': []}
        st.rerun()

# 7. التنفيذ
try:
    orig_g = parse_grammar(grammar_txt)
    if not orig_g:
        st.info("💡 بانتظار إدخال قواعد صحيحة...")
    else:
        processed_g = fix_left_factoring(fix_left_recursion(orig_g))
        f_set, l_set = compute_sets(processed_g)
        
        is_ll1 = True
        terms = sorted(list({s for ps in processed_g.values() for p in ps for s in p if s not in processed_g and s != 'ε'})) + ['$']
        m_table = pd.DataFrame("", index=processed_g.keys(), columns=terms)
        
        for nt, ps in processed_g.items():
            for p in ps:
                pf = set()
                for s in p:
                    sf = f_set[s] if s in processed_g else {s}; pf.update(sf - {'ε'})
                    if 'ε' not in sf: break
                else: pf.add('ε')
                
                rule_str = f"{nt} -> {' '.join(p)}"
                for a in pf:
                    if a != 'ε':
                        if m_table.at[nt, a] and rule_str not in m_table.at[nt, a]:
                            m_table.at[nt, a] += f"\n{rule_str}"; is_ll1 = False
                        else: m_table.at[nt, a] = rule_str
                if 'ε' in pf:
                    for b in l_set[nt]:
                        if m_table.at[nt, b] and rule_str not in m_table.at[nt, b]:
                            m_table.at[nt, b] += f"\n{rule_str}"; is_ll1 = False
                        else: m_table.at[nt, b] = rule_str

        if not is_ll1:
            st.error("⚠️ تحذير: هذه القواعد ليست LL(1)! يوجد تصادم (Conflict).")
        else:
            st.success("✅ القواعد مطابقة لشروط LL(1).")

        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("📋 القواعد الأصلية")
            for k, v in orig_g.items(): st.code(f"{k} → {' | '.join([' '.join(p) for p in v])}")
        with c2:
            st.subheader("🛠 القواعد المعالجة (Factored & Non-Recursive)")
            for k, v in processed_g.items(): st.code(f"{k} → {' | '.join([' '.join(p) for p in v])}")

        st.subheader("🔍 مجموعات First & Follow")
        ff_df = pd.DataFrame({
            "First": ["{ " + ", ".join(sorted(list(f_set[n]))) + " }" for n in processed_g], 
            "Follow": ["{ " + ", ".join(sorted(list(l_set[n]))) + " }" for n in processed_g]
        }, index=processed_g.keys())
        st.table(ff_df)

        st.subheader("📊 جدول التنبؤ (Parsing Table)")
        def highlight_conflicts(val): return 'background-color: #f8d7da; color: #721c24; font-weight: bold;' if '\n' in str(val) else ''
        st.dataframe(m_table.style.applymap(highlight_conflicts), use_container_width=True)

        st.divider()
        st.subheader("⏳ التتبع الحي للجملة (Parsing Trace)")
        s = st.session_state.st
        
        # تهيئة الجذر في الشجرة إذا كانت فارغة
        if not s['stack']:
            root_nt = list(processed_g.keys())[0]
            s['stack'] = [('$', '0'), (root_nt, '0')]
            s['tree_nodes'] = [('0', root_nt, False)]

        def run_step():
            if s['done'] or not s['stack']: return
            tokens = test_input.split(); matched = sum(1 for x in s['trace'] if "Match" in x['Action'])
            lookahead = tokens[matched] if matched < len(tokens) else '$'
            top, pid = s['stack'].pop()
            
            # ضمان ترتيب الأعمدة من اليسار إلى اليمين
            row = OrderedDict()
            row["Stack"] = " ".join([v for v, i in s['stack']] + [top])
            row["Input"] = " ".join(tokens[matched:])
            row["Action"] = ""
            
            if top == lookahead:
                row["Action"] = f"Match {lookahead}"
                if top == '$': s['done'], s['status'] = True, "✅ الجملة مقبولة (Accepted)"
            elif top in processed_g:
                rule = m_table.at[top, lookahead]
                if '\n' in rule:
                    row["Action"] = f"Conflict: {rule.replace(chr(10), ' OR ')}"
                    s['done'], s['status'] = True, "❌ مرفوضة (تصادم في الجدول يمنع الاستمرار)"
                elif rule:
                    row["Action"] = f"Apply {rule}"; rhs = rule.split('->')[1].split()
                    if rhs == ['ε']:
                        s['id'] += 1; eid = f"e{s['id']}"
                        s['tree_nodes'].append((eid, "ε", True))
                        s['tree_edges'].append((pid, eid))
                    else:
                        nodes = []
                        for sym in rhs:
                            s['id'] += 1; nid = str(s['id'])
                            is_term = sym not in processed_g
                            s['tree_nodes'].append((nid, sym, is_term))
                            s['tree_edges'].append((pid, nid))
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

        # إعادة بناء كائن Graphviz من البيانات الخام في كل تحديث للصفحة
        current_dot = Digraph()
        for nid, lbl, is_term in s['tree_nodes']:
            color = '#ffffff' if lbl == 'ε' else ('#D1FAE5' if is_term else '#DBEAFE')
            shape = 'plaintext' if lbl == 'ε' else 'ellipse'
            style = '' if lbl == 'ε' else 'filled'
            current_dot.node(nid, lbl, style=style, fillcolor=color, shape=shape)
        for src, dst in s['tree_edges']: current_dot.edge(src, dst)

        if s['trace']:
            # عرض جدول التتبع
            st.table(pd.DataFrame(s['trace']))
            st.subheader("🌲 شجرة الاشتقاق (Parse Tree)")
            st.graphviz_chart(current_dot)
            if s['done']:
                cls = "accepted" if "✅" in s['status'] else "rejected"
                st.markdown(f'<div class="status-box {cls}">{s["status"]}</div>', unsafe_allow_html=True)

        st.divider()
        st.subheader("📥 تصدير التقارير النهائية")
        ex1, ex2 = st.columns(2)
        with ex1:
            if st.button("📄 تصدير تقرير PDF"):
                try:
                    pdf = AcademicPDF()
                    pdf.write_grammar("1. Original Grammar:", orig_g)
                    pdf.write_grammar("2. Processed Grammar (Factored & Non-Recursive):", processed_g)
                    pdf.write_table("3. First & Follow Sets", ff_df.reset_index().rename(columns={'index': 'NT'}))
                    pdf.write_table("4. Parsing Table", m_table.reset_index().rename(columns={'index': 'NT'}))
                    
                    if s['trace']: 
                        pdf.write_table("5. Parsing Trace", pd.DataFrame(s['trace']))
                        # إضافة الشجرة المكتملة إلى الـ PDF
                        try:
                            current_dot.render('parse_tree', format='png', cleanup=True)
                            pdf.add_page()
                            pdf.set_font("Arial", 'B', 12) if not pdf.has_unicode else pdf.set_font('DejaVu', '', 12)
                            pdf.cell(0, 10, '6. Parse Tree:', 0, 1, 'C')
                            pdf.image('parse_tree.png', x=10, w=190)
                        except Exception as img_err:
                            pdf.cell(0, 10, '(Could not render tree image)', 0, 1, 'C')

                    st.download_button("📥 تحميل PDF", bytes(pdf.output()), "LL1_Report.pdf", "application/pdf")
                except Exception as e:
                    st.error(f"خطأ أثناء توليد الـ PDF: {e}")
        with ex2:
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
                ff_df.to_excel(wr, sheet_name='Sets')
                m_table.to_excel(wr, sheet_name='Table')
                if s['trace']: pd.DataFrame(s['trace']).to_excel(wr, sheet_name='Trace')
            st.download_button("📥 تحميل Excel", buf.getvalue(), "Compiler_Data.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

except Exception as e:
    st.error(f"حدث خطأ: {e}\nيرجى التأكد من كتابة القواعد بصيغة صحيحة.")

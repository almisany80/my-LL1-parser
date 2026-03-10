import streamlit as st
import pandas as pd
import re
from collections import OrderedDict
from graphviz import Digraph
import io, os, tempfile
from fpdf import FPDF

# 1. إعدادات الواجهة
st.set_page_config(page_title="LL(1) Compiler Studio V9.0", layout="wide")
st.markdown("""
    <style>
    .main { direction: RTL; text-align: right; }
    [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    textarea, input[type="text"] { direction: LTR !important; text-align: left !important; font-family: 'monospace'; font-size: 16px; }
    .stTable td { white-space: pre !important; font-family: 'monospace' !important; color: #1e1e1e; }
    .conflict-cell { background-color: #ffcccc !important; color: #cc0000 !important; font-weight: bold; }
    .status-box { padding: 15px; border-radius: 8px; text-align: center; font-weight: bold; margin: 10px 0; }
    .accepted { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
    .rejected { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
    </style>
    """, unsafe_allow_html=True)

# 2. تهيئة الذاكرة
if 'done' not in st.session_state:
    st.session_state.update({'done': False, 'status': "", 'step': 0, 'stack': [], 'trace': [], 'dot': Digraph(), 'n_id': 0})

# 3. فئة PDF الأكاديمية
class AcademicPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.font_to_use = "Arial"

    def header(self):
        self.set_font(self.font_to_use, 'B', 12)
        self.cell(0, 8, 'University of Misan - College of Education for Pure Sciences', 0, 1, 'C')
        self.set_font(self.font_to_use, '', 10)
        self.cell(0, 6, 'Computer Science Department | LL(1) Parsing Report', 0, 1, 'C')
        self.cell(0, 6, 'Prepared by: Asst. Prof. Hassanain Raheem Kareem', 0, 1, 'C')
        self.ln(5)

    def write_section(self, title, content=None, df=None, grammar=None, conflicts=None):
        self.set_font(self.font_to_use, 'B', 11)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 10, title, 1, 1, 'L', fill=True)
        self.ln(2)
        self.set_font(self.font_to_use, '', 10)
        
        if content: self.multi_cell(0, 8, content)
        if conflicts:
            for c in conflicts: self.cell(0, 7, c, 0, 1)
        if grammar:
            for k, v in grammar.items():
                line = f"{k} -> {' | '.join([' '.join(p) for p in v])}"
                self.cell(0, 7, line, 0, 1)
                
        if df is not None:
            col_width = self.epw / len(df.columns)
            for col in df.columns: self.cell(col_width, 8, str(col), 1, 0, 'C')
            self.ln()
            for row in df.values:
                # إزالة أسطر التصادم المزدوجة لتبدو جيدة في PDF
                for item in row: self.cell(col_width, 8, str(item).replace('\n', ' || '), 1, 0, 'C')
                self.ln()
        self.ln(5)

    def add_tree_image(self, dot_graph):
        self.add_page()
        self.set_font(self.font_to_use, 'B', 11)
        self.cell(0, 10, "Final Parsing Tree", 1, 1, 'L', fill=True)
        self.ln(5)
        try:
            img_data = dot_graph.pipe(format='png')
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                tmp.write(img_data)
                tmp_path = tmp.name
            self.image(tmp_path, x=10, y=None, w=180)
            os.unlink(tmp_path)
        except:
            self.cell(0, 10, "(Tree could not be rendered in PDF)", 0, 1)

# 4. معالجة القواعد (Tokenizer & Algorithms)
def smart_tokenize(rule_str):
    rule_str = rule_str.replace("→", "->").replace("=>", "->").replace("ε", "epsilon")
    rule_str = rule_str.replace("->", " -> ").replace("|", " | ")
    tokens = []
    for part in rule_str.split():
        if part in ['->', '|', 'epsilon', 'id']: tokens.append(part)
        else:
            matches = re.findall(r"id|epsilon|[A-Z]''|[A-Z]'|[A-Z]|[a-z]|[^ \w]", part)
            tokens.extend(matches)
    return " ".join(tokens).replace("epsilon", "ε")

def remove_left_recursion(grammar):
    # إزالة التكرار غير المباشر والمباشر (Indirect & Direct)
    nts = list(grammar.keys())
    new_g = OrderedDict()
    for nt in grammar: new_g[nt] = [list(p) for p in grammar[nt]]
    
    for i in range(len(nts)):
        ai = nts[i]
        for j in range(i):
            aj = nts[j]
            updated_prods = []
            for prod in new_g[ai]:
                if prod and prod[0] == aj:
                    for aj_prod in new_g[aj]: updated_prods.append(aj_prod + prod[1:])
                else: updated_prods.append(prod)
            new_g[ai] = updated_prods
            
        alphas = [p[1:] for p in new_g[ai] if p and p[0] == ai]
        betas = [p for p in new_g[ai] if not (p and p[0] == ai)]
        
        if alphas:
            new_nt = f"{ai}'"
            if not betas: betas = [['ε']]
            final_betas = []
            for b in betas:
                if b == ['ε']: final_betas.append([new_nt])
                else: final_betas.append(b + [new_nt])
            new_g[ai] = final_betas
            new_g[new_nt] = [a + [new_nt] for a in alphas] + [['ε']]
            
    return new_g

def apply_left_factoring(grammar):
    new_g = OrderedDict()
    for nt, prods in grammar.items():
        grouped = OrderedDict()
        for p in prods:
            first_sym = p[0] if p else "ε"
            if first_sym not in grouped: grouped[first_sym] = []
            grouped[first_sym].append(p)
            
        for first_sym, group in grouped.items():
            if len(group) > 1 and first_sym != "ε":
                new_nt = f"{nt}''"
                if nt not in new_g: new_g[nt] = []
                new_g[nt].append([first_sym, new_nt])
                if new_nt not in new_g: new_g[new_nt] = []
                for p in group:
                    remainder = p[1:] if len(p) > 1 else ['ε']
                    new_g[new_nt].append(remainder)
            else:
                if nt not in new_g: new_g[nt] = []
                new_g[nt].extend(group)
    return new_g

def get_seq_first(seq, first_dict):
    res = set()
    if not seq or seq == ['ε']: return {'ε'}
    for s in seq:
        sf = first_dict.get(s, {s})
        res.update(sf - {'ε'})
        if 'ε' not in sf: break
    else: res.add('ε')
    return res

def calculate_sets(grammar):
    first = {nt: set() for nt in grammar}
    for _ in range(10):
        for nt, prods in grammar.items():
            for p in prods: first[nt].update(get_seq_first(p, first))
            
    follow = {nt: set() for nt in grammar}; follow[list(grammar.keys())[0]].add('$')
    for _ in range(10):
        for nt, prods in grammar.items():
            for p in prods:
                for i, B in enumerate(p):
                    if B in grammar:
                        beta = p[i+1:]
                        if beta:
                            fb = get_seq_first(beta, first)
                            follow[B].update(fb - {'ε'})
                            if 'ε' in fb: follow[B].update(follow[nt])
                        else: follow[B].update(follow[nt])
    return first, follow

def check_ll1_conditions(grammar, first_s, follow_s):
    conflicts = []
    is_ll1 = True
    for nt, prods in grammar.items():
        for i in range(len(prods)):
            for j in range(i+1, len(prods)):
                alpha, beta = prods[i], prods[j]
                f_alpha = get_seq_first(alpha, first_s)
                f_beta = get_seq_first(beta, first_s)
                
                # Condition 1: FIRST/FIRST
                intersect1 = (f_alpha - {'ε'}) & (f_beta - {'ε'})
                if intersect1:
                    conflicts.append(f"🔴 FIRST/FIRST Conflict in {nt} on symbols {intersect1}")
                    is_ll1 = False
                
                # Condition 2: FIRST/FOLLOW
                if 'ε' in f_alpha:
                    intersect2 = (f_beta - {'ε'}) & follow_s[nt]
                    if intersect2:
                        conflicts.append(f"🔴 FIRST/FOLLOW Conflict in {nt} on symbols {intersect2}")
                        is_ll1 = False
                if 'ε' in f_beta:
                    intersect3 = (f_alpha - {'ε'}) & follow_s[nt]
                    if intersect3:
                        conflicts.append(f"🔴 FIRST/FOLLOW Conflict in {nt} on symbols {intersect3}")
                        is_ll1 = False
    return is_ll1, conflicts

# 5. الواجهة الجانبية
with st.sidebar:
    st.header("⚙️ لوحة التحكم")
    default_rules = "S → aABC\nA → a | ab\nB → a | ε\nC → b | ε"
    raw_input = st.text_area("أدخل القواعد:", value=default_rules, height=180)
    test_sentence = st.text_input("الجملة المختبرة:", "a a a b $")
    if st.button("🗑 مسح الجلسة وإعادة الضبط"):
        st.session_state.clear(); st.rerun()

st.title("🖥️ LL(1) Compiler Studio")

original_grammar = OrderedDict()
grammar = OrderedDict()

for line in raw_input.strip().split('\n'):
    clean_line = smart_tokenize(line)
    if '->' in clean_line:
        lhs, rhs = clean_line.split('->')
        grammar[lhs.strip()] = [p.strip().split() for p in rhs.split('|')]
        original_grammar[lhs.strip()] = [p.strip().split() for p in rhs.split('|')]

if grammar:
    # تطبيق الخوارزميات
    g_no_rec = remove_left_recursion(grammar)
    fixed_g = apply_left_factoring(g_no_rec)
    first_s, follow_s = calculate_sets(fixed_g)
    is_ll1, conflict_list = check_ll1_conditions(fixed_g, first_s, follow_s)
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📝 القواعد الأصلية")
        for k, v in original_grammar.items(): st.code(f"{k} → {' | '.join([' '.join(p) for p in v])}")
    with col2:
        st.subheader("📋 القواعد بعد المعالجة")
        for k, v in fixed_g.items(): st.code(f"{k} → {' | '.join([' '.join(p) for p in v])}")

    # التحقق من شروط LL(1)
    if not is_ll1:
        st.error("⚠️ القواعد المدخلة لا تعتبر LL(1) بسبب التصادمات التالية:")
        for c in conflict_list: st.write(c)
    else:
        st.success("✅ القواعد متوافقة مع شروط LL(1) (لا يوجد تصادم)")

    st.subheader("🔍 مجموعات First & Follow")
    ff_df = pd.DataFrame({"First": [str(first_s[n]) for n in fixed_g], "Follow": [str(follow_s[n]) for n in fixed_g]}, index=fixed_g.keys())
    st.table(ff_df)

    # بناء M-Table مع كشف التصادمات داخل الجدول
    terms = sorted(list({s for ps in fixed_g.values() for p in ps for s in p if s not in fixed_g and s != 'ε'})) + ['$']
    m_table = pd.DataFrame("", index=fixed_g.keys(), columns=terms)
    
    for nt, prods in fixed_g.items():
        for p in prods:
            pf = get_seq_first(p, first_s)
            for a in pf:
                if a != 'ε':
                    rule_str = f"{nt}->{' '.join(p)}"
                    m_table.at[nt, a] = m_table.at[nt, a] + f"\n{rule_str}" if m_table.at[nt, a] else rule_str
            if 'ε' in pf:
                for b in follow_s[nt]:
                    rule_str = f"{nt}->{' '.join(p)}"
                    m_table.at[nt, b] = m_table.at[nt, b] + f"\n{rule_str}" if m_table.at[nt, b] else rule_str

    # تلوين الخلايا التي تحتوي تصادم
    def highlight_conflicts(val):
        return 'background-color: #ffcccc; color: #cc0000; font-weight: bold' if '\n' in str(val) else ''

    st.subheader("📊 جدول التنبؤ (Parsing Table)")
    st.dataframe(m_table.style.applymap(highlight_conflicts), use_container_width=True)

    st.divider()
    st.subheader("⏳ تتبع الجملة ورسم الشجرة")
    
    if not is_ll1:
        st.warning("تم تعطيل محاكي التتبع لأن القواعد تحتوي على تصادم (Not LL(1)). يرجى تعديل القواعد أولاً.")
    else:
        if not st.session_state.stack:
            st.session_state.stack = [('$', '0'), (list(fixed_g.keys())[0], '0')]
            st.session_state.dot = Digraph()
            st.session_state.dot.node('0', list(fixed_g.keys())[0], style='filled', fillcolor='lightblue')

        def step_sim():
            s = st.session_state
            if s.done or not s.stack: return
            tokens = test_sentence.split()
            match_count = sum(1 for x in s.trace if "Match" in x['Action'])
            look = tokens[match_count] if match_count < len(tokens) else '$'
            top, pid = s.stack.pop()
            
            display_input = "\u200B " + " ".join(tokens[match_count:])
            step_rec = {"Stack": " ".join([v for v, i in s.stack] + [top]), "Input": display_input, "Action": ""}
            
            if top == look:
                step_rec["Action"] = f"Match {look}"
                if top == '$': s.done, s.status = True, "Accepted"
            elif top in fixed_g:
                rule = m_table.at[top, look]
                if rule and '\n' not in rule: # تأكيد إضافي لتجنب خلايا التصادم
                    step_rec["Action"] = f"Apply {rule}"
                    rhs = rule.split('->')[1].split()
                    if rhs == ['ε']:
                        nid = f"e_{pid}_{s.n_id}"
                        s.dot.node(nid, "ε", shape='plaintext'); s.dot.edge(pid, nid)
                    else:
                        tmp = []
                        for sym in rhs:
                            s.n_id += 1; nid = str(s.n_id)
                            s.dot.node(nid, sym, style='filled', fillcolor='lightgreen'); s.dot.edge(pid, nid)
                            tmp.append((sym, nid))
                        for item in reversed(tmp): s.stack.append(item)
                else:
                    step_rec["Action"] = "❌ Error"; s.done, s.status = True, "Rejected"
            else:
                step_rec["Action"] = "❌ Error"; s.done, s.status = True, "Rejected"
            s.trace.append(step_rec)

        btn_col1, btn_col2 = st.columns(2)
        if btn_col1.button("⏭ خطوة تالية"): step_sim()
        if btn_col2.button("▶ تشغيل كامل"):
            while not st.session_state.done: step_sim()

        if st.session_state.trace:
            st.table(pd.DataFrame(st.session_state.trace))
            st.graphviz_chart(st.session_state.dot)
            if st.session_state.done:
                css_class = "accepted" if st.session_state.status == "Accepted" else "rejected"
                st.markdown(f'<div class="status-box {css_class}">{st.session_state.status}</div>', unsafe_allow_html=True)

    # التصدير النهائي
    st.divider()
    st.subheader("📥 تصدير التقارير النهائية")
    exp_col1, exp_col2 = st.columns(2)
    
    with exp_col1:
        if st.button("📄 تصدير تقرير PDF شامل"):
            try:
                pdf = AcademicPDF()
                pdf.add_page()
                pdf.write_section("1. Original Grammar", grammar=original_grammar)
                pdf.write_section("2. Processed Grammar", grammar=fixed_g)
                pdf.write_section("3. LL(1) Verification", conflicts=conflict_list if conflict_list else ["Grammar is strictly LL(1). No conflicts found."])
                pdf.write_section("4. First & Follow Sets", df=ff_df.reset_index())
                pdf.write_section("5. Parsing Table (M-Table)", df=m_table.reset_index())
                
                if st.session_state.trace:
                    pdf.add_page()
                    pdf.write_section("6. Parsing Trace", df=pd.DataFrame(st.session_state.trace))
                    pdf.add_tree_image(st.session_state.dot)
                
                st.download_button("📥 تحميل PDF", bytes(pdf.output()), "LL1_Full_Report.pdf", "application/pdf")
            except Exception as e:
                st.error(f"خطأ تقني في PDF: {str(e)}")

    with exp_col2:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            ff_df.to_excel(writer, sheet_name='FF_Sets')
            m_table.to_excel(writer, sheet_name='M_Table')
            if st.session_state.trace: pd.DataFrame(st.session_state.trace).to_excel(writer, sheet_name='Trace', index=False)
        st.download_button("📥 تحميل ملف Excel", buf.getvalue(), "LL1_Data.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

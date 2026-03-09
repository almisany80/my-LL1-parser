import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import io
import os
from fpdf import FPDF

# 1. التنسيق الأكاديمي (RTL & Styling)
st.set_page_config(page_title="LL(1) Compiler Studio Pro", layout="wide")
st.markdown("""
    <style>
    .main { direction: RTL; text-align: right; }
    [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    .ltr-table { direction: LTR !important; text-align: left !important; font-family: 'Consolas', monospace; }
    .status-accepted { background-color: #2e7d32; color: white; padding: 15px; border-radius: 8px; text-align: center; font-weight: bold; }
    .status-rejected { background-color: #c62828; color: white; padding: 15px; border-radius: 8px; text-align: center; font-weight: bold; }
    .conflict-msg { background-color: #ffebee; color: #b71c1c; padding: 15px; border-left: 5px solid #b71c1c; margin: 10px 0; font-weight: bold; border-radius: 5px; }
    .grammar-box { background-color: #f8f9fa; padding: 10px; border-radius: 5px; border-right: 5px solid #d32f2f; margin: 10px 0; font-family: monospace; }
    </style>
    """, unsafe_allow_html=True)

# 2. المعالجة الآلية للقواعد (Factoring & Left Recursion)
def remove_left_recursion(grammar):
    new_grammar = OrderedDict()
    for nt, prods in grammar.items():
        recursive = [p[1:] for p in prods if p and p[0] == nt]
        non_recursive = [p for p in prods if not (p and p[0] == nt)]
        if recursive:
            new_nt = f"{nt}'"
            new_grammar[nt] = [p + [new_nt] for p in non_recursive] if non_recursive else [[new_nt]]
            new_grammar[new_nt] = [p + [new_nt] for p in recursive] + [['ε']]
        else: new_grammar[nt] = prods
    return new_grammar

def apply_left_factoring(grammar):
    new_grammar = OrderedDict()
    for nt, prods in grammar.items():
        if len(prods) <= 1:
            new_grammar[nt] = prods
            continue
        prods.sort()
        prefix = os.path.commonprefix([tuple(p) for p in prods])
        if prefix:
            new_nt = f"{nt}f"
            new_grammar[nt] = [list(prefix) + [new_nt]]
            suffix = [p[len(prefix):] if p[len(prefix):] else ['ε'] for p in prods]
            new_grammar[new_nt] = suffix
        else: new_grammar[nt] = prods
    return new_grammar

# 3. الدوال الحسابية وتلوين التضارب
def get_first_follow_stable(grammar):
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

    follow = {nt: set() for nt in grammar}
    follow[list(grammar.keys())[0]].add('$')
    while True:
        changed = False
        for nt, prods in grammar.items():
            for p in prods:
                for i, B in enumerate(p):
                    if B in grammar:
                        old_len = len(follow[B])
                        beta = p[i+1:]
                        if beta:
                            fb = get_seq_first(beta)
                            follow[B].update(fb - {'ε'})
                            if 'ε' in fb: follow[B].update(follow[nt])
                        else: follow[B].update(follow[nt])
                        if len(follow[B]) > old_len: changed = True
        if not changed: break
    return first, follow

def highlight_conflicts(val):
    if "|" in str(val): return 'background-color: #ffcdd2; color: #b71c1c; font-weight: bold'
    return ''

# 4. محرك التقارير PDF
class AcademicPDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, "LL(1) Compiler Analysis Report", ln=True, align="C")
        self.ln(5)
    def add_section(self, title, df=None, grammar=None):
        self.set_font("Arial", "B", 11)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 10, f" {title}", ln=True, fill=True)
        self.ln(2)
        if grammar:
            self.set_font("Courier", "", 10)
            for k, v in grammar.items():
                self.cell(0, 8, f"{k} -> {' | '.join([' '.join(p) for p in v])}", ln=True)
        elif df is not None:
            self.set_font("Arial", "", 9)
            cols = list(df.columns); cw = self.epw / (len(cols) + 1)
            self.cell(cw, 8, "Key", 1, 0, 'C', True)
            for c in cols: self.cell(cw, 8, str(c), 1, 0, 'C', True)
            self.ln()
            for i, r in df.iterrows():
                self.cell(cw, 7, str(i), 1, 0, 'C')
                for v in r: self.cell(cw, 7, str(v)[:20], 1, 0, 'L')
                self.ln()
        self.ln(5)

# 5. إدارة الحالة (Session State) لمنع الشاشة البيضاء
if 'sim' not in st.session_state:
    st.session_state.sim = {'trace': [], 'dot': None, 'status': None, 'stack': [], 'idx': 0, 'node_id': 0, 'finished': False, 'tokens': []}
if 'last_grammar' not in st.session_state: st.session_state.last_grammar = ""

# 6. الواجهة وتلقي المدخلات
with st.sidebar:
    st.header("⚙️ المدخلات")
    raw_in = st.text_area("أدخل القواعد:", "S -> i e T S S' | a\nS' -> e S | ε\nT -> b", height=150)
    
    if raw_in != st.session_state.last_grammar:
        st.session_state.sim = {'trace': [], 'dot': None, 'status': None, 'stack': [], 'idx': 0, 'node_id': 0, 'finished': False, 'tokens': []}
        st.session_state.last_grammar = raw_in

    u_input = st.text_input("الجملة المراد تتبعها:", "i e b a $")
    if st.button("🔄 مسح الذاكرة وإعادة الضبط"):
        st.session_state.sim = {'trace': [], 'dot': None, 'status': None, 'stack': [], 'idx': 0, 'node_id': 0, 'finished': False, 'tokens': []}
        st.rerun()

grammar_raw = OrderedDict()
for line in raw_in.split('\n'):
    if '->' in line:
        lhs, rhs = line.split('->')
        grammar_raw[lhs.strip()] = [opt.strip().split() for opt in rhs.split('|')]

if grammar_raw:
    # المعالجة الآلية للقواعد
    fixed_g = apply_left_factoring(remove_left_recursion(grammar_raw))
    
    st.header("1️⃣ مراجعة القواعد")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("القواعد الأصلية")
        for k, v in grammar_raw.items(): st.markdown(f'<div class="grammar-box ltr-table">{k} → {" | ".join([" ".join(p) for p in v])}</div>', unsafe_allow_html=True)
    with c2:
        st.subheader("القواعد المعالجة")
        for k, v in fixed_g.items(): st.markdown(f'<div class="grammar-box ltr-table" style="border-right-color:#2e7d32">{k} → {" | ".join([" ".join(p) for p in v])}</div>', unsafe_allow_html=True)

    # حساب First & Follow
    f_sets, fo_sets = get_first_follow_stable(fixed_g)
    st.header("2️⃣ جداول First & Follow")
    ff_df = pd.DataFrame({
        "First": [", ".join(sorted(list(s))) for s in f_sets.values()],
        "Follow": [", ".join(sorted(list(s))) for s in fo_sets.values()]
    }, index=f_sets.keys())
    st.table(ff_df)

    # بناء M-Table واكتشاف التضارب
    terms = sorted(list({s for ps in fixed_g.values() for p in ps for s in p if s not in fixed_g and s != 'ε'})) + ['$']
    m_data = {nt: {t: [] for t in terms} for nt in fixed_g}
    is_ll1 = True

    for nt, prods in fixed_g.items():
        for p in prods:
            p_first = set()
            for s in p:
                sf = f_sets[s] if s in fixed_g else {s}
                p_first.update(sf - {'ε'})
                if 'ε' not in sf: break
            else: p_first.add('ε')
            for a in p_first:
                if a != 'ε': m_data[nt][a].append(f"{nt}->{''.join(p)}")
            if 'ε' in p_first:
                for b in fo_sets[nt]: m_data[nt][b].append(f"{nt}->{''.join(p)}")

    final_table = pd.DataFrame("", index=fixed_g.keys(), columns=terms)
    for nt in fixed_g:
        for t in terms:
            rules = list(set(m_data[nt][t]))
            if len(rules) > 1:
                is_ll1 = False
                final_table.at[nt, t] = " | ".join(rules)
            elif len(rules) == 1:
                final_table.at[nt, t] = rules[0]

    st.header("3️⃣ مصفوفة الإعراب (M-Table)")
    styled_table = final_table.style.applymap(highlight_conflicts)
    st.dataframe(styled_table, use_container_width=True)

    if not is_ll1:
        st.markdown('<div class="conflict-msg">⚠️ هذه القواعد ليست من نوع LL(1): يوجد تضارب في الخلايا المظللة باللون الأحمر (Multiple Entries).</div>', unsafe_allow_html=True)

    # 7. المحاكاة (التطوير الأكاديمي لعمود الإدخال وزر الخطوة)
    st.header("4️⃣ التتبع والشجرة (Parsing Trace)")
    col_run, col_step = st.columns([1, 4])
    
    # دالة مساعدة لحساب الإدخال المتبقي
    def get_remaining_input(tokens, idx):
        if idx < len(tokens):
            rem = " ".join(tokens[idx:])
            return rem if rem.endswith('$') else rem + " $"
        return "$"

    if col_run.button("▶ تشغيل المحاكاة كاملة"):
        tokens = u_input.split()
        stack = [('$', '0'), (list(fixed_g.keys())[0], '0')]
        idx, node_id, trace = 0, 0, []
        dot = Digraph(); dot.attr(rankdir='TD')
        dot.node('0', list(fixed_g.keys())[0], style='filled', fillcolor='#BBDEFB')
        status = "Rejected"
        
        while stack:
            top, pid = stack.pop()
            look = tokens[idx] if idx < len(tokens) else '$'
            rem_input = get_remaining_input(tokens, idx)
            step = {"Stack": " ".join([s for s, i in stack] + [top]), "Input": rem_input, "Action": ""}
            
            if top == look:
                step["Action"] = f"Match {look}"
                idx += 1 # استهلاك الرمز
                if top == '$': status = "Accepted"; trace.append(step); break
            elif top in fixed_g:
                rules = list(set(m_data[top][look]))
                if len(rules) == 1:
                    rhs = rules[0].split('->')[1].replace('ε', '').strip()
                    step["Action"] = f"Apply {rules[0]}"
                    for sym in reversed(list(rhs)):
                        node_id += 1; nid = str(node_id)
                        dot.node(nid, sym, style='filled', fillcolor='#C8E6C9')
                        dot.edge(pid, nid)
                        stack.append((sym, nid))
                elif len(rules) > 1: step["Action"] = "❌ Conflict Error"; trace.append(step); break
                else: step["Action"] = "❌ No Rule"; trace.append(step); break
            else: step["Action"] = "❌ Mismatch Error"; trace.append(step); break
            trace.append(step)
        st.session_state.sim = {'trace': trace, 'dot': dot, 'status': status, 'finished': True, 'stack': [], 'idx': 0}

    if col_step.button("⏭ خطوة تالية"):
        if not st.session_state.sim['stack'] and not st.session_state.sim['finished']:
            st.session_state.sim['tokens'] = u_input.split()
            st.session_state.sim['stack'] = [('$', '0'), (list(fixed_g.keys())[0], '0')]
            st.session_state.sim['dot'] = Digraph(); st.session_state.sim['dot'].attr(rankdir='TD')
            st.session_state.sim['dot'].node('0', list(fixed_g.keys())[0], style='filled', fillcolor='#BBDEFB')
        
        if st.session_state.sim['stack'] and not st.session_state.sim['finished']:
            stack = st.session_state.sim['stack']
            tokens = st.session_state.sim['tokens']
            idx = st.session_state.sim['idx']
            dot = st.session_state.sim['dot']
            node_id = st.session_state.sim['node_id']
            
            top, pid = stack.pop()
            look = tokens[idx] if idx < len(tokens) else '$'
            rem_input = get_remaining_input(tokens, idx)
            step = {"Stack": " ".join([s for s, i in stack] + [top]), "Input": rem_input, "Action": ""}
            
            if top == look:
                step["Action"] = f"Match {look}"
                idx += 1 # استهلاك الرمز
                if top == '$': 
                    st.session_state.sim['status'] = "Accepted"
                    st.session_state.sim['finished'] = True
            elif top in fixed_g:
                rules = list(set(m_data[top][look]))
                if len(rules) == 1:
                    rhs = rules[0].split('->')[1].replace('ε', '').strip()
                    step["Action"] = f"Apply {rules[0]}"
                    for sym in reversed(list(rhs)):
                        node_id += 1; nid = str(node_id)
                        dot.node(nid, sym, style='filled', fillcolor='#C8E6C9')
                        dot.edge(pid, nid)
                        stack.append((sym, nid))
                elif len(rules) > 1:
                    step["Action"] = "❌ Conflict Error"; st.session_state.sim['status'] = "Rejected"; st.session_state.sim['finished'] = True
                else:
                    step["Action"] = "❌ No Rule"; st.session_state.sim['status'] = "Rejected"; st.session_state.sim['finished'] = True
            else:
                step["Action"] = "❌ Mismatch Error"; st.session_state.sim['status'] = "Rejected"; st.session_state.sim['finished'] = True
            
            st.session_state.sim['trace'].append(step)
            st.session_state.sim['idx'] = idx
            st.session_state.sim['node_id'] = node_id

    # 8. عرض النتائج والتقارير
    if st.session_state.sim['trace']:
        st.markdown('<div class="ltr-table">', unsafe_allow_html=True)
        st.table(pd.DataFrame(st.session_state.sim['trace']))
        st.markdown('</div>', unsafe_allow_html=True)
        
        if st.session_state.sim['finished']:
            color_class = "status-accepted" if st.session_state.sim['status'] == "Accepted" else "status-rejected"
            st.markdown(f'<div class="{color_class}">{st.session_state.sim["status"]}</div>', unsafe_allow_html=True)
        
        st.graphviz_chart(st.session_state.sim['dot'])

    st.header("5️⃣ تصدير التقارير")
    if st.button("📄 تحميل تقرير PDF"):
        pdf = AcademicPDF(); pdf.add_page()
        pdf.add_section("Original Grammar", grammar=grammar_raw)
        pdf.add_section("Fixed Grammar", grammar=fixed_g)
        pdf.add_section("M-Table", df=final_table)
        if st.session_state.sim['trace']:
            pdf.add_section("Parsing Trace", df=pd.DataFrame(st.session_state.sim['trace']))
        st.download_button("📥 تنزيل PDF", bytes(pdf.output()), "LL1_Complete_Report.pdf")

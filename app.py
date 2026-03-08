import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import time

# --- 1. دوال الحساب الآلي لـ First و Follow و Parsing Table ---

def get_first(grammar):
    first = {non_terminal: set() for non_terminal in grammar}
    
    def calculate_first(symbol):
        if not symbol or (not any(c.isupper() for c in symbol) and symbol != "ε"): 
            return {symbol} if symbol else set()
        if symbol == "ε": return {"ε"}
        
        res = set()
        for production in grammar.get(symbol, []):
            if production == ['ε']:
                res.add("ε")
            else:
                for char in production:
                    char_first = calculate_first(char)
                    res.update(char_first - {"ε"})
                    if "ε" not in char_first: break
                else: res.add("ε")
        return res

    for nt in grammar:
        first[nt] = calculate_first(nt)
    return first

def get_follow(grammar, start_symbol, first):
    follow = {nt: set() for nt in grammar}
    follow[start_symbol].add('$')
    changed = True
    while changed:
        changed = False
        for nt, productions in grammar.items():
            for prod in productions:
                for i, symbol in enumerate(prod):
                    if symbol in grammar:
                        before = len(follow[symbol])
                        next_part = prod[i+1:]
                        if next_part:
                            first_next = set()
                            for s in next_part:
                                s_first = first[s] if s in grammar else {s}
                                first_next.update(s_first - {"ε"})
                                if "ε" not in s_first: break
                            else: first_next.add("ε")
                            follow[symbol].update(first_next - {"ε"})
                            if "ε" in first_next: follow[symbol].update(follow[nt])
                        else:
                            follow[symbol].update(follow[nt])
                        if len(follow[symbol]) > before: changed = True
    return follow

# --- 2. عرض المدخلات (Input Buffer) بتنسيق الألوان ---

def highlight_input(tokens, current_index):
    html_str = "<div style='font-family: monospace; font-size: 18px; background: #1e1e1e; padding: 15px; border-radius: 8px; border: 1px solid #333;'>"
    for i, token in enumerate(tokens):
        if i < current_index:
            html_str += f"<span style='color: #666; text-decoration: line-through;'>{token}</span> "
        elif i == current_index:
            html_str += f"<span style='color: #000; background: #ffeb3b; padding: 3px 8px; border-radius: 4px; font-weight: bold; border: 1px solid #fbc02d;'>{token}</span> "
        else:
            html_str += f"<span style='color: #eee;'>{token}</span> "
    html_str += "</div>"
    return html_str

# --- 3. بناء شجرة التحليل (Parse Tree) ---

def build_tree(trace_steps):
    dot = Digraph(format='png')
    dot.attr(rankdir='TD', size='8,8')
    # منطق مبسط لبناء الشجرة من خطوات التحليل
    for i, step in enumerate(trace_steps):
        if "Apply" in step['Action']:
            parent = step['Action'].split('->')[0].strip().split()[-1]
            children = step['Action'].split('->')[1].strip().split()
            p_id = f"{parent}_{i}"
            dot.node(p_id, parent, shape='circle')
            for c in children:
                c_id = f"{c}_{i+1}"
                dot.node(c_id, c, shape='ellipse' if c.isupper() else 'plaintext')
                dot.edge(p_id, c_id)
    return dot

# --- الإعدادات العامة لواجهة التطبيق ---

st.set_page_config(page_title="Advanced LL(1) Studio", layout="wide")
st.title("🏗️ استوديو المحلل التنبؤي LL(1) المتكامل")

# Sidebar للمدخلات
st.sidebar.header("🛠️ إعدادات القواعد")
raw_input = st.sidebar.text_area("أدخل القواعد (LHS -> RHS1 | RHS2):", 
    "E -> T E'\nE' -> + T E' | ε\nT -> F T'\nT' -> * F T' | ε\nF -> ( E ) | id")

# معالجة القواعد
grammar = OrderedDict()
for line in raw_input.split('\n'):
    if '->' in line:
        lhs, rhs = line.split('->')
        lhs = lhs.strip()
        grammar[lhs] = [p.strip().split() for p in rhs.split('|')]

start_node = list(grammar.keys())[0]
first_sets = get_first(grammar)
follow_sets = get_follow(grammar, start_node, first_sets)

# --- 4. لوحة الإحصائيات (Dashboard) ---

st.subheader("📊 لوحة التحكم (Dashboard)")
stat_col1, stat_col2, stat_col3 = st.columns(3)

# إدخال الجملة
user_input = st.text_input("أدخل الجملة المراد تحليلها (افصل بمسافات):", "id + id * id")
tokens = user_input.split() + ['$']

# تنفيذ المحاكاة
if st.button("🚀 ابدأ عملية الإعراب والتحليل"):
    progress_bar = st.progress(0)
    input_placeholder = st.empty()
    stack_placeholder = st.empty()
    
    stack = ['$', start_node]
    index = 0
    trace = []
    
    while stack:
        top = stack[-1]
        lookahead = tokens[index]
        
        # تحديث العرض المرئي
        input_placeholder.markdown(highlight_input(tokens, index), unsafe_allow_html=True)
        stack_placeholder.code(f"المكدس: {' '.join(stack)}", language="text")
        
        step = {"Step": len(trace)+1, "Stack": " ".join(stack), "Input": " ".join(tokens[index:]), "Action": ""}
        
        if top == lookahead:
            step["Action"] = f"✅ Match {lookahead}"
            stack.pop()
            index += 1
        elif top in grammar:
            found = False
            for prod in grammar[top]:
                # منطق اختيار القاعدة
                prod_first = set()
                for s in prod:
                    s_f = first_sets[s] if s in grammar else {s}
                    prod_first.update(s_f - {"ε"})
                    if "ε" not in s_f: break
                else: prod_first.add("ε")
                
                if lookahead in prod_first or ("ε" in prod_first and lookahead in follow_sets[top]):
                    stack.pop()
                    if prod != ['ε']: stack.extend(reversed(prod))
                    step["Action"] = f"Apply {top} -> {' '.join(prod)}"
                    found = True
                    break
            if not found:
                step["Action"] = "❌ Error: No Rule"
                trace.append(step)
                break
        else:
            step["Action"] = "❌ Error"
            trace.append(step)
            break
            
        trace.append(step)
        progress_bar.progress(min(index / len(tokens), 1.0))
        time.sleep(0.4)

    # تحديث Dashboard بعد الانتهاء
    is_accepted = (len(stack) == 0 and index == len(tokens))
    stat_col1.metric("الخطوات", len(trace))
    stat_col2.metric("الحالة", "مقبولة ✅" if is_accepted else "مرفوضة ❌")
    stat_col3.metric("المؤشر النهائي", tokens[index] if index < len(tokens) else "End")

    if is_accepted: st.balloons()

    # عرض جدول التتبع
    st.subheader("📑 جدول التتبع التفصيلي (Trace Table)")
    df_trace = pd.DataFrame(trace)
    st.table(df_trace)

    # --- 5. خيار "تحميل التقرير" (Download Report) ---
    st.subheader("💾 مركز التحميل")
    csv = df_trace.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 تحميل التقرير (Excel/CSV)", data=csv, file_name="parse_report.csv", mime="text/csv")

    # عرض الشجرة
    st.subheader("🌳 شجرة الإعراب (Visual Parse Tree)")
    st.graphviz_chart(build_tree(trace))

# جداول المعلومات في الأسفل
with st.expander("ℹ️ عرض مجموعات First & Follow"):
    st.write(pd.DataFrame({
        "Non-Terminal": first_sets.keys(),
        "First": [str(s) for s in first_sets.values()],
        "Follow": [str(s) for s in follow_sets.values()]
    }))

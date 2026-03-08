import streamlit as st
import pandas as pd
from collections import OrderedDict
from graphviz import Digraph
import time
import re

# --- 1. دوال الحساب الآلي لـ First و Follow ---

def get_first(grammar):
    first = {nt: set() for nt in grammar}
    def calculate_first(symbol):
        if not symbol or (symbol not in grammar and symbol != "ε"): 
            return {symbol} if symbol else set()
        if symbol == "ε": return {"ε"}
        res = set()
        for production in grammar.get(symbol, []):
            if not production or production == ['ε']: res.add("ε")
            else:
                for char in production:
                    char_first = calculate_first(char)
                    res.update(char_first - {"ε"})
                    if "ε" not in char_first: break
                else: res.add("ε")
        return res
    for nt in grammar: first[nt] = calculate_first(nt)
    return first

def get_follow(grammar, start_symbol, first):
    follow = {nt: set() for nt in grammar}
    if not start_symbol: return follow
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
                                s_f = first[s] if s in grammar else {s}
                                first_next.update(s_f - {"ε"})
                                if "ε" not in s_f: break
                            else: first_next.add("ε")
                            follow[symbol].update(first_next - {"ε"})
                            if "ε" in first_next: follow[symbol].update(follow[nt])
                        else: follow[symbol].update(follow[nt])
                        if len(follow[symbol]) > before: changed = True
    return follow

# --- 2. معالجة القواعد بمرونة فائقة (دعم السهم → وفك الملتصق) ---

def parse_grammar_flexible(raw_text):
    grammar = OrderedDict()
    lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
    
    for line in lines:
        # دعم كافة أشكال الأسهم بما فيها السهم في الصورة →
        parts = re.split(r'->|=>|=|→', line)
        if len(parts) == 2:
            lhs = parts[0].strip()
            rhs_options = parts[1].split('|')
            productions = []
            for opt in rhs_options:
                opt_str = opt.strip()
                # إذا كانت الخيارات تحتوي مسافات نعتمدها
                if ' ' in opt_str:
                    symbols = [s.strip() for s in opt_str.split() if s.strip()]
                else:
                    # فك الرموز الملتصقة (مثل ABCDE تصبح A B C D E)
                    # مع دعم id و ε والرموز المتبوعة بـ ' مثل E'
                    symbols = re.findall(r"[A-Z]'?|[a-z]|ε|id|\(|\)|\+|\*|\-", opt_str)
                
                if symbols:
                    productions.append(symbols)
                elif not opt_str or opt_str in ["ε", "epsilon"]:
                    productions.append(["ε"])
            
            if lhs and productions:
                grammar[lhs] = productions
    return grammar

# --- 3. بقية وظائف التطبيق (الرسم والواجهة) ---

def highlight_input(tokens, current_index):
    html_str = "<div style='font-family: monospace; font-size: 18px; background: #1a1a1a; padding: 15px; border-radius: 8px; border: 1px solid #333;'>"
    for i, token in enumerate(tokens):
        if i < current_index:
            html_str += f"<span style='color: #555; text-decoration: line-through;'>{token}</span> "
        elif i == current_index:
            html_str += f"<span style='color: #000; background: #ffeb3b; padding: 2px 8px; border-radius: 4px; font-weight: bold;'>{token}</span> "
        else:
            html_str += f"<span style='color: #ddd;'>{token}</span> "
    html_str += "</div>"
    return html_str

def build_tree(trace_steps):
    dot = Digraph()
    dot.attr(rankdir='TD')
    for i, step in enumerate(trace_steps):
        if "Apply" in step['Action']:
            parts = re.search(r'Apply (.*) -> (.*)', step['Action'])
            if parts:
                parent, children_str = parts.groups()
                p_id = f"{parent}_{i}"
                dot.node(p_id, parent, shape='circle', style='filled', fillcolor='#bbdefb')
                for c in children_str.split():
                    c_id = f"{c}_{i+1}"
                    dot.node(c_id, c, shape='ellipse' if any(x.isupper() for x in c) else 'plaintext')
                    dot.edge(p_id, c_id)
    return dot

# --- إعدادات الواجهة ---
st.set_page_config(page_title="Ultra Flexible LL(1) Studio", layout="wide")
st.title("🏗️ استوديو LL(1) الفائق")

st.sidebar.header("🛠️ إعدادات القواعد")
example = "E → T E'\nE' → + T E' | ε\nT → F T'\nT' → * F T' | ε\nF → ( E ) | id"
raw_input = st.sidebar.text_area("أدخل القواعد (يدعم → والرموز الملتصقة):", example, height=250)

grammar = parse_grammar_flexible(raw_input)

if not grammar:
    st.warning("⚠️ يرجى إدخال القواعد بشكل صحيح (LHS → RHS).")
    st.info("تأكد من استخدام سهم مثل -> أو → للفصل.")
    st.stop()

start_node = list(grammar.keys())[0]
first_sets = get_first(grammar)
follow_sets = get_follow(grammar, start_node, first_sets)

# واجهة المحاكاة والـ Dashboard
st.subheader("📊 لوحة التحكم والمحاكاة")
user_input = st.text_input("أدخل الجملة (افصل بين الرموز بمسافات):", "id + id * id")
tokens = [t.strip() for t in user_input.split() if t.strip()] + ['$']

if st.button("🚀 تحليل"):
    col1, col2, col3 = st.columns(3)
    input_box = st.empty()
    stack_box = st.empty()
    
    stack = ['$', start_node]
    index, trace = 0, []
    
    while stack:
        top = stack[-1]
        lookahead = tokens[index]
        input_box.markdown(highlight_input(tokens, index), unsafe_allow_html=True)
        stack_box.info(f"**المكدس:** `{' '.join(stack)}` | **المؤشر:** `{lookahead}`")
        
        step = {"Step": len(trace)+1, "Stack": " ".join(stack), "Input": " ".join(tokens[index:]), "Action": ""}
        
        if top == lookahead:
            step["Action"] = f"✅ Match {lookahead}"
            stack.pop()
            index += 1
        elif top in grammar:
            found = False
            for prod in grammar[top]:
                p_first = set()
                for s in prod:
                    s_f = first_sets[s] if s in grammar else {s}
                    p_first.update(s_f - {"ε"})
                    if "ε" not in s_f: break
                else: p_first.add("ε")
                
                if lookahead in p_first or ("ε" in p_first and lookahead in follow_sets[top]):
                    stack.pop()
                    if prod != ['ε']: stack.extend(reversed(prod))
                    step["Action"] = f"Apply {top} -> {' '.join(prod)}"
                    found = True
                    break
            if not found:
                step["Action"] = f"❌ Error at {lookahead}"
                trace.append(step); break
        elif top == 'ε': stack.pop(); continue
        else:
            step["Action"] = f"❌ Error"; trace.append(step); break
            
        trace.append(step)
        time.sleep(0.3)

    is_acc = (not stack and index == len(tokens))
    col1.metric("الخطوات", len(trace))
    col2.metric("الحالة", "مقبولة ✅" if is_acc else "مرفوضة ❌")
    col3.metric("النتيجة", "Success" if is_acc else "Failed")
    if is_acc: st.balloons()
    
    st.table(pd.DataFrame(trace))
    
    st.subheader("📥 تحميل التقرير")
    csv = pd.DataFrame(trace).to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 تحميل التقرير كملف CSV", csv, "report.csv", "text/csv")
    
    st.subheader("🌳 شجرة الإعراب")
    st.graphviz_chart(build_tree(trace))

with st.expander("ℹ️ مجموعات First & Follow"):
    st.write(pd.DataFrame({
        "Non-Terminal": first_sets.keys(),
        "First": [str(list(s)) for s in first_sets.values()],
        "Follow": [str(list(s)) for s in follow_sets.values()]
    }))

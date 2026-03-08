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

# --- 2. معالجة القواعد بمرونة عالية ---

def parse_grammar_flexible(raw_text):
    grammar = OrderedDict()
    # تقسيم النص إلى أسطر وتجاهل الفارغ منها
    lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
    
    for line in lines:
        # دعم أشكال مختلفة من الأسهم (-> أو => أو =)
        parts = re.split(r'->|=>|=', line)
        if len(parts) == 2:
            lhs = parts[0].strip()
            # تقسيم الخيارات بناءً على |
            rhs_options = parts[1].split('|')
            productions = []
            for opt in rhs_options:
                # تنظيف المسافات الزائدة وتحويل الخيار إلى قائمة رموز
                symbols = [s.strip() for s in opt.split() if s.strip()]
                if symbols:
                    productions.append(symbols)
                elif "ε" in opt or "epsilon" in opt.lower(): # دعم ε حتى لو لم توجد مسافات
                    productions.append(["ε"])
            
            if lhs and productions:
                grammar[lhs] = productions
    return grammar

# --- 3. بقية وظائف التطبيق (الرسم والواجهة) ---

def build_tree(trace_steps):
    dot = Digraph()
    dot.attr(rankdir='TD')
    for i, step in enumerate(trace_steps):
        if "Apply" in step['Action']:
            match = re.search(r'Apply (.*) -> (.*)', step['Action'])
            if match:
                parent, children_str = match.groups()
                children = children_str.split()
                p_id = f"{parent}_{i}"
                dot.node(p_id, parent, shape='circle', style='filled', fillcolor='#bbdefb')
                for c in children:
                    c_id = f"{c}_{i+1}"
                    dot.node(c_id, c, shape='ellipse' if any(x.isupper() for x in c) else 'plaintext')
                    dot.edge(p_id, c_id)
    return dot

st.set_page_config(page_title="Flexible LL(1) Studio", layout="wide")
st.title("🏗️ استوديو LL(1) المرن")

st.sidebar.header("🛠️ إعدادات القواعد")
example = "E -> T E'\nE' -> + T E' | ε\nT -> F T'\nT' -> * F T' | ε\nF -> ( E ) | id"
raw_input = st.sidebar.text_area("أدخل القواعد (مرونة في المسافات والأسهم):", example, height=250)

# استخدام المعالج المرن
grammar = parse_grammar_flexible(raw_input)

if not grammar:
    st.warning("⚠️ يرجى إدخال القواعد بشكل صحيح (LHS -> RHS).")
    st.stop()

start_node = list(grammar.keys())[0]
first_sets = get_first(grammar)
follow_sets = get_follow(grammar, start_node, first_sets)

# واجهة المحاكاة
user_input = st.text_input("الجملة (افصل بين الرموز بمسافات):", "id + id * id")
tokens = [t.strip() for t in user_input.split() if t.strip()] + ['$']

if st.button("🚀 تحليل"):
    col1, col2, col3 = st.columns(3)
    status_box = st.empty()
    
    stack = ['$', start_node]
    index, trace = 0, []
    
    while stack:
        top = stack[-1]
        lookahead = tokens[index]
        status_box.info(f"**المكدس:** `{' '.join(stack)}` | **المؤشر:** `{lookahead}`")
        
        step = {"Step": len(trace)+1, "Stack": " ".join(stack), "Input": " ".join(tokens[index:]), "Action": ""}
        
        if top == lookahead:
            step["Action"] = f"✅ Match {lookahead}"
            stack.pop()
            index += 1
        elif top in grammar:
            found = False
            for prod in grammar[top]:
                # حساب First للقاعدة
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
    if is_acc: st.balloons()
    
    st.table(pd.DataFrame(trace))
    st.graphviz_chart(build_tree(trace))

with st.expander("ℹ️ مجموعات First & Follow المحسوبة"):
    st.write(pd.DataFrame({
        "Non-Terminal": first_sets.keys(),
        "First": [str(list(s)) for s in first_sets.values()],
        "Follow": [str(list(s)) for s in follow_sets.values()]
    }))

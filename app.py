import streamlit as st
import pandas as pd
from collections import OrderedDict

# دالة بناء الجدول مع دعم كشف التضارب
def build_m_table_with_conflicts(grammar, first, follow):
    terms = sorted(list({s for ps in grammar.values() for p in ps for s in p if s not in grammar and s != 'ε'})) + ['$']
    # استخدام list لتخزين أكثر من قاعدة في نفس الخلية
    table = {nt: {t: [] for t in terms} for nt in grammar}
    is_ll1 = True

    for nt, prods in grammar.items():
        for p in prods:
            p_first = set()
            for s in p:
                sf = first[s] if s in grammar else {s}
                p_first.update(sf - {'ε'})
                if 'ε' not in sf: break
            else: p_first.add('ε')
            
            for a in p_first:
                if a != 'ε':
                    rule = f"{nt} -> {' '.join(p)}"
                    if rule not in table[nt][a]:
                        table[nt][a].append(rule)
            
            if 'ε' in p_first:
                for b in follow[nt]:
                    rule = f"{nt} -> {' '.join(p)}"
                    if rule not in table[nt][b]:
                        table[nt][b].append(rule)

    # تحويل القوائم إلى نصوص للعرض وكشف التضارب
    display_table = pd.DataFrame("", index=grammar.keys(), columns=terms)
    for nt in grammar:
        for t in terms:
            rules = table[nt][t]
            if len(rules) > 1:
                is_ll1 = False
                display_table.at[nt, t] = " | ".join(rules) # عرض القواعد المتقاطعة
            elif len(rules) == 1:
                display_table.at[nt, t] = rules[0]

    return display_table, is_ll1

# جزء العرض في Streamlit
st.header("3️⃣ مصفوفة الإعراب (M-Table)")
m_table, is_ll1_status = build_m_table_with_conflicts(fixed_g, f_sets, fo_sets)
st.dataframe(m_table, use_container_width=True)

if not is_ll1_status:
    st.error("⚠️ تنبيه أكاديمي: هذه القواعد ليست من نوع LL(1) لوجود تضارب في الجدول (Multiple entries in cells).")
else:
    st.success("✅ هذه القواعد من نوع LL(1) ونظامية.")

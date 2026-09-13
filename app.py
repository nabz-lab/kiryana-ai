import os, json, re
from pathlib import Path
import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="Kiryana AI", page_icon="🛒", layout="wide")

DATA = Path(__file__).parent / "groceries.json"
GROCERIES = json.loads(DATA.read_text(encoding="utf-8"))
LOOKUP = {x["name"].lower(): x for x in GROCERIES}

st.markdown("""
<style>
.title{font-size:3rem;font-weight:800;margin-bottom:0}
.subtitle{font-size:1.1rem;color:#666;margin-bottom:1.5rem}
</style>
""", unsafe_allow_html=True)

def calculate_total(basket):
    total = 0
    clean = []
    for x in basket:
        g = LOOKUP.get(x["name"].lower())
        if not g: continue
        q = max(0.5, float(x.get("quantity", 1)))
        cost = round(q * g["price"])
        clean.append({**g, "quantity": q, "cost": cost})
        total += cost
    return clean, total

def optimize_basket(basket, budget):
    basket = [dict(x) for x in basket]
    changes = []
    def total(): return sum(round(x["quantity"] * x["price"]) for x in basket)

    while total() > budget:
        candidates = [x for x in basket if x["priority"] == "optional"]
        if not candidates: break
        x = max(candidates, key=lambda z: z["quantity"] * z["price"])
        saving = round(x["quantity"] * x["price"])
        changes.append(f"Removed {x['name']} (-Rs. {saving})")
        basket.remove(x)

    while total() > budget:
        candidates = [x for x in basket if x["priority"] == "important" and x["quantity"] > 0.5]
        if not candidates: break
        x = max(candidates, key=lambda z: z["price"])
        old = x["quantity"]
        x["quantity"] = max(0.5, old - 0.5)
        saving = round((old - x["quantity"]) * x["price"])
        changes.append(f"Reduced {x['name']} ({old:g} → {x['quantity']:g}, -Rs. {saving})")

    while total() > budget:
        candidates = [x for x in basket if x["priority"] == "essential" and x["quantity"] > 0.5]
        if not candidates: break
        x = max(candidates, key=lambda z: z["price"])
        old = x["quantity"]
        x["quantity"] = max(0.5, old - 0.5)
        saving = round((old - x["quantity"]) * x["price"])
        changes.append(f"Reduced {x['name']} ({old:g} → {x['quantity']:g}, -Rs. {saving})")
    return basket, total(), changes

def modify_basket(basket, text):
    t = text.lower()
    basket = [dict(x) for x in basket]
    for g in GROCERIES:
        n = g["name"].lower()
        if re.search(rf"\b(remove|don't buy|do not buy|no)\s+{re.escape(n)}\b", t) or f"already have {n}" in t:
            basket = [x for x in basket if x["name"].lower() != n]
        if f"add {n}" in t or f"keep {n}" in t:
            if not any(x["name"].lower() == n for x in basket):
                basket.append({**g, "quantity":1})
    return basket

def ai_explanation(budget, people, days, needs, basket, total, request):
    key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))
    if not key: return "Built-in budgeting agent handled the calculation. Add OPENAI_API_KEY for natural-language AI explanations."
    model = st.secrets.get("OPENAI_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    catalog = "\n".join(f"{g['name']} | {g['unit']} | Rs. {g['price']} | {g['priority']}" for g in GROCERIES)
    prompt = f"""You are Kiryana AI, a grocery budgeting agent for Karachi.
Budget: Rs. {budget}; household: {people}; days: {days}; needs: {needs}
Current basket: {json.dumps(basket)}
Total: Rs. {total}
Latest user request: {request}
Prototype catalog:
{catalog}
Explain briefly what the agent decided and why. Never invent prices. Do not claim prices are live."""
    try:
        return OpenAI(api_key=key).responses.create(model=model, input=prompt).output_text
    except Exception as e:
        return f"AI explanation unavailable: {e}"

if "basket" not in st.session_state: st.session_state.basket = None
if "changes" not in st.session_state: st.session_state.changes = []
if "note" not in st.session_state: st.session_state.note = ""

st.markdown('<div class="title">🛒 Kiryana AI</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">An AI agent that plans, checks, optimizes and adapts your grocery basket.</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("Your Grocery Goal")
    budget = st.number_input("Budget (Rs.)", min_value=500, value=8000, step=500)
    people = st.number_input("Household size", min_value=1, value=4, step=1)
    days = st.number_input("Shopping period (days)", min_value=1, value=7, step=1)
    needs = st.text_area("What do you need?", value="basic groceries, chicken, vegetables, breakfast items and snacks")
    generate = st.button("🚀 Generate My Plan", use_container_width=True)
    st.caption("Prototype prices are estimated sample values, not live Karachi market prices.")

if generate:
    starter = [
        ("Atta",1),("Rice",1),("Daal",1),("Cooking Oil",2),("Eggs",2),
        ("Milk",min(7,max(2,days))),("Chicken",2),("Potatoes",2),
        ("Onions",2),("Tomatoes",1)
    ]
    n = needs.lower()
    if any(k in n for k in ["fruit","banana","apple"]): starter.append(("Bananas",1))
    if "snack" in n or "biscuit" in n: starter.append(("Biscuits",2))
    if "tea" in n or "breakfast" in n: starter += [("Tea",1),("Bread",2)]
    basket,total = calculate_total([{"name":x,"quantity":q} for x,q in starter])
    basket,total,changes = optimize_basket(basket,budget)
    st.session_state.basket, st.session_state.changes = basket, changes
    st.session_state.note = ai_explanation(budget,people,days,needs,basket,total,"Create the initial plan.")

if st.session_state.basket:
    basket = st.session_state.basket
    total = round(sum(x["quantity"]*x["price"] for x in basket))
    remaining = budget-total
    a,b,c = st.columns(3)
    a.metric("Budget",f"Rs. {budget:,.0f}")
    b.metric("Basket",f"Rs. {total:,.0f}")
    c.metric("Remaining",f"Rs. {remaining:,.0f}")
    if remaining >= 0: st.success(f"🟢 Within budget — Rs. {remaining:,.0f} remaining.")
    else: st.error(f"🔴 Over budget — Rs. {abs(remaining):,.0f} above budget.")

    st.subheader("🛍️ Grocery Basket")
    st.dataframe([
        {"Item":x["name"],"Quantity":x["quantity"],"Unit":x["unit"],"Estimated Cost":f"Rs. {x['quantity']*x['price']:,.0f}"}
        for x in basket
    ], use_container_width=True, hide_index=True)

    if st.session_state.changes:
        st.subheader("⚡ Agent Optimization")
        for change in st.session_state.changes[:8]: st.write("• " + change)

    with st.expander("🤖 Why did the agent make these decisions?"):
        st.write(st.session_state.note)

    st.divider()
    st.subheader("💬 Change your plan")
    request = st.text_input("Tell Kiryana AI what to change", placeholder="Keep the snacks, but make it cheaper.")
    if st.button("🔄 Update My Plan", use_container_width=True) and request:
        modified = modify_basket(basket, request)
        modified,total,changes = optimize_basket(modified,budget)
        st.session_state.basket,st.session_state.changes = modified,changes
        st.session_state.note = ai_explanation(budget,people,days,needs,modified,total,request)
        st.rerun()
else:
    st.info("Enter your grocery goal in the sidebar and click Generate My Plan.")
    st.markdown("### Try this demo\n**Budget:** Rs. 8,000  \n**Family:** 4 people  \n**Duration:** 7 days  \n**Needs:** basic groceries, chicken, vegetables, breakfast items and snacks")

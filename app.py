import os, json, re
from pathlib import Path
import streamlit as st

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

st.set_page_config(page_title="Kiryana AI", page_icon="🛒", layout="wide")

DATA = json.loads((Path(__file__).parent / "groceries.json").read_text(encoding="utf-8"))
ITEMS = DATA["items"]
LOOKUP = {x["name"].lower(): x for x in ITEMS}

st.markdown("""
<style>
.title{font-size:3rem;font-weight:800;margin-bottom:0}
.subtitle{font-size:1.05rem;color:#666;margin-bottom:1.2rem}
</style>
""", unsafe_allow_html=True)

def round_qty(q, step=0.5):
    return max(step, round(q / step) * step)

def requested_categories(text):
    t = text.lower()
    cats = {"staple","pulse","dairy","protein","vegetable"}
    if any(k in t for k in ["breakfast","tea","bread"]): cats.add("breakfast")
    if any(k in t for k in ["fruit","apple","banana"]): cats.add("fruit")
    if any(k in t for k in ["snack","biscuit","juice","chips"]): cats.add("snack")
    return cats

def build_plan(people, days, needs):
    weeks = days / 7
    cats = requested_categories(needs)
    plan = []
    for item in ITEMS:
        if item["category"] not in cats:
            continue
        qty = max(item["min_qty"], round_qty(item["per_person_week"] * people * weeks))
        plan.append({**item, "quantity":qty, "cost":round(qty*item["price"])})
    return plan

def total(plan):
    return round(sum(x["cost"] for x in plan))

def optimize(plan, budget):
    plan = [dict(x) for x in plan]
    changes = []
    while total(plan) > budget:
        candidates = [x for x in plan if x["priority"]=="optional"]
        if not candidates: break
        x=max(candidates,key=lambda z:z["cost"])
        changes.append(f"Removed {x['name']} to protect essentials (saved Rs. {x['cost']:,}).")
        plan.remove(x)
    while total(plan) > budget:
        candidates=[x for x in plan if x["priority"]=="important" and x["quantity"]>x["min_qty"]]
        if not candidates: break
        x=max(candidates,key=lambda z:z["price"])
        old=x["quantity"]
        x["quantity"]=max(x["min_qty"],round(old-0.5,2))
        x["cost"]=round(x["quantity"]*x["price"])
        changes.append(f"Reduced {x['name']} from {old:g} to {x['quantity']:g} {x['unit']}.")
    while total(plan) > budget:
        candidates=[x for x in plan if x["priority"]=="essential" and x["quantity"]>x["min_qty"]]
        if not candidates: break
        x=max(candidates,key=lambda z:z["price"])
        old=x["quantity"]
        x["quantity"]=max(x["min_qty"],round(old-0.5,2))
        x["cost"]=round(x["quantity"]*x["price"])
        changes.append(f"Reduced essential {x['name']} from {old:g} to {x['quantity']:g} {x['unit']} as a last resort.")
    return plan,total(plan),changes

def apply_request(plan, request):
    t=request.lower()
    plan=[dict(x) for x in plan]
    for item in ITEMS:
        n=item["name"].lower()
        if re.search(rf"\b(remove|skip|don't buy|do not buy|without)\s+{re.escape(n)}\b",t) or f"already have {n}" in t:
            plan=[x for x in plan if x["name"].lower()!=n]
        if f"add {n}" in t or f"include {n}" in t:
            if not any(x["name"].lower()==n for x in plan):
                q=max(item["min_qty"],round_qty(item["per_person_week"]))
                plan.append({**item,"quantity":q,"cost":round(q*item["price"])})
    if "no snacks" in t or "without snacks" in t:
        plan=[x for x in plan if x["category"]!="snack"]
    if "no fruit" in t or "without fruit" in t:
        plan=[x for x in plan if x["category"]!="fruit"]
    return plan

def ai_explanation(budget,people,days,needs,plan,request=""):
    key=st.secrets.get("OPENAI_API_KEY",os.getenv("OPENAI_API_KEY"))
    if not key or OpenAI is None:
        return "The built-in budgeting agent calculated quantities from people × days and checked the stored reference prices. Add OPENAI_API_KEY for a natural-language AI explanation."
    model=st.secrets.get("OPENAI_MODEL",os.getenv("OPENAI_MODEL","gpt-4o-mini"))
    prompt=f"""You are Kiryana AI for Karachi/Pakistan.
Budget Rs. {budget}; people {people}; days {days}; needs {needs}; latest request {request}.
Basket: {json.dumps(plan)}
Explain in 4 short bullets: quantity logic, budget status, biggest cost drivers, and any trade-offs. Say that prices are reference prices, not live quotes. Never invent prices."""
    try:
        return OpenAI(api_key=key).responses.create(model=model,input=prompt).output_text
    except Exception as e:
        return f"AI explanation unavailable: {e}"

if "plan" not in st.session_state: st.session_state.plan=None
if "changes" not in st.session_state: st.session_state.changes=[]
if "note" not in st.session_state: st.session_state.note=""

st.markdown('<div class="title">🛒 Kiryana AI</div>',unsafe_allow_html=True)
st.markdown('<div class="subtitle">Estimate needs → price basket → check budget → optimize → adapt.</div>',unsafe_allow_html=True)

with st.sidebar:
    st.header("Your Grocery Goal")
    budget=st.number_input("Budget (Rs.)",min_value=500,value=8000,step=500)
    people=st.number_input("People",min_value=1,max_value=20,value=4,step=1)
    days=st.number_input("Shopping period (days)",min_value=1,max_value=31,value=7,step=1)
    needs=st.text_area("What do you need?",value="basic groceries, chicken, vegetables, breakfast items and snacks",height=120)
    generate=st.button("🚀 Generate Accurate Plan",use_container_width=True)
    st.divider()
    st.caption("Price reference: PBS SPI week ended 10 Sep 2026. Some items use reference estimates where the PBS basket does not directly provide them.")
    st.caption("Actual Karachi prices vary by neighbourhood, shop, brand, quality and pack size.")

if generate:
    raw=build_plan(people,days,needs)
    plan,final_total,changes=optimize(raw,budget)
    st.session_state.plan=plan
    st.session_state.changes=changes
    st.session_state.note=ai_explanation(budget,people,days,needs,plan)

if st.session_state.plan:
    plan=st.session_state.plan
    basket_total=total(plan)
    remaining=budget-basket_total
    c1,c2,c3=st.columns(3)
    c1.metric("Budget",f"Rs. {budget:,.0f}")
    c2.metric("Estimated basket",f"Rs. {basket_total:,.0f}")
    c3.metric("Remaining",f"Rs. {remaining:,.0f}")
    if remaining>=0: st.success(f"🟢 Within budget — Rs. {remaining:,.0f} remaining.")
    else: st.error(f"🔴 Minimum practical basket is still Rs. {abs(remaining):,.0f} over budget.")
    st.subheader("🛍️ Recommended basket")
    st.dataframe([{
        "Item":x["name"],
        "Quantity":f"{x['quantity']:g} {x['unit']}",
        "Reference price":f"Rs. {x['price']:,.0f}",
        "Estimated cost":f"Rs. {x['cost']:,.0f}",
        "Priority":x["priority"].title()
    } for x in plan],use_container_width=True,hide_index=True)
    essential=sum(x["cost"] for x in plan if x["priority"]=="essential")
    important=sum(x["cost"] for x in plan if x["priority"]=="important")
    optional=sum(x["cost"] for x in plan if x["priority"]=="optional")
    st.write(f"**Essentials:** Rs. {essential:,.0f}  |  **Important:** Rs. {important:,.0f}  |  **Optional:** Rs. {optional:,.0f}")
    if st.session_state.changes:
        st.subheader("⚡ Agent optimization")
        for change in st.session_state.changes: st.write("• "+change)
    with st.expander("🤖 Why did the agent choose this?"):
        st.write(st.session_state.note)
    st.caption("Reference pricing is dated 10 September 2026 and is not a live shop quote.")
    st.divider()
    st.subheader("💬 Change the plan")
    request=st.text_input("Tell the agent what changed",placeholder="Add biscuits, but keep me under Rs. 8,000.")
    if st.button("🔄 Re-plan",use_container_width=True) and request:
        modified=apply_request(plan,request)
        modified,new_total,changes=optimize(modified,budget)
        st.session_state.plan=modified
        st.session_state.changes=changes
        st.session_state.note=ai_explanation(budget,people,days,needs,modified,request)
        st.rerun()
else:
    st.info("Set your budget, household size, duration and needs, then generate the plan.")
    st.markdown("### Demo\\n**Budget:** Rs. 8,000  \\n**People:** 4  \\n**Days:** 7  \\n**Needs:** basic groceries, chicken, vegetables, breakfast items and snacks")

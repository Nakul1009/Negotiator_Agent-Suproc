from typing import TypedDict, Dict, Any
from langgraph.graph import StateGraph, END
import json
import re

# 1. State Definition
class NegotiatorState(TypedDict):
    # Inputs
    rfq: Dict[str, Any]
    quote: Dict[str, Any]
    
    # Ingested/Routed variables
    item: str
    quantity: int
    destination: str
    supplier_location: str
    quoted_price: float
    
    # Retrieved Env Data
    base_material_cost: float
    labor_multiplier: float
    shipping_cost_per_unit: float
    
    # Calculations
    calculated_base_cost_per_unit: float
    total_base_cost: float
    supplier_margin: float
    
    # Outputs
    raw_llm_response: str
    private_report: str
    supplier_message: str

# Node 1: Ingestion & Routing
def ingest_and_route(state: NegotiatorState) -> Dict[str, Any]:
    rfq = state["rfq"]
    quote = state["quote"]
    
    return {
        "item": rfq.get("item", ""),
        "quantity": rfq.get("quantity", 0),
        "destination": rfq.get("destination", ""),
        "supplier_location": quote.get("supplier_location", ""),
        "quoted_price": float(quote.get("total_quoted_price_inr", 0.0))
    }

# Node 2: The Mock Retriever
def mock_retriever(state: NegotiatorState) -> Dict[str, Any]:
    with open("mock_market_db.json", "r") as f:
        db = json.load(f)
        
    item = state["item"]
    supplier_loc = state["supplier_location"]
    destination = state["destination"]
    
    # 1. Pull material cost
    base_material_cost = db.get("materials", {}).get(item, {}).get("base_cost_inr", 0.0)
    
    # 2. Pull labor multiplier (matching by substring)
    labor_multiplier = 1.0
    for loc, info in db.get("labor", {}).items():
        if loc.lower() in supplier_loc.lower() or supplier_loc.lower() in loc.lower():
            labor_multiplier = info.get("manufacturing_multiplier", 1.0)
            break
            
    # 3. Pull shipping cost (matching by substring of cities/regions)
    sup_match = re.search(r"([A-Za-z\-]+)", supplier_loc)
    dest_match = re.search(r"([A-Za-z\-]+)", destination)
    sup_name = sup_match.group(1) if sup_match else ""
    dest_name = dest_match.group(1) if dest_match else ""
    
    shipping_cost = 0.0
    for key, val in db.get("shipping", {}).items():
        if sup_name.lower() in key.lower() and dest_name.lower() in key.lower():
            shipping_cost = val.get("cost_per_unit_inr", 0.0)
            break
    else:
        # Fallback to direct key if no substring match
        shipping_key = f"{sup_name}_to_{dest_name}"
        shipping_cost = db.get("shipping", {}).get(shipping_key, {}).get("cost_per_unit_inr", 0.0)
        
    return {
        "base_material_cost": base_material_cost,
        "labor_multiplier": labor_multiplier,
        "shipping_cost_per_unit": shipping_cost
    }

# Node 3: The Deterministic Calculator
def deterministic_calculator(state: NegotiatorState) -> Dict[str, Any]:
    material = state["base_material_cost"]
    labor_multiplier = state["labor_multiplier"]
    shipping = state["shipping_cost_per_unit"]
    quantity = state["quantity"]
    quoted_price = state["quoted_price"]
    
    # Base Cost = (Material * Labor Multiplier + Shipping) * Quantity
    base_cost_per_unit = (material * labor_multiplier) + shipping
    total_base_cost = base_cost_per_unit * quantity
    
    # Margin = ((Quoted Price - Base Cost) / Quoted Price) * 100
    if quoted_price > 0:
        margin = ((quoted_price - total_base_cost) / quoted_price) * 100
    else:
        margin = 0.0
        
    return {
        "calculated_base_cost_per_unit": base_cost_per_unit,
        "total_base_cost": total_base_cost,
        "supplier_margin": margin
    }

# Node 4: The Strategic Reasoner (LLM)
def strategic_reasoner(state: NegotiatorState) -> Dict[str, Any]:
    from llm_client import llm_call
    
    item = state["item"]
    quantity = state["quantity"]
    destination = state["destination"]
    supplier_location = state["supplier_location"]
    quoted_price = state["quoted_price"]
    total_base_cost = state["total_base_cost"]
    supplier_margin = state["supplier_margin"]
    
    # Calculate what a target 25% margin price would be:
    # Margin = (QuotedPrice - BaseCost) / QuotedPrice = 0.25 => QuotedPrice * 0.75 = BaseCost => QuotedPrice = BaseCost / 0.75
    target_price_25 = total_base_cost / 0.75
    
    system_prompt = (
        "You are a B2B Procurement Strategist. Your goal is to secure a fair market price that ensures a "
        "long-term, profitable relationship for BOTH the buyer and the seller.\n\n"
        "Data Provided:\n"
        f"- Item: {item}\n"
        f"- Quantity: {quantity}\n"
        f"- Destination: {destination}\n"
        f"- Supplier Location: {supplier_location}\n"
        f"- Supplier's Quoted Price: ₹{quoted_price:,.2f}\n"
        f"- Calculated Base Cost (Materials + Labor + Shipping): ₹{total_base_cost:,.2f}\n"
        f"- Supplier's Current Profit Margin: {supplier_margin:.2f}%\n"
        f"- Suggested Target Price (at 25% margin): ₹{target_price_25:,.2f}\n\n"
        "Instructions:\n"
        "Internal Report:\n"
        "- Write a brief, bulleted report for the buyer explaining the cost breakdown.\n"
        "- State clearly if the margin is fair (20-30%) or inflated (>30%).\n"
        "- Use the labels: Supplier Quote, Estimated True Cost, Estimated Margin, and Analysis.\n\n"
        "Negotiation Draft:\n"
        "- If the margin is >30%, draft a message to the supplier.\n"
        "- Do NOT demand a 0% margin.\n"
        "- Target a 25% margin (suggest the target price calculated above or round it cleanly).\n"
        "- Use collaborative language.\n"
        "- Highlight that you understand their logistics and material costs, but ask them to adjust "
        "their markup to align with market standards so you can approve the PO immediately.\n"
        "- Never be adversarial.\n"
        "- If the margin is fair (20-30%), draft a short collaborative acceptance message to the supplier instead.\n\n"
        "Formatting constraint:\n"
        "You MUST format the output exactly as two distinct sections. Use the tags '[PRIVATE BUYER REPORT]' "
        "and '[DRAFTED MESSAGE TO SUPPLIER]' to start each section."
    )
    
    response = llm_call(system_prompt)
    return {
        "raw_llm_response": response
    }

# Node 5: Output Generation
def output_generation(state: NegotiatorState) -> Dict[str, Any]:
    raw_response = state["raw_llm_response"]
    
    # Extract report and message using regex/string parsing
    private_report = ""
    supplier_message = ""
    
    # Split on '[DRAFTED MESSAGE TO SUPPLIER]'
    parts = raw_response.split("[DRAFTED MESSAGE TO SUPPLIER]")
    if len(parts) == 2:
        private_report = parts[0].replace("[PRIVATE BUYER REPORT]", "").strip()
        supplier_message = parts[1].strip()
    else:
        # Check lowercase or alternative formatting
        parts_alt = re.split(r"\[?DRAFTED MESSAGE TO SUPPLIER\]?:?", raw_response, flags=re.IGNORECASE)
        if len(parts_alt) == 2:
            private_report = re.sub(r"\[?PRIVATE BUYER REPORT\]?:?", "", parts_alt[0], flags=re.IGNORECASE).strip()
            supplier_message = parts_alt[1].strip()
        else:
            private_report = raw_response
            supplier_message = "No negotiation draft generated."
            
    return {
        "private_report": private_report,
        "supplier_message": supplier_message
    }

def create_negotiator_graph():
    workflow = StateGraph(NegotiatorState)
    
    # Add nodes
    workflow.add_node("ingest", ingest_and_route)
    workflow.add_node("retrieve", mock_retriever)
    workflow.add_node("calculate", deterministic_calculator)
    workflow.add_node("reason", strategic_reasoner)
    workflow.add_node("generate_output", output_generation)
    
    # Add transitions
    workflow.set_entry_point("ingest")
    workflow.add_edge("ingest", "retrieve")
    workflow.add_edge("retrieve", "calculate")
    workflow.add_edge("calculate", "reason")
    workflow.add_edge("reason", "generate_output")
    workflow.add_edge("generate_output", END)
    
    return workflow.compile()

import json
import os
import sys
from negotiator_graph import create_negotiator_graph

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        
    print("=" * 60)
    print("Suproc Fair-Market Negotiator Agent CLI")
    print("=" * 60)
    
    # 1. Check if required files exist
    rfq_path = "rfq.json"
    quote_path = "quote.json"
    db_path = "mock_market_db.json"
    
    missing_files = [f for f in [rfq_path, quote_path, db_path] if not os.path.exists(f)]
    if missing_files:
        print(f"Error: Required files are missing: {', '.join(missing_files)}")
        sys.exit(1)
        
    # 2. Ingest RFQ and Quote data
    try:
        with open(rfq_path, "r") as f:
            rfq = json.load(f)
        with open(quote_path, "r") as f:
            quote = json.load(f)
    except Exception as e:
        print(f"Error parsing input JSON files: {e}")
        sys.exit(1)
        
    print(f"Ingesting RFQ: {rfq['rfq_id']} | Item: {rfq['item']} | Qty: {rfq['quantity']}")
    print(f"Ingesting Quote: {quote['quote_id']} | Supplier Loc: {quote['supplier_location']} | Quoted Price: ₹{quote['total_quoted_price_inr']:,}")
    print("-" * 60)
    
    # 3. Compile and execute LangGraph workflow
    print("Initializing LangGraph State Machine...")
    graph = create_negotiator_graph()
    
    initial_state = {
        "rfq": rfq,
        "quote": quote
    }
    
    print("Executing nodes (Ingest -> Retrieve -> Calculate -> Reason -> Generate)...")
    try:
        final_state = graph.invoke(initial_state)
    except Exception as e:
        print(f"Error executing agent pipeline: {e}")
        sys.exit(1)
        
    print("-" * 60)
    print("Execution complete. Results:")
    print("-" * 60)
    print(f"Retrieved Material Base Cost: ₹{final_state['base_material_cost']:.2f}")
    print(f"Retrieved Labor Multiplier: {final_state['labor_multiplier']}")
    print(f"Retrieved Shipping Cost per Unit: ₹{final_state['shipping_cost_per_unit']:.2f}")
    print(f"Calculated Base Cost per Unit: ₹{final_state['calculated_base_cost_per_unit']:.2f}")
    print(f"Calculated Total Base Cost: ₹{final_state['total_base_cost']:,.2f}")
    print(f"Calculated Supplier Profit Margin: {final_state['supplier_margin']:.2f}%")
    print("=" * 60)
    
    print("Private Buyer Report:")
    print(final_state["private_report"])
    print("-" * 60)
    print("Drafted Message to Supplier:")
    print(final_state["supplier_message"])
    print("=" * 60)

if __name__ == "__main__":
    main()
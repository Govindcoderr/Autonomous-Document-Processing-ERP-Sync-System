# backend/data_validator.py

def validate_invoice_data(data):
    """
    Validate extracted invoice data.
    Compatible with LLM-based extractor.
    Only reject when: important fields missing OR no valid items.
    """


    # 1. Validate top-level fields


    required_fields = ["customer_name", "invoice_date", "reference_number", "items"]

    for field in required_fields:
        if not data.get(field):
            print(f" Missing required field: {field}")
            return None  # STOP: Cannot send to ERP

    # 2. Validate & normalize items
    

    items = data.get("items", [])
    valid_items = []
    total_amount = 0.0

    if not items:
        print(" No items found → Cannot push to ERP")
        return None

    for item in items:
        desc = item.get("description")
        qty = item.get("quantity", 1)   # default quantity
        rate = item.get("rate")

        # LLM already ensures desc and rate exist
        if not desc or rate is None:
            print(f"Skipping invalid item: {item}")
            continue

        try:
            qty = float(str(qty).replace(",", "").strip())
            rate = float(str(rate).replace(",", "").strip())
        except Exception:
            print("Quantity/Rate conversion failed → skipping item")
            continue

        valid_items.append({
            "description": desc.strip(),
            "quantity": qty,
            "rate": rate
        })

        total_amount += qty * rate

    # After filtering:
    if not valid_items:
        print(" No valid items → Cannot push to ERP")
        return None


    # 3. Build final clean structure
 

    data["invoice_number"] = data.get("invoice_number") or "UNKNOWN"
    data["total"] = round(total_amount, 2)
    data["line_items"] = valid_items

    # Remove old field
    data.pop("items", None)

    print(" Validation passed → ready for ERP push")
    return data

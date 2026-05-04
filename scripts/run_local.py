from src.orchestrator.orchestrator import Orchestrator

if __name__ == "__main__":
    orch = Orchestrator()
    result = orch.process_order({"order_id": "ORD-1001", "customer_id": "C-1"})
    print(result)

# signals/generate.py
# Generates trade profiles (entry, target, stop-loss, confidence, hold time)
# from the latest market data using the current model version.
# Downstream: load model, run inference, write rows to signals table.

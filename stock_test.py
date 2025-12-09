print("--- START ---")

import yfinance as yf
print("1. Library Loaded")

# Apple Stock
apple = yf.Ticker("AAPL")
print("2. Downloading Data...")

# Get Data (1 month)
df = apple.history(period="1mo")

# Print Result
print("3. Result:")
print(df)

print("--- END ---")
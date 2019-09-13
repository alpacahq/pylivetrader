# Example MACD Algorithm

This simple example algorithm allocates all of your portfolio to a long position in a stock when its [MACD](https://www.investopedia.com/terms/m/macd.asp) is positive and to a short position when its MACD is negative. This can be considered a momentum-based algorithm, as the MACD indicator will be positive when a stock is doing better than its recent average performance.

If you've already set your Alpaca API information as environment variables, you can run this file with the following command: `pylivetrader run -f macd_example.py`.

# Example Pipeline live Algorithm
In this example code we will be using Alpaca 
[Pipeline-live](https://github.com/alpacahq/pipeline-live) to get a 
"zipline's pipeline" behavior.<br>
we will define a pipeline factor, and screen 5 stocks every day that we
 can buy.<br>
Our pipeline filters out the top 5 AverageDollarVolume shares for today based
 on close price and volume. Then, like in our MACD example we will  allocates a
 long position in a stock when its [MACD](https://www.investopedia.com/terms/m/macd.asp) 
is positive and closes the position when its MACD is negative. <br>This can be 
considered a momentum-based algorithm, as the MACD indicator will be positive 
when a stock is doing better than its recent average performance.

## How to execute it
a nice way to get familiar with the code is to execute it in paper trading mode
* open a terminal and activate the virtual env
* cd into the algorithm's folder
* execute in one of two ways

If you've already set your Alpaca API information as environment variables, you
 can run this file with the following command: 
 `pylivetrader run -f macd_example.py`.
<br>
if you haven't done that just set them in a `config.yaml` file that contains:
```yaml
key_id: <YOUR-API-KEY>
secret: <YOUR-SECRET-KEY>
base_url: https://paper-api.alpaca.markets
```
and execute it like so: `pylivetrader run pipeline_live_example.py
 --backend-config config.yaml`
 
## Using the built-in smoke tool
smoke is used to make sure you don't have any syntax error and to check to
 flow of your algorithm.
 
 you can use the the script called `smoke_pipelinelive.py`
 * you can execute it from the command line:
   * cd into the folder like before
   * run `python smoke_pipelinelive.py` 
 * you can use your IDE to run the `smoke_pipelinelive.py` script and then you could
  debug the algorithm
 
 try both, and learn more about the platform
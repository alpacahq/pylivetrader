# Example Portfolio Manager

Rather than executing trades based on market conditions, this example enforces a 
configurable set of rules on your portfolio using pylivetrader.
 
 In particular, 
it does the following: 
* sets a maximum time that orders can remain open
* sets stop-loss and profit-taking levels
* and sets a maximum percentage of your portfolio that a single position may
 occupy. 
 
 You can see here how to use 
`get_open_orders()` and the `context.portfolio` view to monitor your
 positions in relation to your portfolio as a whole.
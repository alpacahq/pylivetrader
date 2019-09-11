# Local Setup

## Alpaca Configuration

Before running any of these example algorithms, you need to set up your environment for API access. To do that, you can either store your connection information in environment variables or in a config file, as described in this repository's README file. All relevant information can be obtained via the Alpaca dashboard at https://alpaca.markets/.

Note: For paper trading, be sure to grab your information from a dashboard that has been toggled into "Paper" mode, as otherwise it will show you your live account's information.

### Environment Variables

* APCA_API_BASE_URL
* APCA_API_KEY_ID
* APCA_API_SECRET_KEY

### Config File Parameters

* base_url
* key_id
* secret

# Running An Example

If you've saved your API information in `config.yaml`, you can execute an example in pylivetrader like this:

```
pylivetrader run path/to/example.py --backend-config config.yaml
```

If you saved your API information to environment variables, you can omit `--backend-config config.yaml` from the command.

---

Alternatively, you can see instructions for how to run your algorithm with pylivetrader in a docker container [here](https://github.com/alpacahq/pylivetrader/tree/master/examples/heroku-dockerfile).
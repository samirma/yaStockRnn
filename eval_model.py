from providers import OnLineDataProvider
from stock_agent import *
from data_agent import *
from data_util import *
from datetime import datetime
from sklearn.metrics import *

def add_hot_load(minutes, 
                win, 
                total, 
                currency, 
                timestamp_end, 
                verbose, 
                back: BackTest, 
                model_agent: ModelAgent, 
                agent: DataAgent):
                
    model_agent.verbose = False
    back.verbose = False
    online = load_val_data_with_total(minutes = minutes, 
                                        total = total, 
                                        currency_list = [currency],
                                        window = win, 
                                        val_end = timestamp_end)
    x_list, price_list, time_list = online.load_val_data(currency)
    timestamp_start = time_list[0]
    timestamp_end = time_list[-1]
    start = pd.to_datetime(timestamp_start, unit='s')
    end = pd.to_datetime(timestamp_end, unit='s')
    total = len(price_list)
    for idx in range(total):
        price = price_list[idx]
        time = time_list[idx]
        order = [[f"{price}", f"{price}"]]
        amount = 0.0
        agent.process_data(price, amount, time, order, order)
    back.on_down(back.buy_price, back.buy_price)
    if (verbose):
        print(f"###### Past report({total}): {start}({timestamp_start}) - {end}({timestamp_end}) ######")
        back.report()
        print("###### - ######")
    model_agent.verbose = verbose
    back.verbose = verbose

def eval_model(
    model, 
    currency, 
    step, 
    provider: OnLineDataProvider,
    hot_load_total = 100,
    verbose = False):

    valX, valY, times = provider.load_val_data(currency)
    
    x, y, closed_prices = get_sequencial_data(valX, valY, step)

    minutes = provider.minutes
    win = provider.windows()
    agent, back, model_agent = get_agent(minutes = provider.minutes,
                                    win = provider.windows(),
                                    step = step,
                                    currency = currency,
                                    hot_load = False,
                                    model = model,
                                    simulate_on_price = True)
    agent.save_history = True
    add_hot_load(minutes, 
        win = win, 
        total = hot_load_total, 
        currency = currency, 
        timestamp_end = times[-1], 
        verbose = False, 
        back = back, 
        model_agent = model_agent, 
        agent = agent
    )

    #agent.report()
    
    preds = []
    histoty_times = []

    for data in agent.history:
        pred = 0
        if (data.is_up):
            pred = 1
        histoty_times.append(data.timestamp)
        preds.append(pred)

    preds = preds[-(len(y)):]

    metrics = {}
    metrics["recall"] = recall_score(y, preds)
    metrics["precision"] = precision_score(y, preds)
    metrics["f1"] = f1_score(y, preds)
    metrics["accuracy"] = accuracy_score(y, preds)
    metrics["roc_auc"] = roc_auc_score(y, preds)

    back.report()

    return back, metrics    


def get_agent(minutes, 
                win, 
                step,
                model,
                simulate_on_price = False,
                hot_load = True, 
                currency = "btcusd",
                timestamp = int(datetime.timestamp((datetime.now()))),
                verbose = True
                ):
    
    back = BackTest(value = 100,
                        verbose = verbose,
                        pending_sell_steps = step, 
                        sell_on_profit = True)

    request_sell = lambda bid, ask: back.on_down(bid = bid, ask = ask)
    request_buy = lambda bid, ask: back.on_up(bid = bid, ask = ask)

    model_agent = ModelAgent(
        model = model,
        on_down = request_sell,
        on_up = request_buy,
        verbose = verbose
    )

    model_agent.simulate_on_price = simulate_on_price

    on_new_data = lambda x: print(x)
    on_new_data = lambda x: model_agent.on_x(x)

    on_state = lambda timestamp, price, buy, sell: print("{} {} {} {}".format(timestamp, price, buy, sell))
    on_state = lambda timestamp, price, buy, sell: model_agent.on_new_state(timestamp, price, buy, sell)

    agent = DataAgent(
        taProc = TacProcess(), 
        tec = TecAn(windows = win, windows_limit = 100),
        resample = f'{minutes}Min',
        on_state = on_state,
        on_new_data = on_new_data,
        verbose = False
    )
    
    if (hot_load):
        add_hot_load(minutes, 
        win, 
        step, 
        model, 
        currency, 
        timestamp, 
        verbose, 
        back, 
        model_agent, 
        agent)
    back.reset()
    return agent, back, model_agent
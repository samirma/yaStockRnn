import json
import websocket
from time import sleep
from threading import Thread, Lock
import state_util
from numpy import array
from tqdm.notebook import tqdm
import requests
import json
import pandas as pd
import datetime
import numpy as np
import datetime


def get_now_plus_min(min = 2):
    format = "%a %b %d %H:%M:%S %Y"
    today = datetime.datetime.today() + datetime.timedelta(minutes=min)
    return today.strftime(format)

class LiveBitstamp:
    def __init__(self, list_limit, on_list_full = lambda : print("list full")):
        self.trade = {}
        self.raw_states_list = []
        self.last_timestamp = 0
        self.list_limit = list_limit
        self.last_price = 0
        self.last_time = 0
        self.on_list_full = on_list_full
        self.last_raw_state = {}

    def save_trade(self, data):
        self.trade = data

    #Process the raw state
    def process(self, data):
        current_count = len(self.raw_states_list)
        timestamp = data['timestamp']
        if (timestamp != self.last_timestamp):
            self.raw_states_list.append(data)
            if (current_count < self.list_limit):
                if (current_count == 0):
                  self.pbar = tqdm(total=self.list_limit)
                self.pbar.update(1)
                if (current_count == self.list_limit-1):
                  print("Starting prediction verification at {}".format(get_now_plus_min()))
                  self.pbar.close()
            
        self.last_timestamp = timestamp
        if (len(self.raw_states_list) > self.list_limit):
            self.raw_states_list.pop(0)
            self.on_list_full(self.raw_states_list)
            
    
    def trade_callback(self,data):
        self.last_price = data["price"]
        self.save_trade(data)

    def order_book_callback(self, current_state):
        last_trade = self.trade
        should_process = len(last_trade) > 0
        self.last_time = int(current_state['timestamp'])
        if (should_process):
            orders_limit = 19
            current_state["bids"] = current_state["bids"][:orders_limit]
            current_state["asks"] = current_state["asks"][:orders_limit]
            current_state["amount"] = last_trade["amount"]
            current_state["price"] = last_trade["price"]
            self.last_raw_state = current_state
            self.process(current_state)
    
    def start_live(self):
        bt = Bitstamp(self)
        bt.connect
        self.thread = Thread(target=bt.connect)
        self.thread.daemon = True
        self.thread.start()
        

class Bitstamp:
    def __init__(self, liveStates, currency = "btcusd"):
        self.base_url = "wss://ws.bitstamp.net"
        self.trade_ch = "live_trades_" + currency
        self.bookings_ch = "order_book_" + currency
        self.liveStates = liveStates

    def connect(self):
        #websocket.enableTrace(True)

        self.ws = websocket.WebSocketApp(self.base_url,
                                         on_message=self.__on_message,
                                         on_close=self.__on_close,
                                         on_open=self.__on_open,
                                         on_error=self.__on_error)

        self.ws.run_forever()


    def __on_error(self, ws, error):
        print(str(error))

    def __on_open(self, ws):
        print("Bitstamp Websocket Opened.")
        print("Reading form {} and {}".format(self.trade_ch, self.bookings_ch))
        self.subscribe()

    def __on_close(self, ws):
        print("Bitstamp Websocket Closed.")
        if not self.exited:
            self.reconnect()

    def __on_message(self, ws, message):
        try:
            raw_json = json.loads(message)
            channel = raw_json["channel"]
            data = raw_json["data"]
            if (len(data) != 0):
                #print(channel)
                if (channel == self.bookings_ch):
                    #print("pre")
                    self.liveStates.order_book_callback(data)
                    #print("pos")
                if (channel == self.trade_ch):
                    self.liveStates.trade_callback(data)
        except Exception as e: print("Unexpected error:", e)
        

    def isConnected(self):
        return self.ws.sock and self.ws.sock.connected

    def disconnect(self):
        self.exited = True
        self.timer.cancel()
        self.callbacks = {}
        self.ws.close()
        self.logger.info('Bitstamp Websocket Disconnected')

    def reconnect(self):
        if self.ws is not None and self.isConnected():
            self.disconnect()
        self.connect()

    def __restart_ping_timer(self):
        if self.timer.isAlive():
            self.timer.cancel()
        self.timer = Timer(180, self.ping)
        self.timer.start()

    def ping(self):
        self.ws.send('pong')

    def subscribe(self):
        payload = {
            "event": "bts:subscribe",
            "data": {
                "channel": self.trade_ch
            }
        }
        self.ws.send(json.dumps(payload))
        payload = {
            "event": "bts:subscribe",
            "data": {
                "channel": self.bookings_ch
            }
        }
        self.ws.send(json.dumps(payload))
        
        

def load_bitstamp_ohlc(currency_pair, start=-1, end=-1, step=60, limit=5):
    # params:
    #   currency_pair: currency pair on which to trigger the request
    #   start: unix timestamp from when OHLC data will be started
    #   end: unix timestamp to when OHLC data will be shown
    #   step: timeframe in seconds; possible options are:
    #         60, 180, 300, 900, 1800, 3600, 7200, 14400, 21600, 43200, 86400, 259200
    #   limit: limit ohlc results (minimum: 1; maximum: 1000)
    #
    # returns:
    #   pair: trading pair on which the request was made
    #   high: price high
    #   timestamp: unix timestamp date and time
    #   volume: volume
    #   low: price low
    #   close: closing price
    #   open: opening price

    if step not in [60, 180, 300, 900, 1800, 3600, 7200, 14400, 21600, 43200, 86400, 259200]:
        raise Exception('Invalid step: {}'.format(step))

    if not (1 <= limit and limit <= 1000):
        raise Exception('Invalid limit: {}'.format(limit))

    route = 'https://www.bitstamp.net/api/v2/ohlc/{}/'.format(currency_pair)

    payload = {
        'currency_pair': currency_pair,
        'step': step,
        'limit': limit,
    }
    if (start > 0):
        payload['start'] = start

    if (end > 0):
        payload['end'] = end

    print(f"{route} -> {payload}")
    response = requests.get(route, params=payload)
    ohlc = response.json()
    
    
    return ohlc["data"]["ohlc"]


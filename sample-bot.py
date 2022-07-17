#!/usr/bin/env python3
# ~~~~~==============   HOW TO RUN   ==============~~~~~
# 1) Configure things in CONFIGURATION section
# 2) Change permissions: chmod +x sample-bot.py
# 3) Run in loop: while true; do ./sample-bot.py --production; sleep 1; done

import argparse
from collections import deque
from enum import Enum
import time
import socket
import json
import math
import random

# ~~~~~============== CONFIGURATION  ==============~~~~~
# Replace "REPLACEME" with your team name!
team_name = "PILEPERCH"

# ~~~~~============== MAIN LOOP ==============~~~~~

# You should put your code here! We provide some starter code as an example,
# but feel free to change/remove/edit/update any of it as you'd like. If you
# have any questions about the starter code, or what to do next, please ask us!
#
# To help you get started, the sample code below tries to buy BOND for a low
# price, and it prints the current prices for VALE every second. The sample
# code is intended to be a working example, but it needs some improvement
# before it will start making good trades!

symbol_dict = {}
global_variables = {
    "order_id" : 0
}
position_dict = {
    "BOND" : 0,
    "VALBZ" : 0,
    "VALE" : 0,
    "GS" : 0,
    "MS" : 0,
    "WFC" : 0,
    "XLF" : 0
} # symbols : shares
risk_limit_dict = {
    "BOND" : 100, 
    "VALBZ" : 10,
    "VALE" : 10,
    "GS" : 100,
    "MS" : 100,
    "WFC" : 100,
    "XLF" : 100
}

outgoing_vale_orders = []

def maybe_print_new_symbol_data(now, symbol, best_buy_price, best_sell_price):
    symbol_last_print_time = symbol_dict[symbol]["ts"] if symbol in symbol_dict else 0 
    if now > symbol_last_print_time + 1:
        symbol_last_print_time = now
        print(
            {
                symbol + "_best_buy_price": best_buy_price,
                symbol + "_best_sell_price": best_sell_price,
            }
        )

def update_symbol_dict(symbol, best_buy_price, best_sell_price, fair_value, best_buy_price_size, best_sell_price_size):
    now = time.time()
    if symbol not in symbol_dict:
        maybe_print_new_symbol_data(now, symbol, best_buy_price, best_sell_price)
        symbol_dict[symbol] = {
            "best_buy_price": best_buy_price, 
            "best_sell_price": best_sell_price, 
            'ts' : now, 
            'fair_value' : fair_value,
            'best_buy_price_size' : best_buy_price_size,
            'best_sell_price_size' : best_sell_price_size
            }
    else:
        maybe_print_new_symbol_data(now, symbol, best_buy_price, best_sell_price)
        symbol_dict[symbol]["ts"] = now
        symbol_dict[symbol]["best_buy_price"] = best_buy_price
        symbol_dict[symbol]["best_sell_price"] = best_sell_price
        symbol_dict[symbol]["fair_value"] = fair_value
        symbol_dict[symbol]["best_buy_price_size"] = best_buy_price_size
        symbol_dict[symbol]["best_sell_price_size"] = best_sell_price_size
    

def update_symbol_dict_with_message(message):
    def best_price(side):
        if message[side]:
            return message[side][0][0]
    def best_price_size(side):
        if message[side]:
            return message[side][0][1]

    best_buy_price = best_price("buy")
    best_sell_price = best_price("sell")
    best_buy_price_size = best_price_size("buy")
    best_sell_price_size = best_price_size("sell")
    fair_value = calculate_fair_value(message, best_buy_price, best_sell_price)
    update_symbol_dict(message['symbol'], best_buy_price, best_sell_price, fair_value, best_buy_price_size, best_sell_price_size)

def getCurrentBuyPrice(best_sell_price, fair_value):
    if best_sell_price is None:
        return None
    curr_buy_price = best_sell_price + 1
    if curr_buy_price >= fair_value:
        return None
    return curr_buy_price

def getCurrentSellPrice(best_buy_price, fair_value):
    if best_buy_price is None:
        return None
    curr_sell_price = best_buy_price - 1
    if curr_sell_price <= fair_value:
        return None
    return curr_sell_price

def calculate_fair_value(message, best_buy_price, best_sell_price):
    if message["symbol"] == "BOND":
        return 1000
    if best_buy_price and best_sell_price:
        return (best_buy_price + best_sell_price) / 2
    return best_buy_price or best_sell_price

# less-liquid is vale 
# more liquid is valbz
# vale -> valbz
# checks fair value where we use valbz size and best buy price and check if vale sell is less than valbz buy
# we want valbz's best buy price to be less than vale's best sell price
def check_arb(symbol_x, symbol_y, size_x, size_y, conversion_cost, exchange):
    if symbol_x not in symbol_dict or symbol_y not in symbol_dict:
        return False
    if symbol_dict[symbol_y]["best_buy_price"] is None or symbol_dict[symbol_x]["best_sell_price"] is None:
        return False
    # arb based on size
    # if symbol_dict[symbol_y]["best_buy_price"] * size_y > symbol_dict[symbol_x]["best_sell_price"] * size_x + conversion_cost:
    if symbol_dict[symbol_y]["best_buy_price"] > symbol_dict[symbol_x]["best_sell_price"] + conversion_cost:
        # TODO(chris): buy symbol y and convert and sell symbol x 
        #              more liquidity means that price is more accurate - probably hold more liquid symbol
        exchange.send_add_message(global_variables["order_id"], symbol=symbol_x, dir=Dir.BUY, price=symbol_dict[symbol_x]["best_sell_price"], size = size_x) # buy vale
        global_variables["order_id"] += 1
        print(f"Sent buy order for {symbol_x} at a size of {size_x}")
        exchange.send_convert_message(global_variables["order_id"], symbol=symbol_x, dir=Dir.SELL, size = size_x) # convert vale -> valbz
        print(f"Sent convert order for {symbol_x} to {symbol_y} at a size of {size_x}")
        global_variables["order_id"] += 1
        exchange.send_add_message(global_variables["order_id"], symbol=symbol_y, dir=Dir.SELL, price=symbol_dict[symbol_y]["best_buy_price"], size=size_x) # sell valbz
        print(f"Sent sell order for {symbol_y} at a size of {size_x}")
        global_variables["order_id"] += 1

def check_buy_price_exists(lst):
    for item in lst:
        if item not in symbol_dict or symbol_dict[item]["best_buy_price"] is None:
            return False
    return True

def check_spread_exists(lst):
    for item in lst:
        if item not in symbol_dict or symbol_dict[item]["best_buy_price"] is None or symbol_dict[item]["best_sell_price"] is None:
            return False
    return True


def xlf_to_basket(size, conversion_cost, exchange):    
    if not check_buy_price_exists(["BOND", "GS", "MS", "WFC"]):
        return False
    
    if symbol_dict["XLF"]["best_sell_price"] is None:
        return False

    weighted_sum = 3 * symbol_dict["BOND"]["best_buy_price"] + 2 * symbol_dict["GS"]["best_buy_price"] + 3 * symbol_dict["MS"]["best_buy_price"] + 2 * symbol_dict["WFC"]["best_buy_price"]
    weighted_sum /= 10
    print("Weighted_sum: ", weighted_sum * size)
    print("xlf best sell price: ", symbol_dict["XLF"]["best_sell_price"] * size + conversion_cost)
    if symbol_dict["XLF"]["best_sell_price"] * size + conversion_cost < weighted_sum * size:
        # TODO(chris): fix the sizing
        exchange.send_add_message(global_variables["order_id"], symbol="XLF", dir=Dir.BUY, price = symbol_dict["XLF"]["best_sell_price"], size = size)
        global_variables["order_id"] += 1
        exchange.send_convert_message(global_variables["order_id"], symbol="XLF", dir=Dir.SELL, size = size)
        print(f"Sent convert buy order for {'XLF'} at a size of {size}")
        global_variables["order_id"] += 1
        exchange.send_add_message(global_variables["order_id"], symbol="BOND", dir=Dir.SELL, price=symbol_dict["BOND"]["best_buy_price"], size=int(size * 0.3))
        print(f"Sent convert sell order for {'BOND'} at a size of {int(size * 0.3)}")
        exchange.send_add_message(global_variables["order_id"], symbol="GS", dir=Dir.SELL, price=symbol_dict["GS"]["best_buy_price"], size=int(size * 0.2))
        print(f"Sent convert sell order for {'GS'} at a size of {int(size * 0.2)}")
        exchange.send_add_message(global_variables["order_id"], symbol="MS", dir=Dir.SELL, price=symbol_dict["MS"]["best_buy_price"], size=int(size * 0.3))
        print(f"Sent convert sell order for {'MS'} at a size of {int(size * 0.3)}")
        exchange.send_add_message(global_variables["order_id"], symbol="WFC", dir=Dir.SELL, price=symbol_dict["WFC"]["best_buy_price"], size=int(size * 0.2))
        print(f"Sent convert sell order for {'WFC'} at a size of {int(size * 0.2)}")
        global_variables["order_id"] += 1

def initiate_bid_ask_arb(symbol_ll, symbol_ml, exchange):
    if not check_spread_exists([symbol_ll, symbol_ml]):
        return False
    if symbol_dict[symbol_ll]["best_sell_price"] > symbol_dict[symbol_ml]["best_sell_price"] and symbol_dict[symbol_ll]["best_buy_price"] < symbol_dict[symbol_ml]["best_buy_price"] and position_dict[symbol_ll] < risk_limit_dict[symbol_ll]:
        for i in range(5):
            exchange.send_add_message(global_variables["order_id"], symbol=symbol_ll, dir=Dir.BUY, price=symbol_dict[symbol_ll]["best_buy_price"] + random.randint(1, symbol_dict[symbol_ml]["best_buy_price"] - symbol_dict[symbol_ll]["best_buy_price"]), size=1)
            outgoing_vale_orders.append(global_variables["order_id"])
            global_variables["order_id"] += 1
            print(f"Sent buy order for {'VALE'} at a size of {1}")
        return True

def finish_bid_ask_arb(symbol_ll, symbol_ml, exchange):
    if not check_buy_price_exists([symbol_ml]):
        return False

    print(f"Finishing bid ask arb for {symbol_ll} to {symbol_ml}")
    exchange.send_convert_message(global_variables["order_id"], symbol=symbol_ll, dir=Dir.SELL, size = 1) # convert vale -> valbz
    global_variables["order_id"] += 1
    exchange.send_add_message(global_variables["order_id"], symbol=symbol_ml, dir=Dir.SELL, price=symbol_dict[symbol_ml]["best_buy_price"], size=1)
    global_variables["order_id"] += 1

def maybe_buy_symbol(best_sell_price, curr_buy_price, fair_value, best_sell_price_size, exchange, symbol):
    if best_sell_price and curr_buy_price and best_sell_price < fair_value and position_dict[symbol] + best_sell_price_size < risk_limit_dict[symbol]: # person willing to sell bond for less than fair value
        order_id = global_variables["order_id"]
        print(f"Order ID {order_id}: buying at {curr_buy_price} at size of {best_sell_price_size}")
        exchange.send_add_message(global_variables["order_id"], symbol=symbol, dir=Dir.BUY, price=curr_buy_price, size=best_sell_price_size)
        position_dict[symbol] += best_sell_price_size
        global_variables["order_id"] += 1

def maybe_sell_symbol(best_buy_price, curr_sell_price, fair_value, best_buy_price_size, exchange, symbol):
    if best_buy_price and curr_sell_price and best_buy_price > fair_value and position_dict[symbol] - best_buy_price_size > -risk_limit_dict[symbol]: # sell if someone is willing to buy for more than fair value
        order_id = global_variables["order_id"]
        print(f"Order ID {order_id}: selling at {curr_sell_price} at size of {best_buy_price_size}")
        exchange.send_add_message(global_variables["order_id"], symbol=symbol, dir=Dir.SELL, price=curr_sell_price, size=best_buy_price_size)
        position_dict[symbol] -= best_buy_price_size
        global_variables["order_id"] += 1

def maybe_trade_symbol(message, exchange, symbol):
    fair_value = symbol_dict[symbol]["fair_value"]
    best_buy_price = symbol_dict[symbol]["best_buy_price"]
    best_buy_price_size = symbol_dict[symbol]["best_buy_price_size"]
    best_sell_price = symbol_dict[symbol]["best_sell_price"]
    best_sell_price_size = symbol_dict[symbol]["best_sell_price_size"]

    curr_buy_price = getCurrentBuyPrice(best_sell_price, fair_value)
    curr_sell_price = getCurrentSellPrice(best_buy_price, fair_value)
        
    # Normal buying
    maybe_buy_symbol(best_sell_price, curr_buy_price, fair_value, best_sell_price_size, exchange, symbol)
    # Normal selling 
    maybe_sell_symbol(best_buy_price, curr_sell_price, fair_value, best_buy_price_size, exchange, symbol)
    # Checking arbitrarge opportunities
    if message["symbol"] == "VALE":
        if "VALBZ" in symbol_dict:
            check_arb("VALE", "VALBZ", best_buy_price_size, symbol_dict["VALBZ"]["best_sell_price_size"], 10, exchange)
    if message["symbol"] == "VALBZ":
        if "VALE" in symbol_dict:
            check_arb("VALBZ", "VALE", best_buy_price_size, symbol_dict["VALE"]["best_sell_price_size"], 10, exchange)
    if message["symbol"] == "XLF":
        if best_sell_price_size:
            xlf_to_basket(math.ceil(best_sell_price_size/10)*10, 100, exchange)

    # Hold less liquid positions
    initiate_bid_ask_arb("VALE", "VALBZ", exchange)

def main():
    args = parse_arguments()

    exchange = ExchangeConnection(args=args)

    # Store and print the "hello" message received from the exchange. This
    # contains useful information about your positions. Normally you start with
    # all positions at zero, but if you reconnect during a round, you might
    # have already bought/sold symbols and have non-zero positions.
    hello_message = exchange.read_message()
    print("First message from exchange:", hello_message)

    # Send an order for BOND at a good price, but it is low enough that it is
    # unlikely it will be traded against. Maybe there is a better price to
    # pick? Also, you will need to send more orders over time.
    # exchange.send_add_message(order_id=1, symbol="BOND", dir=Dir.BUY, price=990, size=1)

    # Set up some variables to track the bid and ask price of a symbol. Right
    # now this doesn't track much information, but it's enough to get a sense
    # of the VALE market.
    vale_best_buy_price, vale_best_sell_price = None, None
    vale_last_print_time = time.time()

    # Here is the main loop of the program. It will continue to read and
    # process messages in a loop until a "close" message is received. You
    # should write to code handle more types of messages (and not just print
    # the message). Feel free to modify any of the starter code below.
    #
    # Note: a common mistake people make is to call write_message() at least
    # once for every read_message() response.
    #
    # Every message sent to the exchange generates at least one response
    # message. Sending a message in response to every exchange message will
    # cause a feedback loop where your bot's messages will quickly be
    # rate-limited and ignored. Please, don't do that!
    trade_set = ["BOND", "VALE", "XLF", "GS", "MS", "WFC"]
    while True:
        message = exchange.read_message()

        # Some of the message types below happen infrequently and contain
        # important information to help you understand what your bot is doing,
        # so they are printed in full. We recommend not always printing every
        # message because it can be a lot of information to read. Instead, let
        # your code handle the messages and just print the information
        # important for you!
        if message["type"] == "close":
            print("The round has ended")
            break
        elif message["type"] == "error":
            print(message)
        elif message["type"] == "reject":
            print(message)
        elif message["type"] == "fill":
            print(message)
        elif message["type"] == "book":
            update_symbol_dict_with_message(message)
            # Buy the bond if the fair_value < 1000
            if message["symbol"] in trade_set:
                maybe_trade_symbol(message, exchange, message["symbol"])
        elif message["type"] == "out":
            print(message)
            if message["order_id"] in outgoing_vale_orders:
                position_dict["VALE"] += 1
                finish_bid_ask_arb("VALE", "VALBZ", exchange)
                outgoing_vale_orders.remove(message["order_id"])            


# ~~~~~============== PROVIDED CODE ==============~~~~~

# You probably don't need to edit anything below this line, but feel free to
# ask if you have any questions about what it is doing or how it works. If you
# do need to change anything below this line, please feel free to


class Dir(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class ExchangeConnection:
    def __init__(self, args):
        self.message_timestamps = deque(maxlen=500)
        self.exchange_hostname = args.exchange_hostname
        self.port = args.port
        self.exchange_socket = self._connect(add_socket_timeout=args.add_socket_timeout)

        self._write_message({"type": "hello", "team": team_name.upper()})

    def read_message(self):
        """Read a single message from the exchange"""
        message = json.loads(self.exchange_socket.readline())
        if "dir" in message:
            message["dir"] = Dir(message["dir"])
        return message

    def send_add_message(self, order_id: int, symbol: str, dir: Dir, price: int, size: int):
        """Add a new order"""
        self._write_message(
            {
                "type": "add",
                "order_id": order_id,
                "symbol": symbol,
                "dir": dir,
                "price": price,
                "size": size,
            }
        )

    def send_convert_message(self, order_id: int, symbol: str, dir: Dir, size: int):
        """Convert between related symbols"""
        self._write_message(
            {
                "type": "convert",
                "order_id": order_id,
                "symbol": symbol,
                "dir": dir,
                "size": size,
            }
        )

    def send_cancel_message(self, order_id: int):
        """Cancel an existing order"""
        self._write_message({"type": "cancel", "order_id": order_id})

    def _connect(self, add_socket_timeout):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        if add_socket_timeout:
            # Automatically raise an exception if no data has been recieved for
            # multiple seconds. This should not be enabled on an "empty" test
            # exchange.
            s.settimeout(5)
        s.connect((self.exchange_hostname, self.port))
        return s.makefile("rw", 1)

    def _write_message(self, message):
        json.dump(message, self.exchange_socket)
        self.exchange_socket.write("\n")

        now = time.time()
        self.message_timestamps.append(now)
        if len(
            self.message_timestamps
        ) == self.message_timestamps.maxlen and self.message_timestamps[0] > (now - 1):
            print(
                "WARNING: You are sending messages too frequently. The exchange will start ignoring your messages. Make sure you are not sending a message in response to every exchange message."
            )


def parse_arguments():
    test_exchange_port_offsets = {"prod-like": 0, "slower": 1, "empty": 2}

    parser = argparse.ArgumentParser(description="Trade on an ETC exchange!")
    exchange_address_group = parser.add_mutually_exclusive_group(required=True)
    exchange_address_group.add_argument(
        "--production", action="store_true", help="Connect to the production exchange."
    )
    exchange_address_group.add_argument(
        "--test",
        type=str,
        choices=test_exchange_port_offsets.keys(),
        help="Connect to a test exchange.",
    )

    # Connect to a specific host. This is only intended to be used for debugging.
    exchange_address_group.add_argument(
        "--specific-address", type=str, metavar="HOST:PORT", help=argparse.SUPPRESS
    )

    args = parser.parse_args()
    args.add_socket_timeout = True

    if args.production:
        args.exchange_hostname = "production"
        args.port = 25000
    elif args.test:
        args.exchange_hostname = "test-exch-" + team_name
        args.port = 25000 + test_exchange_port_offsets[args.test]
        if args.test == "empty":
            args.add_socket_timeout = False
    elif args.specific_address:
        args.exchange_hostname, port = args.specific_address.split(":")
        args.port = int(port)

    return args


if __name__ == "__main__":
    # Check that [team_name] has been updated.
    assert (
        team_name != "REPLACEME"
    ), "Please put your team name in the variable [team_name]."

    main()

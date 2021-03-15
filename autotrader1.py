import asyncio
import itertools
import numpy as np

from typing import List

from ready_trader_one import BaseAutoTrader, Instrument, Lifespan, Side


LOT_SIZE = 100
POSITION_LIMIT = 1000
TICK_SIZE_IN_CENTS = 100


class AutoTrader(BaseAutoTrader):
    """Example Auto-trader.

    When it starts this auto-trader places ten-lot bid and ask orders at the
    current best-bid and best-ask prices respectively. Thereafter, if it has
    a long position (it has bought more lots than it has sold) it reduces its
    bid and ask prices. Conversely, if it has a short position (it has sold
    more lots than it has bought) then it increases its bid and ask prices.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop, team_name: str, secret: str):
        """Initialise a new instance of the AutoTrader class."""
        super().__init__(loop, team_name, secret)
        self.order_ids = itertools.count(1)
        self.bids = set()
        self.asks = set()
        self.hit_order = set()
        self.ask_id = self.ask_price = self.bid_id = self.bid_price = self.position = 0

        self.etf_bid_prices = [0]
        self.etf_bid_volumes = [0]
        self.etf_ask_prices = [0]
        self.etf_ask_volumes = [0]
        
        self.futures_bid_prices = [0]
        self.futures_bid_volumes = [0]
        self.futures_ask_prices = [0]
        self.futures_ask_volumes = [0]
        

    def on_error_message(self, client_order_id: int, error_message: bytes) -> None:
        """Called when the exchange detects an error.

        If the error pertains to a particular order, then the client_order_id
        will identify that order, otherwise the client_order_id will be zero.
        """
        self.logger.warning("error with order %d: %s", client_order_id, error_message.decode())
        if client_order_id != 0:
            self.on_order_status_message(client_order_id, 0, 0, 0)

    def average_price(self, price, volume):
        a = np.array(volume)
        return int(sum((a / a.sum()) * np.array(price)))
            
    def on_order_book_update_message(self, instrument: int, sequence_number: int, ask_prices: List[int],
                                     ask_volumes: List[int], bid_prices: List[int], bid_volumes: List[int]) -> None:
        """Called periodically to report the status of an order book.

        The sequence number can be used to detect missed or out-of-order
        messages. The five best available ask (i.e. sell) and bid (i.e. buy)
        prices are reported along with the volume available at each of those
        price levels.
        """
        
        if instrument == Instrument.ETF:
            self.etf_bid_prices = bid_prices
            self.etf_bid_volumes = bid_volumes
            self.etf_ask_prices = ask_prices
            self.etf_ask_volumes = ask_volumes
        
        if instrument == Instrument.FUTURE:
            self.futures_bid_prices = bid_prices
            self.futures_bid_volumes = bid_volumes
            self.futures_ask_prices = ask_prices
            self.futures_ask_volumes = ask_volumes
            
        if (instrument == Instrument.FUTURE) and self.futures_bid_prices[0] != 0 and self.etf_bid_prices[0] != 0:
#            new_bid_price = 100*round(self.average_price(bid_prices, bid_volumes)/100) if bid_prices[0] != 0 else 0
#            new_ask_price = 100*round(self.average_price(ask_prices, ask_volumes)/100) if ask_prices[0] != 0 else 0

            if ((ask_prices[0] - bid_prices[0])/100) > 2:
                new_bid_price = bid_prices[0] + 100
                new_ask_price = ask_prices[0] - 100
#            price_adjustment = - (self.position // LOT_SIZE) * TICK_SIZE_IN_CENTS
#            new_bid_price = bid_prices[0] + price_adjustment if bid_prices[0] != 0 else 0
#            new_ask_price = ask_prices[0] + price_adjustment if ask_prices[0] != 0 else 0
            
            if self.bid_id != 0 and new_bid_price not in (self.bid_price, 0):
                self.send_cancel_order(self.bid_id)
                self.bid_id = 0
            if self.ask_id != 0 and new_ask_price not in (self.ask_price, 0):
                self.send_cancel_order(self.ask_id)
                self.ask_id = 0

            if self.bid_id == 0 and new_bid_price != 0 and self.position < POSITION_LIMIT:
                self.execute_trade(Side.BUY, new_bid_price)
#                self.bid_id = next(self.order_ids)
#                self.bid_price = new_bid_price
#                self.send_insert_order(self.bid_id, Side.BUY, new_bid_price, LOT_SIZE, Lifespan.GOOD_FOR_DAY)
#                self.bids.add(self.bid_id)

            if self.ask_id == 0 and new_ask_price != 0 and self.position > -POSITION_LIMIT:
                self.execute_trade(Side.SELL, new_ask_price)
                
#                self.ask_id = next(self.order_ids)
#                self.ask_price = new_ask_price
#                self.send_insert_order(self.ask_id, Side.SELL, new_ask_price, LOT_SIZE, Lifespan.GOOD_FOR_DAY)
#                self.asks.add(self.ask_id)

    def execute_trade(self, side, price, hedge = False, amount=LOT_SIZE, lifespan=Lifespan.GOOD_FOR_DAY):
        order_id = next(self.order_ids)      
        if side == Side.SELL:
            print("Hi Sell")
            if hedge == False:
                self.ask_id = order_id
            self.send_insert_order(order_id, Side.SELL, price, amount, lifespan)
            self.asks.add(self.ask_id)
        elif side == Side.BUY:
            print(order_id, price, amount, lifespan)
            if hedge == False:
                self.bid_id = order_id
            self.send_insert_order(order_id, Side.BUY, price, amount, lifespan)
            self.bids.add(self.bid_id)
        else:
            print("Lol idiot check ur side")
        print("Exevuted lol")
    
    def find_midpoint(self, bid_price, bid_volume, ask_price, ask_volume, weighted=False):
        if weighted == False:
            return 100*round((ask_price[0] - bid_price[0])/200)
        else:
            bid_side = self.average_price(bid_price, bid_volume)
            ask_side = self.average_price(ask_price, ask_volume)
            return 100*round((ask_side - bid_side)/200)
    
    def on_order_filled_message(self, client_order_id: int, price: int, volume: int) -> None:
        """Called when when of your orders is filled, partially or fully.

        The price is the price at which the order was (partially) filled,
        which may be better than the order's limit price. The volume is
        the number of lots filled at that price.
        """
        if client_order_id in self.bids:
            self.position += volume
            weighted_sell = self.average_price(self.etf_ask_prices, self.etf_ask_volumes)
            
            if weighted_sell > price:
                self.execute_trade(Side.SELL, weighted_sell, hedge = True, amount = volume)
            else:
                self.execute_trade(Side.SELL, self.etf_ask_prices[0], hedge = True, amount = volume)
            
            
#            self.ask_id = next(self.order_ids)
#            self.ask_price = new_ask_price
#            self.send_insert_order(self.ask_id, Side.SELL, new_ask_price, LOT_SIZE, Lifespan.GOOD_FOR_DAY)
#            self.asks.add(self.ask_id)
            
        elif client_order_id in self.asks:
            self.position -= volume
            print(self.etf_bid_prices, self.etf_bid_volumes)
            weighted_bid = self.average_price(self.etf_bid_prices, self.etf_bid_volumes)
            if weighted_bid < price:
                self.execute_trade(Side.BUY, weighted_bid, hedge = True, amount = volume)
            else:
                self.execute_trade(Side.BUY, self.etf_bid_prices[0], hedge = True, amount = volume)

            
            

    def on_order_status_message(self, client_order_id: int, fill_volume: int, remaining_volume: int,
                                fees: int) -> None:
        """Called when the status of one of your orders changes.

        The fill_volume is the number of lots already traded, remaining_volume
        is the number of lots yet to be traded and fees is the total fees for
        this order. Remember that you pay fees for being a market taker, but
        you receive fees for being a market maker, so fees can be negative.

        If an order is cancelled its remaining volume will be zero.
        """
        if remaining_volume == 0:
            if client_order_id == self.bid_id:
                self.bid_id = 0
            elif client_order_id == self.ask_id:
                self.ask_id = 0

            # It could be either a bid or an ask
            self.bids.discard(client_order_id)
            self.asks.discard(client_order_id)

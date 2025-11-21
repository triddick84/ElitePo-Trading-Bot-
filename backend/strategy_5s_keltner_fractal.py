"""
5-Second Keltner Channel and Fractal Strategy
User-Requested Strategy for Pocket Option

Keltner Channel Settings:
- EMA Period: 10
- ATR Period: 10
- Multiplier: 2

Fractal Indicator Settings:
- Period: 2

Buy Signal: Candle closes outside/near bottom of Keltner lower band + Fractal reversal up
Sell Signal: Candle closes outside/near top of Keltner upper band + Fractal reversal down

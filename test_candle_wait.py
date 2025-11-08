#!/usr/bin/env python3
"""
Test script to verify the candle waiting functionality
"""
import asyncio
import sys
import os
sys.path.append('/app/backend')

from force_signal_generator import ForceSignalGenerator
from models import MarketData, AssetType
from datetime import datetime

async def test_candle_wait():
    """Test the candle waiting functionality"""
    print("🧪 Testing candle waiting functionality...")
    
    # Create test market data
    test_market_data = MarketData(
        symbol="EURUSD",
        asset_type=AssetType.FOREX,
        price=1.0850,
        timestamp=datetime.now(),
        volume=1000
    )
    
    # Create force signal generator
    generator = ForceSignalGenerator()
    
    # Test 1: With candle waiting (default)
    print("\n📊 Test 1: Force generate with candle waiting (wait_for_candle=True)")
    start_time = datetime.now()
    
    try:
        signals = await generator.force_generate_signal(
            symbol="EURUSD",
            market_data=test_market_data,
            user_timeframes=["5s"],
            chart_type="japanese_candles",
            wait_for_candle=True
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print(f"✅ Generated {len(signals)} signals in {duration:.2f} seconds")
        if signals:
            signal = signals[0]
            print(f"   Signal: {signal.direction.value} for {signal.symbol}")
            print(f"   Confidence: {signal.probability:.1f}%")
            print(f"   Timeframe: {signal.timeframe}")
            
    except Exception as e:
        print(f"❌ Error in test 1: {e}")
    
    # Test 2: Without candle waiting
    print("\n📊 Test 2: Force generate without candle waiting (wait_for_candle=False)")
    start_time = datetime.now()
    
    try:
        signals = await generator.force_generate_signal(
            symbol="EURUSD",
            market_data=test_market_data,
            user_timeframes=["5s"],
            chart_type="japanese_candles",
            wait_for_candle=False
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print(f"✅ Generated {len(signals)} signals in {duration:.2f} seconds")
        if signals:
            signal = signals[0]
            print(f"   Signal: {signal.direction.value} for {signal.symbol}")
            print(f"   Confidence: {signal.probability:.1f}%")
            print(f"   Timeframe: {signal.timeframe}")
            
    except Exception as e:
        print(f"❌ Error in test 2: {e}")
    
    print("\n🎉 Candle waiting functionality test completed!")

if __name__ == "__main__":
    asyncio.run(test_candle_wait())
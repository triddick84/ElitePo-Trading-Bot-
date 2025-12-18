#!/usr/bin/env python3
"""
Direct test of the PROVEN 5s strategy to see if it's working
"""

import sys
sys.path.append('/app/backend')

from proven_5s_strategy import get_proven_5s_strategy, generate_proven_5s_signal

def test_proven_strategy_direct():
    """Test the PROVEN 5s strategy directly"""
    print("🎯 Testing PROVEN 5s Strategy Directly")
    print("=" * 50)
    
    try:
        # Get strategy instance
        strategy = get_proven_5s_strategy()
        print(f"✅ Strategy instance created successfully")
        
        # Test signal generation for EURUSD
        print(f"🚀 Testing signal generation for EURUSD...")
        result = strategy.generate_signal('EURUSD')
        
        if result:
            print(f"✅ Signal generated successfully!")
            print(f"   Direction: {result.get('direction')}")
            print(f"   Confidence: {result.get('confidence')}%")
            print(f"   Strategy: {result.get('strategy')}")
            
            # Check for support_resistance data
            tech_analysis = result.get('technical_analysis', {})
            if 'support_resistance' in tech_analysis:
                print(f"✅ Support/Resistance data present")
                sr_data = tech_analysis['support_resistance']
                print(f"   Nearest support: {sr_data.get('nearest_support')}")
                print(f"   Nearest resistance: {sr_data.get('nearest_resistance')}")
            else:
                print(f"❌ Support/Resistance data missing")
                
        else:
            print(f"ℹ️ No signal generated (market conditions may not meet criteria)")
            
        # Test convenience function
        print(f"\n🔧 Testing convenience function...")
        result2 = generate_proven_5s_signal('EURUSD')
        
        if result2:
            print(f"✅ Convenience function works!")
            print(f"   Direction: {result2.get('direction')}")
            print(f"   Confidence: {result2.get('confidence')}%")
        else:
            print(f"ℹ️ Convenience function: No signal generated")
            
        return True
        
    except Exception as e:
        print(f"❌ Error testing PROVEN strategy: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = test_proven_strategy_direct()
    print(f"\n{'✅ SUCCESS' if success else '❌ FAILED'}")
"""
Test Pocket Option WebSocket Connection
Uses fresh auth data provided by user
"""
import asyncio
import logging
import sys
from pocket_option_v2 import PocketOptionV2

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_connection():
    """Test connection with fresh auth data"""
    
    # Fresh auth data from user's browser
    ssid = "A4zP7dZSXxYCq0X5z"
    uid = 53953294
    is_demo = True  # User is using demo account
    
    logger.info("=" * 80)
    logger.info("🔧 POCKET OPTION CONNECTION TEST")
    logger.info("=" * 80)
    logger.info(f"📋 SSID: {ssid}")
    logger.info(f"👤 UID: {uid}")
    logger.info(f"🎮 Mode: {'DEMO' if is_demo else 'LIVE'}")
    logger.info("=" * 80)
    
    # Create client instance
    client = PocketOptionV2(ssid, uid, is_demo)
    
    try:
        # Attempt connection
        logger.info("🔌 Attempting to connect...")
        connected = await client.connect()
        
        if connected:
            logger.info("=" * 80)
            logger.info("✅ CONNECTION SUCCESSFUL!")
            logger.info("=" * 80)
            
            # Get balance
            logger.info("💰 Fetching balance...")
            balance = await client.get_balance()
            logger.info(f"💵 Balance: ${balance:.2f}")
            
            # Test getting candles
            logger.info("\n📊 Testing candle data retrieval...")
            test_assets = ['EURUSD_otc', 'BTCUSD']
            
            for asset in test_assets:
                logger.info(f"\n🔍 Fetching candles for {asset}...")
                candles = await client.get_candles(asset, 60, 5)
                
                if candles:
                    logger.info(f"✅ Retrieved {len(candles)} candles for {asset}")
                    logger.info(f"   Latest candle: {candles[-1] if candles else 'None'}")
                else:
                    logger.warning(f"⚠️ No candles retrieved for {asset}")
            
            # Disconnect
            logger.info("\n👋 Disconnecting...")
            await client.disconnect()
            
            logger.info("=" * 80)
            logger.info("✅ TEST COMPLETED SUCCESSFULLY")
            logger.info("=" * 80)
            return True
            
        else:
            logger.error("=" * 80)
            logger.error("❌ CONNECTION FAILED")
            logger.error("=" * 80)
            logger.error("Possible reasons:")
            logger.error("1. SSID has expired (session timed out)")
            logger.error("2. UID mismatch")
            logger.error("3. Network/firewall issues")
            logger.error("4. Wrong server region")
            logger.error("\n💡 Solution: Extract fresh auth message from browser DevTools")
            return False
            
    except Exception as e:
        logger.error("=" * 80)
        logger.error("❌ TEST FAILED WITH ERROR")
        logger.error("=" * 80)
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_connection())
    sys.exit(0 if result else 1)

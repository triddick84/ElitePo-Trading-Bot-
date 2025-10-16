"""
Chart Type Transformations for Pocket Option
Supports: Japanese Candles, Line, Bars, Heikin Ashi
"""

import pandas as pd
import numpy as np
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class ChartTransformations:
    """
    Transform market data into different chart types for signal generation
    """
    
    @staticmethod
    def to_japanese_candles(df: pd.DataFrame) -> pd.DataFrame:
        """
        Standard Japanese candlesticks (OHLC)
        No transformation needed - this is the base format
        """
        return df.copy()
    
    @staticmethod
    def to_line_chart(df: pd.DataFrame) -> pd.DataFrame:
        """
        Line chart - uses only close prices
        Transforms OHLC to a line by setting all values to Close
        """
        line_df = df.copy()
        line_df['Open'] = line_df['Close']
        line_df['High'] = line_df['Close']
        line_df['Low'] = line_df['Close']
        
        logger.info(f"Transformed to Line chart: {len(line_df)} points")
        return line_df
    
    @staticmethod
    def to_bars(df: pd.DataFrame) -> pd.DataFrame:
        """
        Bar chart - same as Japanese candles but different visual representation
        Data structure remains OHLC
        """
        return df.copy()
    
    @staticmethod
    def to_heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
        """
        Heikin Ashi Candles - Smoothed candlesticks for trend identification
        
        Formula:
        - HA Close = (Open + High + Low + Close) / 4
        - HA Open = (Previous HA Open + Previous HA Close) / 2
        - HA High = Max(High, HA Open, HA Close)
        - HA Low = Min(Low, HA Open, HA Close)
        
        Benefits:
        - Filters out market noise
        - Better trend identification
        - Smoother price action
        """
        ha_df = df.copy()
        
        # Initialize Heikin Ashi columns
        ha_df['HA_Close'] = (ha_df['Open'] + ha_df['High'] + ha_df['Low'] + ha_df['Close']) / 4
        ha_df['HA_Open'] = 0.0
        ha_df['HA_High'] = 0.0
        ha_df['HA_Low'] = 0.0
        
        # Calculate HA Open (requires previous values)
        for i in range(len(ha_df)):
            if i == 0:
                # First candle: HA Open = (Open + Close) / 2
                ha_df.loc[ha_df.index[i], 'HA_Open'] = (ha_df.loc[ha_df.index[i], 'Open'] + 
                                                         ha_df.loc[ha_df.index[i], 'Close']) / 2
            else:
                # Subsequent candles: HA Open = (Previous HA Open + Previous HA Close) / 2
                ha_df.loc[ha_df.index[i], 'HA_Open'] = (ha_df.loc[ha_df.index[i-1], 'HA_Open'] + 
                                                         ha_df.loc[ha_df.index[i-1], 'HA_Close']) / 2
            
            # Calculate HA High and Low
            ha_open = ha_df.loc[ha_df.index[i], 'HA_Open']
            ha_close = ha_df.loc[ha_df.index[i], 'HA_Close']
            high = ha_df.loc[ha_df.index[i], 'High']
            low = ha_df.loc[ha_df.index[i], 'Low']
            
            ha_df.loc[ha_df.index[i], 'HA_High'] = max(high, ha_open, ha_close)
            ha_df.loc[ha_df.index[i], 'HA_Low'] = min(low, ha_open, ha_close)
        
        # Replace standard OHLC with Heikin Ashi values
        ha_df['Open'] = ha_df['HA_Open']
        ha_df['High'] = ha_df['HA_High']
        ha_df['Low'] = ha_df['HA_Low']
        ha_df['Close'] = ha_df['HA_Close']
        
        # Drop temporary columns
        ha_df = ha_df.drop(columns=['HA_Open', 'HA_High', 'HA_Low', 'HA_Close'])
        
        logger.info(f"Transformed to Heikin Ashi: {len(ha_df)} candles")
        return ha_df
    
    @staticmethod
    def transform_data(df: pd.DataFrame, chart_type: str) -> pd.DataFrame:
        """
        Transform data based on chart type selection
        
        Args:
            df: DataFrame with OHLC data
            chart_type: One of 'japanese_candles', 'line', 'bars', 'heikin_ashi'
        
        Returns:
            Transformed DataFrame
        """
        if df is None or df.empty:
            logger.warning("Empty dataframe provided for transformation")
            return df
        
        # Ensure required columns exist
        required_cols = ['Open', 'High', 'Low', 'Close']
        if not all(col in df.columns for col in required_cols):
            logger.error(f"Missing required OHLC columns in dataframe")
            return df
        
        chart_type = chart_type.lower()
        
        if chart_type == 'japanese_candles' or chart_type == 'candles':
            return ChartTransformations.to_japanese_candles(df)
        
        elif chart_type == 'line':
            return ChartTransformations.to_line_chart(df)
        
        elif chart_type == 'bars':
            return ChartTransformations.to_bars(df)
        
        elif chart_type == 'heikin_ashi' or chart_type == 'heikinashi':
            return ChartTransformations.to_heikin_ashi(df)
        
        else:
            logger.warning(f"Unknown chart type '{chart_type}', using Japanese candles")
            return ChartTransformations.to_japanese_candles(df)
    
    @staticmethod
    def get_chart_type_info(chart_type: str) -> dict:
        """Get information about a chart type"""
        info = {
            'japanese_candles': {
                'name': 'Japanese Candlesticks',
                'description': 'Standard OHLC candlestick charts showing price action',
                'icon': '🕯️',
                'best_for': 'All trading styles, pattern recognition',
                'noise_level': 'Medium'
            },
            'line': {
                'name': 'Line Chart',
                'description': 'Simple line connecting close prices',
                'icon': '📈',
                'best_for': 'Trend identification, clean view',
                'noise_level': 'Low'
            },
            'bars': {
                'name': 'Bar Chart',
                'description': 'OHLC bars showing price ranges',
                'icon': '📊',
                'best_for': 'Price range analysis',
                'noise_level': 'Medium'
            },
            'heikin_ashi': {
                'name': 'Heikin Ashi',
                'description': 'Smoothed candles for better trend identification',
                'icon': '🎴',
                'best_for': 'Trend following, noise filtering',
                'noise_level': 'Very Low'
            }
        }
        
        return info.get(chart_type, info['japanese_candles'])


# Global instance
chart_transformer = ChartTransformations()

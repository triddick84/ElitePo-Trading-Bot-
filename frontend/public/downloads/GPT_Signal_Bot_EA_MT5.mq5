//+------------------------------------------------------------------+
//|                                        GPT_Signal_Bot_EA_MT5.mq5 |
//|                         GPT Signal Bot - MetaTrader 5 Integration |
//|                 https://auto-invert-engine.preview.emergentagent.com |
//+------------------------------------------------------------------+
#property copyright "GPT Signal Bot"
#property link      "https://auto-invert-engine.preview.emergentagent.com"
#property version   "1.00"
#property description "Receives trading signals from GPT Signal Bot and executes trades"

#include <Trade\Trade.mqh>

//--- Input parameters
input string   API_URL = "https://auto-invert-engine.preview.emergentagent.com/api";  // API URL
input string   API_KEY = "";                    // API Key (optional)
input int      PollIntervalSeconds = 5;         // Signal poll interval (seconds)
input double   LotSize = 0.01;                  // Trade lot size
input int      StopLoss = 50;                   // Stop loss in pips (0 = disabled)
input int      TakeProfit = 100;                // Take profit in pips (0 = disabled)
input ulong    Slippage = 30;                   // Maximum slippage in points
input ulong    MagicNumber = 123456;            // Magic number for EA trades
input bool     AutoTrade = true;                // Auto execute trades
input bool     SendToServer = true;             // Send trade results to server
input ENUM_ORDER_TYPE_FILLING FillingType = ORDER_FILLING_IOC; // Order filling type

//--- Global variables
datetime lastSignalTime = 0;
string lastSignalId = "";
CTrade trade;

//+------------------------------------------------------------------+
//| Expert initialization function                                      |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("GPT Signal Bot EA v1.0 (MT5) initialized");
   Print("API URL: ", API_URL);
   Print("Poll Interval: ", PollIntervalSeconds, " seconds");
   Print("Lot Size: ", LotSize);
   Print("Auto Trade: ", AutoTrade ? "Enabled" : "Disabled");
   
   // Configure trade object
   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(Slippage);
   trade.SetTypeFilling(FillingType);
   trade.SetAsyncMode(false);
   
   // Set timer for polling
   EventSetTimer(PollIntervalSeconds);
   
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                   |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("GPT Signal Bot EA stopped. Reason: ", reason);
}

//+------------------------------------------------------------------+
//| Expert tick function                                               |
//+------------------------------------------------------------------+
void OnTick()
{
   // Main logic runs on timer, not every tick
}

//+------------------------------------------------------------------+
//| Timer function - polls for signals                                 |
//+------------------------------------------------------------------+
void OnTimer()
{
   CheckForSignals();
}

//+------------------------------------------------------------------+
//| Check for new signals from the API                                 |
//+------------------------------------------------------------------+
void CheckForSignals()
{
   string url = API_URL + "/signals/latest";
   string headers = "Content-Type: application/json\r\n";
   if(StringLen(API_KEY) > 0)
      headers += "Authorization: Bearer " + API_KEY + "\r\n";
   
   char post[];
   char result[];
   string resultHeaders;
   
   int res = WebRequest("GET", url, headers, 5000, post, result, resultHeaders);
   
   if(res == -1)
   {
      int error = GetLastError();
      if(error == 4060)
         Print("Error: Add ", API_URL, " to allowed URLs in Tools > Options > Expert Advisors");
      else
         Print("WebRequest error: ", error);
      return;
   }
   
   string response = CharArrayToString(result);
   
   // Parse JSON response
   if(StringFind(response, "\"success\":true") >= 0 && StringFind(response, "\"signal\":") >= 0)
   {
      // Extract signal data
      string signalId = ExtractJsonValue(response, "id");
      string direction = ExtractJsonValue(response, "direction");
      string symbol = ExtractJsonValue(response, "symbol");
      string confidence = ExtractJsonValue(response, "confidence");
      
      // Check if this is a new signal
      if(signalId != lastSignalId && StringLen(direction) > 0)
      {
         lastSignalId = signalId;
         lastSignalTime = TimeCurrent();
         
         Print("New Signal: ", direction, " ", symbol, " (Confidence: ", confidence, "%)");
         
         if(AutoTrade)
         {
            ExecuteSignal(direction, symbol);
         }
         else
         {
            Alert("GPT Signal: ", direction, " ", symbol);
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Execute a trading signal                                           |
//+------------------------------------------------------------------+
void ExecuteSignal(string direction, string symbol)
{
   // Normalize symbol name
   string tradeSymbol = NormalizeSymbol(symbol);
   
   if(StringLen(tradeSymbol) == 0)
   {
      Print("Invalid symbol: ", symbol);
      return;
   }
   
   // Ensure symbol is selected in Market Watch
   if(!SymbolSelect(tradeSymbol, true))
   {
      Print("Cannot select symbol: ", tradeSymbol);
      return;
   }
   
   // Determine order type
   ENUM_ORDER_TYPE orderType;
   if(direction == "CALL" || direction == "BUY" || direction == "UP")
      orderType = ORDER_TYPE_BUY;
   else if(direction == "PUT" || direction == "SELL" || direction == "DOWN")
      orderType = ORDER_TYPE_SELL;
   else
   {
      Print("Unknown direction: ", direction);
      return;
   }
   
   // Get current price
   double price = (orderType == ORDER_TYPE_BUY) ? SymbolInfoDouble(tradeSymbol, SYMBOL_ASK) 
                                                 : SymbolInfoDouble(tradeSymbol, SYMBOL_BID);
   double point = SymbolInfoDouble(tradeSymbol, SYMBOL_POINT);
   int digits = (int)SymbolInfoInteger(tradeSymbol, SYMBOL_DIGITS);
   
   // Calculate SL/TP
   double sl = 0, tp = 0;
   if(StopLoss > 0)
   {
      sl = (orderType == ORDER_TYPE_BUY) ? price - StopLoss * point * 10 : price + StopLoss * point * 10;
      sl = NormalizeDouble(sl, digits);
   }
   if(TakeProfit > 0)
   {
      tp = (orderType == ORDER_TYPE_BUY) ? price + TakeProfit * point * 10 : price - TakeProfit * point * 10;
      tp = NormalizeDouble(tp, digits);
   }
   
   // Execute order
   bool success = false;
   if(orderType == ORDER_TYPE_BUY)
      success = trade.Buy(LotSize, tradeSymbol, price, sl, tp, "GPT Signal Bot");
   else
      success = trade.Sell(LotSize, tradeSymbol, price, sl, tp, "GPT Signal Bot");
   
   if(success)
   {
      ulong ticket = trade.ResultOrder();
      Print("Order executed: Ticket #", ticket, " ", (orderType == ORDER_TYPE_BUY ? "BUY" : "SELL"), 
            " ", LotSize, " ", tradeSymbol, " @ ", price);
      
      if(SendToServer)
         ReportTradeToServer(ticket, direction, tradeSymbol, "success");
   }
   else
   {
      uint error = trade.ResultRetcode();
      Print("Order failed: Error ", error, " - ", trade.ResultRetcodeDescription());
      
      if(SendToServer)
         ReportTradeToServer(0, direction, tradeSymbol, "failed: " + IntegerToString(error));
   }
}

//+------------------------------------------------------------------+
//| Normalize symbol name for MT5                                      |
//+------------------------------------------------------------------+
string NormalizeSymbol(string symbol)
{
   // Remove _OTC suffix
   string normalized = symbol;
   StringReplace(normalized, "_OTC", "");
   StringReplace(normalized, "_", "");
   
   // Check if symbol exists
   if(SymbolInfoDouble(normalized, SYMBOL_BID) > 0)
      return normalized;
   
   // Try with suffix variations
   string suffixes[] = {"", ".pro", ".ecn", "m", ".std", ".raw"};
   for(int i = 0; i < ArraySize(suffixes); i++)
   {
      string testSymbol = normalized + suffixes[i];
      if(SymbolInfoDouble(testSymbol, SYMBOL_BID) > 0)
         return testSymbol;
   }
   
   // Search in all available symbols
   int totalSymbols = SymbolsTotal(false);
   for(int i = 0; i < totalSymbols; i++)
   {
      string sym = SymbolName(i, false);
      if(StringFind(sym, normalized) >= 0)
         return sym;
   }
   
   return "";
}

//+------------------------------------------------------------------+
//| Extract value from JSON string                                     |
//+------------------------------------------------------------------+
string ExtractJsonValue(string json, string key)
{
   string searchKey = "\"" + key + "\":";
   int keyPos = StringFind(json, searchKey);
   if(keyPos < 0) return "";
   
   int valueStart = keyPos + StringLen(searchKey);
   
   // Skip whitespace
   while(valueStart < StringLen(json) && (StringGetCharacter(json, valueStart) == ' ' || StringGetCharacter(json, valueStart) == '\t'))
      valueStart++;
   
   // Check if value is a string
   if(StringGetCharacter(json, valueStart) == '"')
   {
      valueStart++;
      int valueEnd = StringFind(json, "\"", valueStart);
      if(valueEnd > valueStart)
         return StringSubstr(json, valueStart, valueEnd - valueStart);
   }
   else
   {
      // Numeric or boolean value
      int valueEnd = valueStart;
      while(valueEnd < StringLen(json))
      {
         ushort ch = StringGetCharacter(json, valueEnd);
         if(ch == ',' || ch == '}' || ch == ']' || ch == ' ' || ch == '\n' || ch == '\r')
            break;
         valueEnd++;
      }
      return StringSubstr(json, valueStart, valueEnd - valueStart);
   }
   
   return "";
}

//+------------------------------------------------------------------+
//| Report trade execution to server                                   |
//+------------------------------------------------------------------+
void ReportTradeToServer(ulong ticket, string direction, string symbol, string status)
{
   string url = API_URL + "/mt5/trade-report";
   string headers = "Content-Type: application/json\r\n";
   if(StringLen(API_KEY) > 0)
      headers += "Authorization: Bearer " + API_KEY + "\r\n";
   
   string jsonData = "{";
   jsonData += "\"ticket\":" + IntegerToString(ticket) + ",";
   jsonData += "\"direction\":\"" + direction + "\",";
   jsonData += "\"symbol\":\"" + symbol + "\",";
   jsonData += "\"status\":\"" + status + "\",";
   jsonData += "\"lot_size\":" + DoubleToString(LotSize, 2) + ",";
   jsonData += "\"magic_number\":" + IntegerToString(MagicNumber) + ",";
   jsonData += "\"platform\":\"MT5\",";
   jsonData += "\"timestamp\":\"" + TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS) + "\"";
   jsonData += "}";
   
   char post[];
   char result[];
   string resultHeaders;
   
   StringToCharArray(jsonData, post);
   ArrayResize(post, ArraySize(post) - 1);  // Remove null terminator
   
   int res = WebRequest("POST", url, headers, 5000, post, result, resultHeaders);
   
   if(res != -1)
      Print("Trade reported to server: ", status);
}

//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//|                                        GPT_Signal_Bot_EA_MT4.mq4 |
//|                         GPT Signal Bot - MetaTrader 4 Integration |
//|                 https://auto-trade-hub-25.preview.emergentagent.com |
//+------------------------------------------------------------------+
#property copyright "GPT Signal Bot"
#property link      "https://auto-trade-hub-25.preview.emergentagent.com"
#property version   "1.00"
#property strict
#property description "Receives trading signals from GPT Signal Bot and executes trades"

//--- Input parameters
input string   API_URL = "https://auto-trade-hub-25.preview.emergentagent.com/api";  // API URL
input string   API_KEY = "";                    // API Key (optional)
input int      PollIntervalSeconds = 5;         // Signal poll interval (seconds)
input double   LotSize = 0.01;                  // Trade lot size
input int      StopLoss = 50;                   // Stop loss in pips (0 = disabled)
input int      TakeProfit = 100;                // Take profit in pips (0 = disabled)
input int      Slippage = 3;                    // Maximum slippage
input int      MagicNumber = 123456;            // Magic number for EA trades
input bool     AutoTrade = true;                // Auto execute trades
input bool     SendToServer = true;             // Send trade results to server

//--- Global variables
datetime lastSignalTime = 0;
string lastSignalId = "";
int pollTimer = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                      |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("GPT Signal Bot EA v1.0 initialized");
   Print("API URL: ", API_URL);
   Print("Poll Interval: ", PollIntervalSeconds, " seconds");
   Print("Lot Size: ", LotSize);
   Print("Auto Trade: ", AutoTrade ? "Enabled" : "Disabled");
   
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
   
   // Determine order type
   int orderType = -1;
   if(direction == "CALL" || direction == "BUY" || direction == "UP")
      orderType = OP_BUY;
   else if(direction == "PUT" || direction == "SELL" || direction == "DOWN")
      orderType = OP_SELL;
   else
   {
      Print("Unknown direction: ", direction);
      return;
   }
   
   // Get current price
   double price = (orderType == OP_BUY) ? MarketInfo(tradeSymbol, MODE_ASK) : MarketInfo(tradeSymbol, MODE_BID);
   double point = MarketInfo(tradeSymbol, MODE_POINT);
   int digits = (int)MarketInfo(tradeSymbol, MODE_DIGITS);
   
   // Calculate SL/TP
   double sl = 0, tp = 0;
   if(StopLoss > 0)
   {
      sl = (orderType == OP_BUY) ? price - StopLoss * point : price + StopLoss * point;
      sl = NormalizeDouble(sl, digits);
   }
   if(TakeProfit > 0)
   {
      tp = (orderType == OP_BUY) ? price + TakeProfit * point : price - TakeProfit * point;
      tp = NormalizeDouble(tp, digits);
   }
   
   // Execute order
   int ticket = OrderSend(tradeSymbol, orderType, LotSize, price, Slippage, sl, tp, 
                          "GPT Signal Bot", MagicNumber, 0, (orderType == OP_BUY) ? clrGreen : clrRed);
   
   if(ticket > 0)
   {
      Print("Order executed: Ticket #", ticket, " ", (orderType == OP_BUY ? "BUY" : "SELL"), " ", LotSize, " ", tradeSymbol);
      
      if(SendToServer)
         ReportTradeToServer(ticket, direction, tradeSymbol, "success");
   }
   else
   {
      int error = GetLastError();
      Print("Order failed: Error ", error);
      
      if(SendToServer)
         ReportTradeToServer(0, direction, tradeSymbol, "failed: " + IntegerToString(error));
   }
}

//+------------------------------------------------------------------+
//| Normalize symbol name for MT4                                      |
//+------------------------------------------------------------------+
string NormalizeSymbol(string symbol)
{
   // Remove _OTC suffix
   string normalized = symbol;
   StringReplace(normalized, "_OTC", "");
   StringReplace(normalized, "_", "");
   
   // Check if symbol exists
   if(MarketInfo(normalized, MODE_BID) > 0)
      return normalized;
   
   // Try with suffix variations
   string suffixes[] = {"", ".pro", ".ecn", "m", ".std"};
   for(int i = 0; i < ArraySize(suffixes); i++)
   {
      string testSymbol = normalized + suffixes[i];
      if(MarketInfo(testSymbol, MODE_BID) > 0)
         return testSymbol;
   }
   
   // Try original symbol
   if(MarketInfo(symbol, MODE_BID) > 0)
      return symbol;
   
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
void ReportTradeToServer(int ticket, string direction, string symbol, string status)
{
   string url = API_URL + "/mt4/trade-report";
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

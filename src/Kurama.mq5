//+------------------------------------------------------------------+
//|                                                       Kurama.mq5 |
//|                                  Copyright 2026, MetaQuotes Ltd. |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, MetaQuotes Ltd."
#property link      "https://www.mql5.com"
#property description "Kurama Grid Recovery v0.1.0 baseline"
#property version   "1.10"
#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\OrderInfo.mqh>

//create on 30/05/2569
//--------------------------------------------------

CTrade         Trade;
CPositionInfo  m_position; 
COrderInfo     m_order;

enum mlot
  {
   lot_plus,       // Plus
   lot_multiply,  // Multiply
  };

enum mTrade
  {
      BandS,      // Buy and Sell
      BorS,       // Buy or Sell
      BuyOnly,    // Buy Only
      SellOnly,   // Sell Only
  };

enum mFirstEntry
  {
      Entry_MA_Filter,       // Close above/below MA
      Entry_MA_Cross,        // Candle cross MA
      Entry_Candle_Color,    // Previous candle color
      Entry_Breakout,        // Break previous candle high/low
      Entry_MA_Candle        // MA filter + candle color
  };  

//+------------------------------------------------------------------+
//| Expert input function                                            |
//+------------------------------------------------------------------+
input int      MagicNumber             = 12345;
input ENUM_TIMEFRAMES  TimeFrame       = PERIOD_CURRENT; // TimeFrame
input mTrade   ModeTradeP              = BorS;           // Mode Trade
input mFirstEntry FirstEntryMode       = Entry_MA_Filter;// First Entry Mode

input string   __martingale__          = "";             // ---------------|| Martingale Setting
input int      MaxOrder                = 99;
input int      TakeProfit              = 500;    
input int      Distance                = 100;            // Distance
input int      Pending                 = 100;

input string   __lot__                 = "";             // ---------------|| Lot Setting
input double   Lots                    = 0.01;           // Lots
input mlot     LotType                 = lot_plus;       // Lot Type
input double   LotPlus                 = 0.01;           // Plus
input double   LotExponent             = 1.5;            // Multiplier
input double   MaxLot                  = 3.0;            // Max Lot

input string   __CLOSE__               = "=============== Close Setting ===============";
input int      TrailingStart           = 100;
input int      TrailingStop            = 60;             // TrailingStop
input double   TP2                     = 0.0;            // TP($)
input double   SL2                     = 0.0;            // SL($)
input double   TP3                     = 0;              // TP(%)
input double   SL3                     = 0.0;            // SL(%)
input bool     StopEA                  = false;          // stop EA when cutloss
input double   ProfitPerday            = 0.0;            // Profit per day($)

input string   __close__               = "";             // ---------------|| จับคู่ปิด
input double   SecureProfit            = 50.0;           // ปิดด้วย Secure profit คูณล็อตสุดท้าย

input string   TimeTrade               = "============== Time Trade ===============";
input bool     UseTime                 = true;
input string   TimeStart               = "00:00";
input string   TimeEnd                 = "23:59"; 

input string   __MA__                  = "=============== Moving Average Trade ===============";
input int      MA1                     = 50;             // Period
input ENUM_MA_METHOD      MA_METHOD1   = MODE_EMA;       // MA Method
input ENUM_APPLIED_PRICE  MA_PRICE1    = PRICE_CLOSE;    // Applied to

input string   SetComment              = "=============== Comment Setting ===============";
input bool     ShowComment             = true;           // Comment

int            OpenOrders=0, cnt=0;
int            myOrderType=0;
int            CountB, CountS;
int            CountBS, CountSS;
int            BarB, BarS, count;
int            CountBar, LastBar;

datetime       time_open;
bool           success;
bool           ContinuebyTime;
bool           AutoRun = true;

string         EaName;
double         BuyPrice=0, SellPrice=0;
double         mylotsi=0;
double         SL,TP;
double         Profit;
double         LastLotsBuy, LastLotsSell;
double         SumProfitBuy, SumProfitSell;
double         TPB, TPS;
double         B_Lot, S_Lot;
double         B_LotPrice= 0;
double         B_Average = 0;
double         S_LotPrice= 0;
double         S_Average = 0;
double         Bid, Ask, pips;
double         MaxDD, DDcurr, MaxDDcurr, MarginLevel;
double         MinLot, LastLots;
double         FirstLotB, FirstLotS, LastPrice;
double         MinPriceBuy, MaxPriceBuy;
double         MinPriceSell, MaxPriceSell;

double         profit_max_buy, profit_min_buy;
double         profit_max_sell, profit_min_sell;
ulong          tick_max_buy, tick_min_buy;
ulong          tick_max_sell, tick_min_sell;

double         C1, EMA1;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
   Comment(" ");

   pips = _Point;
   if(_Digits==3 || _Digits==5)
     {
      pips = _Point*10;
     }

   Trade.SetExpertMagicNumber(MagicNumber);      
   EaName = MQLInfoString(MQL_PROGRAM_NAME); 

   for(int i=0;i<30;i++)
     {
      ObjectDelete(0,IntegerToString(i));
     }

   DeleteDashboardObjects();

   if(ShowComment)
      CreateDashboardPanel();

   ChartSetInteger(0,CHART_MODE,CHART_CANDLES);
   ChartSetInteger(0,CHART_SHOW_GRID,0,0);
   ChartSetInteger(0,CHART_COLOR_BACKGROUND,clrBlack);
   ChartSetInteger(0,CHART_COLOR_FOREGROUND,clrWhite);
   ChartSetInteger(0,CHART_COLOR_CHART_UP,clrLime);
   ChartSetInteger(0,CHART_COLOR_CHART_DOWN,clrRed);
   ChartSetInteger(0,CHART_COLOR_CANDLE_BULL,clrLime);
   ChartSetInteger(0,CHART_COLOR_CANDLE_BEAR,clrRed);

   DeleteOldButtons();

   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   DeleteOldButtons();
   DeleteDashboardObjects();
  }

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
  {
   ContinuebyTime  = false;

   if(UseTime && IsWithinTimeRange(TimeStart, TimeEnd)) 
     {
      ContinuebyTime = true;
     }

   if(UseTime==false)
     {
      ContinuebyTime = true;
     }

   OpenOrders      = 0;
   CountB          = 0;
   CountS          = 0;
   Profit          = 0;
   SumProfitBuy    = 0;
   SumProfitSell   = 0;
   B_Lot           = 0;
   S_Lot           = 0;
   BarS            = 0;
   BarB            = 0;
   B_LotPrice      = 0;
   B_Average       = 0;
   S_LotPrice      = 0;
   S_Average       = 0;

   LastLotsBuy     = 0; 
   LastLotsSell    = 0;

   MinPriceSell    = 0;
   MaxPriceSell    = 0;
   tick_max_sell   = 0;
   tick_min_sell   = 0;
   profit_max_sell = 0;
   profit_min_sell = 0;

   MinPriceBuy     = 0;
   MaxPriceBuy     = 0;
   tick_max_buy    = 0;
   tick_min_buy    = 0;
   profit_max_buy  = 0;
   profit_min_buy  = 0;

   for(int i=0;i<=PositionsTotal()-1;i++)   
     {
      if(m_position.SelectByIndex(i))
        {
         if(m_position.Symbol()==Symbol() && m_position.Magic()==MagicNumber)
           {
            OpenOrders++;
            Profit = Profit + PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP); 

            if(m_position.PositionType()==POSITION_TYPE_SELL)
              {				
               CountS++;
               time_open      = (datetime)PositionGetInteger(POSITION_TIME); 
               BarS           = iBarShift(Symbol(),TimeFrame,time_open);
               S_Lot          += PositionGetDouble(POSITION_VOLUME);
               S_LotPrice     += PositionGetDouble(POSITION_VOLUME)*PositionGetDouble(POSITION_PRICE_OPEN);
               LastLotsSell   = PositionGetDouble(POSITION_VOLUME);
               SumProfitSell  = SumProfitSell + PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);  

               if(PositionGetDouble(POSITION_PRICE_OPEN)>MaxPriceSell || MaxPriceSell==0)
                 {
                  MaxPriceSell    = PositionGetDouble(POSITION_PRICE_OPEN);
                  tick_max_sell   = PositionGetInteger(POSITION_TICKET);
                  profit_max_sell = PositionGetDouble(POSITION_PROFIT);
                 }

               if(PositionGetDouble(POSITION_PRICE_OPEN)<MinPriceSell || MinPriceSell==0)
                 {
                  MinPriceSell    = PositionGetDouble(POSITION_PRICE_OPEN);
                  tick_min_sell   = PositionGetInteger(POSITION_TICKET);
                  profit_min_sell = PositionGetDouble(POSITION_PROFIT);
                 }
              }	

            if(m_position.PositionType()==POSITION_TYPE_BUY)
              {
               CountB++;
               time_open      = (datetime)PositionGetInteger(POSITION_TIME); 
               BarB           = iBarShift(Symbol(),TimeFrame,time_open);
               LastLotsBuy    = PositionGetDouble(POSITION_VOLUME);
               B_Lot          += PositionGetDouble(POSITION_VOLUME);
               B_LotPrice     += PositionGetDouble(POSITION_VOLUME)*PositionGetDouble(POSITION_PRICE_OPEN);
               SumProfitBuy   = SumProfitBuy + PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);  

               if(PositionGetDouble(POSITION_PRICE_OPEN)<MinPriceBuy || MinPriceBuy==0)
                 {
                  MinPriceBuy    = PositionGetDouble(POSITION_PRICE_OPEN);
                  tick_min_buy   = PositionGetInteger(POSITION_TICKET);
                  profit_min_buy = PositionGetDouble(POSITION_PROFIT);
                 }

               if(PositionGetDouble(POSITION_PRICE_OPEN)>MaxPriceBuy || MaxPriceBuy==0)
                 {
                  MaxPriceBuy    = PositionGetDouble(POSITION_PRICE_OPEN);
                  tick_max_buy   = PositionGetInteger(POSITION_TICKET);
                  profit_max_buy = PositionGetDouble(POSITION_PROFIT);
                 }
              }	
           }
        }			
     }

   CountBS = 0;
   CountSS = 0;

   for(int i=0;i<=OrdersTotal()-1;i++)   
     {
      if(m_order.SelectByIndex(i)) 
        {
         if(m_order.Symbol()==_Symbol && m_order.Magic()==MagicNumber)
           {
            OpenOrders++;

            if(m_order.OrderType()==ORDER_TYPE_SELL_STOP)
              {
               CountSS++;
              }

            if(m_order.OrderType()==ORDER_TYPE_BUY_STOP)
              {
               CountBS++;
              }
           }
        }
     }     

   if(Profit<=MaxDD)
     {
      MaxDD = Profit;
     }   

   if(AccountInfoDouble(ACCOUNT_BALANCE)>0)
     {
      DDcurr = ((AccountInfoDouble(ACCOUNT_EQUITY)/AccountInfoDouble(ACCOUNT_BALANCE))*100)-100;
     }

   if(DDcurr<MaxDDcurr)
     {
      MaxDDcurr = ((AccountInfoDouble(ACCOUNT_EQUITY)/AccountInfoDouble(ACCOUNT_BALANCE))*100)-100;
     }    

   if(B_Lot!=0 && B_LotPrice!=0)
      B_Average=NormalizeDouble(B_LotPrice/B_Lot,_Digits);

   if(S_Lot!=0 && S_LotPrice!=0)
      S_Average=NormalizeDouble(S_LotPrice/S_Lot,_Digits);

   TPB = NormalizeDouble(B_Average+(TakeProfit*pips),_Digits);
   TPS = NormalizeDouble(S_Average-(TakeProfit*pips),_Digits);

   if(TakeProfit>0)
     {
      for(int i=PositionsTotal()-1;i>=0;i--)
        {
         ulong ticket=PositionGetTicket(i);

         if(PositionGetSymbol(i)==Symbol() &&
            TPB>0 &&
            PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY &&
            PositionGetDouble(POSITION_TP)!=TPB &&
            PositionGetInteger(POSITION_MAGIC)==MagicNumber)
           {
            Trade.PositionModify(ticket,PositionGetDouble(POSITION_SL),TPB);
           }

         if(PositionGetSymbol(i)==Symbol() &&
            TPS>0 &&
            PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_SELL &&
            PositionGetDouble(POSITION_TP)!=TPS &&
            PositionGetInteger(POSITION_MAGIC)==MagicNumber)
           {
            Trade.PositionModify(ticket,PositionGetDouble(POSITION_SL),TPS);
           }
        }
     }

   if(TrailingStart>0 && TrailingStop>0)
     {
      TrailingMar();
     }

   CountBar = iBars(Symbol(),TimeFrame);
   Bid      = SymbolInfoDouble(_Symbol,SYMBOL_BID);
   Ask      = SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   C1       = iClose(Symbol(),TimeFrame,1);
   EMA1     = GetMA();

   // ==============================
   // MODE BUY
   // ==============================
   if((ModeTradeP==BorS && OpenOrders<1) || (ModeTradeP==BandS) || (ModeTradeP==BuyOnly))
     {
      if(CountB<1 &&
         FirstEntrySignal(true) &&
         AutoRun &&
         ContinuebyTime &&
         (ProfitToday()<ProfitPerday || ProfitPerday==0))
        {
         BuyPrice= Ask;

         if(TakeProfit==0)
            TP=0;
         else
            TP=BuyPrice+TakeProfit*pips;	

         mylotsi = Lots;
         success = Trade.Buy(NormalizeLot(mylotsi),_Symbol,BuyPrice,0,TP,EaName+"-1");

         Print("Buy 1");
         Sleep(5000);
         return;
        }
     }

   BuyPrice = Ask+Pending*pips;

   if(CountB>0 &&
      CountB<MaxOrder &&
      CountBS<1 &&
      BarB>0 &&
      CountBar!=LastBar &&
      BuyPrice<MinPriceBuy &&
      MinPriceBuy-Ask>Distance*pips &&
      MinPriceBuy>0)
     {       
      LastBar = CountBar;
      count = CheckLastOrder(POSITION_TYPE_BUY);
      mylotsi= Lots;

      if(LotType==lot_plus)
        {
         mylotsi=NormalizeDouble(LastLotsBuy+LotPlus,2);
        }

      if(LotType==lot_multiply)
        {
         mylotsi = Lots;

         for(cnt=1;cnt<=count;cnt++)
           {
            LastLots=mylotsi;
            mylotsi=NormalizeDouble(LastLots*LotExponent,8);
           }
        }

      if(mylotsi>MaxLot)
        {
         mylotsi = MaxLot;
        }

      success = Trade.BuyStop(NormalizeLot(mylotsi),BuyPrice,_Symbol,0,0,0,0,EaName+"-"+IntegerToString(count+1));

      Sleep(5000);
      return;
     }

   // ==============================
   // MODE SELL
   // ==============================
   if((ModeTradeP==BorS && OpenOrders<1) || (ModeTradeP==BandS) || (ModeTradeP==SellOnly))
     {
      if(CountS<1 &&
         CountS<MaxOrder &&
         FirstEntrySignal(false) &&
         AutoRun &&
         ContinuebyTime &&
         (ProfitToday()<ProfitPerday || ProfitPerday==0))
        {
         SellPrice=Bid;

         if(TakeProfit==0)
            TP=0;
         else
            TP=SellPrice-TakeProfit*pips;	

         mylotsi= Lots;
         success = Trade.Sell(NormalizeLot(mylotsi),_Symbol,SellPrice,0,TP,EaName+"-1");

         Sleep(5000);
         return;
        }
     }

   SellPrice = Bid-Pending*pips;

   if(CountS>0 &&
      CountSS<1 &&
      BarS>0 &&
      CountBar!=LastBar &&
      SellPrice>MaxPriceSell &&
      Bid-MaxPriceSell>Distance*pips &&
      MaxPriceSell>0)
     {       
      count = CheckLastOrder(POSITION_TYPE_SELL);
      LastBar = CountBar;
      mylotsi= Lots;

      if(LotType==lot_plus)
        {
         mylotsi=NormalizeDouble(LastLotsSell+LotPlus,2);
        }

      if(LotType==lot_multiply)
        {
         mylotsi = Lots;

         for(cnt=1;cnt<=count;cnt++)
           {
            LastLots=mylotsi;
            mylotsi=NormalizeDouble(LastLots*LotExponent,8);
           }
        }

      if(mylotsi>MaxLot)
        {
         mylotsi = MaxLot;
        }

      success = Trade.SellStop(NormalizeLot(mylotsi),SellPrice,_Symbol,0,0,0,0,EaName+"-"+IntegerToString(count+1));

      Sleep(5000);
      return;
     }

   // ==============================
   // MODIFY PENDING ORDERS
   // ==============================
   if(CountBS>0 || CountSS>0)
     {
      for(int i=0;i<=OrdersTotal()-1;i++)   
        {
         if(m_order.SelectByIndex(i)) 
           {
            if(m_order.Symbol()==_Symbol && m_order.Magic()==MagicNumber)
              {
               if(m_order.OrderType()==ORDER_TYPE_BUY_STOP && m_order.PriceOpen()>Ask+Pending*pips)
                 {
                  Trade.OrderModify(m_order.Ticket(),Ask+Pending*pips,0,0,0,0);
                 }

               if(m_order.OrderType()==ORDER_TYPE_SELL_STOP && m_order.PriceOpen()<Bid-Pending*pips)
                 {
                  Trade.OrderModify(m_order.Ticket(),Bid-Pending*pips,0,0,0,0);
                 }
              }
           }
        }     
     }

   // ==============================
   // CLOSE BY TP MONEY
   // ==============================
   if(CountB!=0 && SumProfitBuy>= TP2 && TP2>0)
     { 
      ClosePositionsByType(POSITION_TYPE_BUY);
      DeleteOrdersByType(ORDER_TYPE_BUY_STOP);
     }

   if(CountS!=0 && SumProfitSell>= TP2 && TP2>0)
     { 
      ClosePositionsByType(POSITION_TYPE_SELL);
      DeleteOrdersByType(ORDER_TYPE_SELL_STOP);
     }

   // ==============================
   // CLOSE BY SL MONEY
   // ==============================
   if(OpenOrders!=0 && Profit<= -SL2 && SL2>0)
     { 
      ClosePositionsByType();
      DeleteOrdersByType();

      if(StopEA)
        {
         AutoRun = false;
        }
     }

   // ==============================
   // CLOSE BY SL %
   // ==============================
   if(OpenOrders!=0 && Profit<= -(SL3*AccountInfoDouble(ACCOUNT_BALANCE)/100) && SL3>0)
     { 
      ClosePositionsByType();
      DeleteOrdersByType();

      if(StopEA)
        {
         AutoRun = false;
        }
     }

   // ==============================
   // CLOSE BY TP %
   // ==============================
   if(OpenOrders!=0 && Profit>= (TP3*AccountInfoDouble(ACCOUNT_BALANCE)/100) && TP3>0)
     { 
      ClosePositionsByType();
      DeleteOrdersByType();
     }

   // ==============================
   // SECURE PROFIT BUY
   // ==============================
   if(CountB>2 && profit_max_buy+profit_min_buy>LastLotsBuy*SecureProfit && SecureProfit>0)
     {
      for(int i=PositionsTotal()-1;i>=0;i--)   
        {
         if(m_position.SelectByIndex(i))
           {
            if(m_position.Symbol()==_Symbol &&
               m_position.PositionType()==POSITION_TYPE_BUY &&
               m_position.Magic()==MagicNumber)
              {
               if(m_position.Ticket()==tick_max_buy || m_position.Ticket()==tick_min_buy)
                 {
                  Trade.PositionClose(m_position.Ticket());
                  Print("ปิดบายจับคู่บน-ล่าง");
                 }
              }
           }
        }   
     }

   // ==============================
   // SECURE PROFIT SELL
   // ==============================
   if(CountS>2 && profit_max_sell+profit_min_sell>LastLotsSell*SecureProfit && SecureProfit>0)
     {
      for(int i=PositionsTotal()-1;i>=0;i--)   
        {
         if(m_position.SelectByIndex(i))
           {
            if(m_position.Symbol()==_Symbol &&
               m_position.PositionType()==POSITION_TYPE_SELL &&
               m_position.Magic()==MagicNumber)
              {
               if(m_position.Ticket()==tick_max_sell || m_position.Ticket()==tick_min_sell)
                 {
                  Trade.PositionClose(m_position.Ticket());
                  Print("ปิดเซลจับคู่บน-ล่าง");
                 }
              }
           }
        }   
     }

   // ==============================
   // DELETE ORPHAN PENDING
   // ==============================
   if(CountB<1 && CountBS>0)
     {
      DeleteOrdersByType(ORDER_TYPE_BUY_STOP);
     }

   if(CountS<1 && CountSS>0)
     {
      DeleteOrdersByType(ORDER_TYPE_SELL_STOP);
     }

   if(ShowComment) 
     {
      Information();     
     }
  }

string ModeTradeName()
  {
   switch(ModeTradeP)
     {
      case BandS:    return("Buy/Sell");
      case BorS:     return("Buy or Sell");
      case BuyOnly:  return("Buy Only");
      case SellOnly: return("Sell Only");
     }

   return("Unknown");
  }

//+------------------------------------------------------------------+
//| Show price or dash                                               |
//+------------------------------------------------------------------+
string ShowPriceOrDash(double value)
  {
   if(value<=0)
      return("-");

   return(DoubleToString(value,_Digits));
  }

//+------------------------------------------------------------------+
//| Format money                                                     |
//+------------------------------------------------------------------+
string MoneyText(double value)
  {
   if(value>0)
      return("+$"+TestCommaFormat(value,2));

   if(value<0)
      return("-$"+TestCommaFormat(MathAbs(value),2));

   return("$0.00");
  }

//+------------------------------------------------------------------+
//| Create compact dashboard background                              |
//+------------------------------------------------------------------+
void CreateDashboardPanel()
  {
   string name = "DB_BG";

   if(ObjectFind(0,name)<0)
      ObjectCreate(0,name,OBJ_RECTANGLE_LABEL,0,0,0);

   ObjectSetInteger(0,name,OBJPROP_CORNER,CORNER_RIGHT_UPPER);
   ObjectSetInteger(0,name,OBJPROP_XDISTANCE,4);
   ObjectSetInteger(0,name,OBJPROP_YDISTANCE,18);
   ObjectSetInteger(0,name,OBJPROP_XSIZE,210);
   ObjectSetInteger(0,name,OBJPROP_YSIZE,330);
   ObjectSetInteger(0,name,OBJPROP_BGCOLOR,clrBlack);
   ObjectSetInteger(0,name,OBJPROP_COLOR,clrDimGray);
   ObjectSetInteger(0,name,OBJPROP_BORDER_TYPE,BORDER_FLAT);
   ObjectSetInteger(0,name,OBJPROP_BACK,false);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,name,OBJPROP_SELECTED,false);
   ObjectSetInteger(0,name,OBJPROP_HIDDEN,true);
   ObjectSetInteger(0,name,OBJPROP_ZORDER,0);
  }

//+------------------------------------------------------------------+
//| Delete dashboard objects                                         |
//+------------------------------------------------------------------+
void DeleteDashboardObjects()
  {
   for(int i=ObjectsTotal(0)-1;i>=0;i--)
     {
      string name = ObjectName(0,i);

      if(StringFind(name,"DB_")==0)
         ObjectDelete(0,name);
     }

   // Cleanup labels used by the old dashboard version.
   for(int i=4;i<=28;i++)
      ObjectDelete(0,IntegerToString(i));
  }

//+------------------------------------------------------------------+
//| Dashboard                                                        |
//+------------------------------------------------------------------+
void Information()
  {
   if(ObjectFind(0,"DB_BG")<0)
      CreateDashboardPanel();

   const int fs      = 8;
   const int fsTitle = 9;

   const int xLabel  = 126;
   const int xValue  = 12;

   color normalCol = clrWhite;
   color mutedCol  = clrSilver;

   color buyCol =
      (SumProfitBuy>0 ? clrLime :
      (SumProfitBuy<0 ? clrTomato : clrWhite));

   color sellCol =
      (SumProfitSell>0 ? clrLime :
      (SumProfitSell<0 ? clrTomato : clrWhite));

   color totalCol =
      (Profit>0 ? clrLime :
      (Profit<0 ? clrTomato : clrWhite));

   color statusCol = AutoRun ? clrLime : clrOrange;
   color timeCol   = ContinuebyTime ? clrLime : clrOrange;

   string statusText = AutoRun ? "RUNNING" : "PAUSED";
   string timeText   = ContinuebyTime ? "Allowed" : "Blocked";

   double todayProfit = ProfitToday();

   color todayCol =
      (todayProfit>0 ? clrLime :
      (todayProfit<0 ? clrTomato : clrWhite));

   // Header
   SetText("DB_TITLE","EA DASHBOARD",
           78,26,fsTitle,"Arial",clrAqua);

   SetText("DB_STATUS",statusText,
           xValue,26,fs,"Arial",statusCol);

   SetText("DB_SYMBOL",_Symbol,
           xLabel,44,fsTitle,"Arial",clrWhite);

   SetText("DB_MAGIC","#"+IntegerToString(MagicNumber),
           xValue,44,fs,"Arial",mutedCol);

   // EA settings
   SetText("DB_L_ENTRY","Entry",
           xLabel,59,fs,"Arial",mutedCol);
   SetText("DB_V_ENTRY",FirstEntryModeName(),
           xValue,59,fs,"Arial",normalCol);

   SetText("DB_L_MODE","Mode",
           xLabel,74,fs,"Arial",mutedCol);
   SetText("DB_V_MODE",ModeTradeName(),
           xValue,74,fs,"Arial",normalCol);

   SetText("DB_L_TIME","Time",
           xLabel,89,fs,"Arial",mutedCol);
   SetText("DB_V_TIME",timeText,
           xValue,89,fs,"Arial",timeCol);

   // BUY
   SetText("DB_BUY_HEAD","----- BUY -----",
           72,108,fs,"Consolas",clrDeepSkyBlue);

   SetText("DB_BUY_L1","Orders / Lot",
           xLabel,124,fs,"Arial",mutedCol);
   SetText("DB_BUY_V1",
           IntegerToString(CountB)+" / "+DoubleToString(B_Lot,2),
           xValue,124,fs,"Arial",normalCol);

   SetText("DB_BUY_L2","Average",
           xLabel,139,fs,"Arial",mutedCol);
   SetText("DB_BUY_V2",ShowPriceOrDash(B_Average),
           xValue,139,fs,"Arial",normalCol);

   SetText("DB_BUY_L3","P/L",
           xLabel,154,fs,"Arial",mutedCol);
   SetText("DB_BUY_V3",MoneyText(SumProfitBuy),
           xValue,154,fsTitle,"Arial",buyCol);

   // SELL
   SetText("DB_SELL_HEAD","----- SELL -----",
           70,173,fs,"Consolas",clrTomato);

   SetText("DB_SELL_L1","Orders / Lot",
           xLabel,189,fs,"Arial",mutedCol);
   SetText("DB_SELL_V1",
           IntegerToString(CountS)+" / "+DoubleToString(S_Lot,2),
           xValue,189,fs,"Arial",normalCol);

   SetText("DB_SELL_L2","Average",
           xLabel,204,fs,"Arial",mutedCol);
   SetText("DB_SELL_V2",ShowPriceOrDash(S_Average),
           xValue,204,fs,"Arial",normalCol);

   SetText("DB_SELL_L3","P/L",
           xLabel,219,fs,"Arial",mutedCol);
   SetText("DB_SELL_V3",MoneyText(SumProfitSell),
           xValue,219,fsTitle,"Arial",sellCol);

   // ACCOUNT
   SetText("DB_ACC_HEAD","--- ACCOUNT ---",
           70,238,fs,"Consolas",clrGold);

   SetText("DB_ACC_L1","Floating",
           xLabel,254,fs,"Arial",mutedCol);
   SetText("DB_ACC_V1",MoneyText(Profit),
           xValue,254,fsTitle,"Arial",totalCol);

   SetText("DB_ACC_L2","Today",
           xLabel,269,fs,"Arial",mutedCol);
   SetText("DB_ACC_V2",MoneyText(todayProfit),
           xValue,269,fs,"Arial",todayCol);

   SetText("DB_ACC_L3","Equity",
           xLabel,284,fs,"Arial",mutedCol);
   SetText("DB_ACC_V3",
           "$"+TestCommaFormat(AccountInfoDouble(ACCOUNT_EQUITY),2),
           xValue,284,fs,"Arial",normalCol);

   SetText("DB_ACC_L4","Balance",
           xLabel,299,fsTitle,"Arial",clrGold);
   SetText("DB_ACC_V4",
           "$"+TestCommaFormat(AccountInfoDouble(ACCOUNT_BALANCE),2),
           xValue,299,fsTitle,"Arial",clrGold);

   SetText("DB_ACC_L5","Max DD",
           xLabel,314,fs,"Arial",mutedCol);
   SetText("DB_ACC_V5",
           "$"+TestCommaFormat(MathAbs(MaxDD),2)+
           " | "+DoubleToString(MathAbs(MaxDDcurr),2)+"%",
           xValue,314,fs,"Arial",clrTomato);

   SetText("DB_ACC_L6","Lot All History",
           xLabel,329,fs,"Arial",mutedCol);
   SetText("DB_ACC_V6",
           TestCommaFormat(LotALL(),2),
           xValue,329,fs,"Arial",normalCol);
  }

//+------------------------------------------------------------------+
//| Format number with comma                                         |
//+------------------------------------------------------------------+
string TestCommaFormat(double Numb,int dig)
  {
   bool negative = (Numb<0);
   double value  = MathAbs(Numb);

   string raw = DoubleToString(value,dig);
   int dotPos = StringFind(raw,".");

   string integerPart;
   string decimalPart = "";

   if(dotPos>=0)
     {
      integerPart = StringSubstr(raw,0,dotPos);
      decimalPart = StringSubstr(raw,dotPos);
     }
   else
     {
      integerPart = raw;
     }

   string formatted = "";
   int len = StringLen(integerPart);

   for(int i=0;i<len;i++)
     {
      if(i>0 && ((len-i)%3)==0)
         formatted += ",";

      formatted += StringSubstr(integerPart,i,1);
     }

   if(negative)
      formatted = "-"+formatted;

   return(formatted+decimalPart);
  }

//+------------------------------------------------------------------+
//| Lot history all                                                  |
//+------------------------------------------------------------------+
double LotALL()
  {
   ulong    deal_ticket;    
   ulong    magic;
   ulong    type = 9;
   string   sym;
   double   orderlot;
   double   value = 0;
   ENUM_DEAL_ENTRY entry_type;
   datetime from_date=0; 
   datetime to_date=TimeCurrent();

   HistorySelect(from_date,to_date); 

   for(int i=0;i<HistoryDealsTotal();i++) 
     { 
      deal_ticket = HistoryDealGetTicket(i); 
      magic       = HistoryDealGetInteger(deal_ticket,DEAL_MAGIC);
      sym         = HistoryDealGetString(deal_ticket,DEAL_SYMBOL);
      orderlot    = HistoryDealGetDouble(deal_ticket,DEAL_VOLUME);
      type        = HistoryDealGetInteger(deal_ticket,DEAL_TYPE);
      entry_type  = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal_ticket,DEAL_ENTRY);

      if(_Symbol==sym && type<=1 && magic==MagicNumber && entry_type==DEAL_ENTRY_IN)
        {
         value += orderlot;
        }
     } 

   return(value);     
  }

//+------------------------------------------------------------------+
//| Lots today                                                       |
//+------------------------------------------------------------------+
double LotsD()
  {
   ulong    deal_ticket;    
   ulong    magic, type;
   string   sym;
   double   lot;
   double   value = 0;
   datetime from_date=iTime(Symbol(), PERIOD_D1, 0); 
   datetime to_date=TimeCurrent();

   HistorySelect(from_date,to_date); 

   for(int i=0;i<HistoryDealsTotal();i++) 
     { 
      deal_ticket = HistoryDealGetTicket(i); 
      type        = HistoryDealGetInteger(deal_ticket,DEAL_TYPE);
      magic       = HistoryDealGetInteger(deal_ticket,DEAL_MAGIC);
      sym         = HistoryDealGetString(deal_ticket,DEAL_SYMBOL);
      lot         = HistoryDealGetDouble(deal_ticket,DEAL_VOLUME);

      if(_Symbol==sym && type<2 && magic==MagicNumber)
        {
         value += lot;
        }
     } 

   return(value);     
  }

//+------------------------------------------------------------------+
//| Lots week                                                        |
//+------------------------------------------------------------------+
double LotsW()
  {
   ulong    deal_ticket;    
   ulong    magic, type;
   string   sym;
   double   lot;
   double   value = 0;
   datetime from_date=iTime(Symbol(), PERIOD_W1, 0); 
   datetime to_date=TimeCurrent();

   HistorySelect(from_date,to_date); 

   for(int i=0;i<HistoryDealsTotal();i++) 
     { 
      deal_ticket = HistoryDealGetTicket(i); 
      type        = HistoryDealGetInteger(deal_ticket,DEAL_TYPE);
      magic       = HistoryDealGetInteger(deal_ticket,DEAL_MAGIC);
      sym         = HistoryDealGetString(deal_ticket,DEAL_SYMBOL);
      lot         = HistoryDealGetDouble(deal_ticket,DEAL_VOLUME);

      if(_Symbol==sym && type<2 && magic==MagicNumber)
        {
         value += lot;
        }
     } 

   return(value);     
  }

//+------------------------------------------------------------------+
//| Lots month                                                       |
//+------------------------------------------------------------------+
double LotsM()
  {
   ulong    deal_ticket;    
   ulong    magic, type;
   string   sym;
   double   lot;
   double   value = 0;
   datetime from_date=iTime(Symbol(), PERIOD_MN1, 0); 
   datetime to_date=TimeCurrent();

   HistorySelect(from_date,to_date); 

   for(int i=0;i<HistoryDealsTotal();i++) 
     { 
      deal_ticket = HistoryDealGetTicket(i); 
      type        = HistoryDealGetInteger(deal_ticket,DEAL_TYPE);
      magic       = HistoryDealGetInteger(deal_ticket,DEAL_MAGIC);
      sym         = HistoryDealGetString(deal_ticket,DEAL_SYMBOL);
      lot         = HistoryDealGetDouble(deal_ticket,DEAL_VOLUME);

      if(_Symbol==sym && type<2 && magic==MagicNumber)
        {
         value += lot;
        }
     } 

   return(value);     
  }

//+------------------------------------------------------------------+
//| Set label text                                                   |
//+------------------------------------------------------------------+
void SetText(string name,
             string text,
             int PositionX,
             int PositionY,
             int fontsize_16,
             string fonts,
             color fontcolor,
             ENUM_BASE_CORNER corner=CORNER_RIGHT_UPPER,
             ENUM_ANCHOR_POINT anchor = ANCHOR_RIGHT_UPPER) 
  {
   if(ObjectFind(0,name) < 0)
      ObjectCreate(0,name, OBJ_LABEL, 0, 0, 0, 0, 0);

   ObjectSetInteger(0,name, OBJPROP_CORNER,corner);
   ObjectSetInteger(0,name, OBJPROP_ANCHOR,anchor);
   ObjectSetInteger(0,name, OBJPROP_XDISTANCE, PositionX);
   ObjectSetInteger(0,name, OBJPROP_YDISTANCE, PositionY);
   ObjectSetString(0,name,OBJPROP_TEXT,text);
   ObjectSetString(0,name,OBJPROP_FONT,fonts);
   ObjectSetInteger(0,name,OBJPROP_COLOR,fontcolor);
   ObjectSetInteger(0,name,OBJPROP_FONTSIZE,fontsize_16);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,name,OBJPROP_SELECTED,false);
   ObjectSetInteger(0,name,OBJPROP_HIDDEN,true);
   ObjectSetInteger(0,name,OBJPROP_ZORDER,1);
  }

//+------------------------------------------------------------------+
//| Profit today                                                     |
//+------------------------------------------------------------------+
double ProfitToday()
  {
   ulong deal_ticket;
   datetime close_time;
   double profit;
   double swap;
   double commision;
   double value = 0;
   ulong type = 9;
   ulong magic;
   string sym;

   datetime from_date=iTime(Symbol(), PERIOD_D1, 0); 
   datetime to_date=TimeCurrent();

   HistorySelect(from_date,to_date); 

   for(int i=0;i<HistoryDealsTotal();i++) 
     { 
      deal_ticket = HistoryDealGetTicket(i); 
      type        = HistoryDealGetInteger(deal_ticket,DEAL_TYPE);
      magic       = HistoryDealGetInteger(deal_ticket,DEAL_MAGIC);
      sym         = HistoryDealGetString(deal_ticket,DEAL_SYMBOL);
      profit      = HistoryDealGetDouble(deal_ticket,DEAL_PROFIT); 
      swap        = HistoryDealGetDouble(deal_ticket,DEAL_SWAP);
      commision   = HistoryDealGetDouble(deal_ticket,DEAL_COMMISSION);
      close_time  = (datetime)HistoryDealGetInteger(deal_ticket,DEAL_TIME); 

      if(type<=1 &&
         magic==MagicNumber &&
         sym==_Symbol &&
         TimeToString(TimeCurrent(),TIME_DATE) == TimeToString(close_time,TIME_DATE))
        {
         value = value + profit + swap + commision;
        }
     } 

   return(value);     
  }

//+------------------------------------------------------------------+
//| Convert string to today time                                     |
//+------------------------------------------------------------------+
datetime StrToTime(string timeStr)
  {
   MqlDateTime timeStruct;
   TimeToStruct(TimeLocal(), timeStruct); 

   int currentHour = timeStruct.hour;
   int currentMinute = timeStruct.min;

   int hour = (int)StringToInteger(StringSubstr(timeStr, 0, 2));
   int minute = (int)StringToInteger(StringSubstr(timeStr, 3, 2));

   return TimeLocal() - (currentHour * 3600 + currentMinute * 60) + (hour * 3600 + minute * 60);
  }

//+------------------------------------------------------------------+
//| Check time range                                                 |
//+------------------------------------------------------------------+
bool IsWithinTimeRange(string start, string end)
  {
   datetime startTime = StrToTime(start);
   datetime endTime = StrToTime(end);
   datetime currentTime = TimeLocal();

   if(startTime < endTime)
     {
      return(currentTime >= startTime && currentTime <= endTime);
     }
   else
     {
      return(currentTime >= startTime || currentTime <= endTime);
     }
  }

//+------------------------------------------------------------------+
//| Trailing stop                                                    |
//+------------------------------------------------------------------+
void TrailingMar()
  {
   double tss;

   if(TrailingStop>0)
     {
      if(Ask<=S_Average-pips*TrailingStart && S_Average>0)
        {
         tss = Ask+pips*TrailingStop;

         for(int i=PositionsTotal()-1;i>=0;i--)   
           {
            ulong ticket=PositionGetTicket(i);

            if(m_position.SelectByIndex(i))
              {
               if(m_position.Symbol()==Symbol() &&
                  m_position.PositionType()==POSITION_TYPE_SELL &&
                  m_position.Magic()==MagicNumber)
                 {
                  if(tss<PositionGetDouble(POSITION_SL) || PositionGetDouble(POSITION_SL)==0)
                    {
                     Trade.PositionModify(ticket,tss,PositionGetDouble(POSITION_TP));
                    }
                 }
              }
           }
        }   

      if(Bid>=B_Average+pips*TrailingStart && B_Average>0)
        {
         tss = Bid-pips*TrailingStop;

         for(int i=PositionsTotal()-1;i>=0;i--)   
           {
            ulong ticket=PositionGetTicket(i);

            if(m_position.SelectByIndex(i))
              {
               if(m_position.Symbol()==Symbol() &&
                  m_position.PositionType()==POSITION_TYPE_BUY &&
                  m_position.Magic()==MagicNumber)
                 {
                  if(tss>PositionGetDouble(POSITION_SL))
                    {
                     Trade.PositionModify(ticket,tss,PositionGetDouble(POSITION_TP));
                    }
                 }
              }
           }              
        }               
     }
  }

//+------------------------------------------------------------------+
//| MA value                                                         |
//+------------------------------------------------------------------+
double GetMA()
  {
   double ema1Buffer[];
   ArraySetAsSeries(ema1Buffer,true);

   int ema1Handle = iMA(_Symbol,TimeFrame,MA1,0,MA_METHOD1,MA_PRICE1);

   if(ema1Handle==INVALID_HANDLE)
      return(0);

   int ema1Copy = CopyBuffer(ema1Handle,0,0,3,ema1Buffer);

   IndicatorRelease(ema1Handle);

   if(ema1Copy<=1)
      return(0);

   return(ema1Buffer[1]);
  }

//+------------------------------------------------------------------+
//| Check last order number from comment                             |
//+------------------------------------------------------------------+
int CheckLastOrder(ulong type)
  {
   int value = 0;
   string parts[];

   for(int i=0;i<=PositionsTotal()-1;i++)
     {
      if(m_position.SelectByIndex(i))
        {
         if(m_position.Symbol()==Symbol() &&
            m_position.PositionType()==type &&
            m_position.Magic()==MagicNumber)
           {
            int nub = StringSplit(m_position.Comment(), '-', parts);

            if(nub>=2)
              {
               value = (int)StringToInteger(parts[1]);
              }
           }
        }
     }

   return(value);
  }

//+------------------------------------------------------------------+
//| First entry signal                                               |
//+------------------------------------------------------------------+
bool FirstEntrySignal(bool isBuy)
  {
   double c1 = iClose(Symbol(),TimeFrame,1);
   double c2 = iClose(Symbol(),TimeFrame,2);
   double o1 = iOpen(Symbol(),TimeFrame,1);
   double h2 = iHigh(Symbol(),TimeFrame,2);
   double l2 = iLow(Symbol(),TimeFrame,2);
   double ma1 = GetMA();

   if(c1==0 || ma1==0)
      return(false);

   switch(FirstEntryMode)
     {
      case Entry_MA_Filter:
         return(isBuy ? c1>ma1 : c1<ma1);

      case Entry_MA_Cross:
         return(isBuy ? (c2<=ma1 && c1>ma1) : (c2>=ma1 && c1<ma1));

      case Entry_Candle_Color:
         return(isBuy ? c1>o1 : c1<o1);

      case Entry_Breakout:
         return(isBuy ? c1>h2 : c1<l2);

      case Entry_MA_Candle:
         return(isBuy ? (c1>ma1 && c1>o1) : (c1<ma1 && c1<o1));
     }

   return(false);
  }

//+------------------------------------------------------------------+
//| First entry mode name                                            |
//+------------------------------------------------------------------+
string FirstEntryModeName()
  {
   switch(FirstEntryMode)
     {
      case Entry_MA_Filter:    return("MA Filter");
      case Entry_MA_Cross:     return("MA Cross");
      case Entry_Candle_Color: return("Candle Color");
      case Entry_Breakout:     return("Breakout");
      case Entry_MA_Candle:    return("MA + Candle");
     }

   return("Unknown");
  }

//+------------------------------------------------------------------+
//| Normalize lot                                                    |
//+------------------------------------------------------------------+
double NormalizeLot(double lot)
  {
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   lot = MathMin(lot, MaxLot);

   if(maxLot>0)
      lot = MathMin(lot, maxLot);

   if(minLot>0)
      lot = MathMax(lot, minLot);

   if(step>0)
     {
      lot = MathFloor(lot/step) * step;
     }

   int digits = 2;

   if(step>0 && step<1)
     {
      digits = (int)MathCeil(-MathLog10(step));
     }

   return NormalizeDouble(lot, digits);
  }

//+------------------------------------------------------------------+
//| Delete old button objects                                        |
//+------------------------------------------------------------------+
void DeleteOldButtons()
  {
   ObjectDelete(0,"Button_Start");
   ObjectDelete(0,"Button_CloseBuy");
   ObjectDelete(0,"Button_CloseSell");
   ObjectDelete(0,"Button_CloseAll");
  }

//+------------------------------------------------------------------+
//| Close positions by type                                          |
//| position_type = -1 means close all                               |
//+------------------------------------------------------------------+
void ClosePositionsByType(int position_type=-1)
  {
   ulong trades[];
   int n = 0;

   for(int i=0; i<PositionsTotal(); i++)
     {
      if(!m_position.SelectByIndex(i))
         continue;

      if(m_position.Symbol()!=_Symbol || m_position.Magic()!=MagicNumber)
         continue;

      if(position_type!=-1 && (int)m_position.PositionType()!=position_type)
         continue;

      ArrayResize(trades, n+1);
      trades[n] = m_position.Ticket();
      n++;
     }

   Trade.SetAsyncMode(true);

   for(int i=0; i<n; i++)
     {
      if(trades[i]>0)
        {
         Trade.PositionClose(trades[i]);
        }
     }

   Trade.SetAsyncMode(false);
  }

//+------------------------------------------------------------------+
//| Delete pending orders by type                                    |
//| order_type = -1 means delete all                                 |
//+------------------------------------------------------------------+
void DeleteOrdersByType(int order_type=-1)
  {
   for(int i=OrdersTotal()-1; i>=0; i--)
     {
      if(!m_order.SelectByIndex(i))
         continue;

      if(m_order.Symbol()!=_Symbol || m_order.Magic()!=MagicNumber)
         continue;

      if(order_type!=-1 && (int)m_order.OrderType()!=order_type)
         continue;

      Trade.OrderDelete(m_order.Ticket());
     }
  }
//+------------------------------------------------------------------+

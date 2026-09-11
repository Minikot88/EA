//+------------------------------------------------------------------+
//|                                                           EA.mq5 |
//|                                  Copyright 2026, MetaQuotes Ltd. |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, MetaQuotes Ltd."
#property link      "https://www.mql5.com"
#property version   "2.3"
#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\OrderInfo.mqh>

//create on 30/05/2569
//--------------------------------------------------

CTrade         Trade;
CPositionInfo  m_position; 
COrderInfo     m_order;

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

enum ENUM_EA_TRADE_OPERATION
  {
   TRADE_OP_MARKET_OPEN,
   TRADE_OP_PENDING_CREATE,
   TRADE_OP_CLOSE,
   TRADE_OP_DELETE,
   TRADE_OP_MODIFY
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
input double   LotPlus                 = 0.01;           // Plus
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

input string   __NEWS__                 = "=============== News Safety Filter ===============";
input bool     UseNewsFilter            = true;
input string   NewsCurrency             = "USD";
input int      NewsImportance           = 2;             // 2 = high impact
input int      NewsStopMinutes          = 30;
input int      NewsHardCloseMinutes     = 15;
input int      NewsResumeMinutes        = 60;

input string   __MA__                  = "=============== Moving Average Trade ===============";
input int      MA1                     = 50;             // Period
input ENUM_MA_METHOD      MA_METHOD1   = MODE_EMA;       // MA Method
input ENUM_APPLIED_PRICE  MA_PRICE1    = PRICE_CLOSE;    // Applied to

input string   SetComment              = "=============== Comment Setting ===============";
input bool     ShowComment             = true;           // Comment

int            OpenOrders=0;
int            CountB, CountS;
int            CountBS, CountSS;
int            BarB, BarS, count;
int            CountBar, LastBar, LastBarBuy, LastBarSell;
datetime       RecoveryRetryAfterBuy=0, RecoveryRetryAfterSell=0;
datetime       LegacyActionCooldownUntil=0;

datetime       time_open;
bool           success;
bool           ContinuebyTime;
bool           AutoRun = true;

string         EaName;
double         BuyPrice=0, SellPrice=0;
double         mylotsi=0;
 double         TP;
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
double         MinPriceBuy, MaxPriceBuy;
double         MinPriceSell, MaxPriceSell;

double         profit_max_buy, profit_min_buy;
double         profit_max_sell, profit_min_sell;
ulong          tick_max_buy, tick_min_buy;
ulong          tick_max_sell, tick_min_sell;

int            MaHandle=INVALID_HANDLE;
MqlCalendarValue NewsValues[];
datetime       NewsCacheAt=0;
datetime       NewsLastAttempt=0;
datetime       NewsLastErrorLog=0;
bool           NewsCacheValid=false;
datetime       NewsNextTime=0;
string         NewsNextName="-";
bool           newsTradeLocked=false;
bool           newsLiquidationPending=false;
datetime       newsLockUntil=0;
double         DailyPeakEquity=0, DailyMaxDDMoney=0, DailyMaxDDPercent=0;
double         PortfolioPeakEquity=0, PortfolioMaxDDMoney=0, PortfolioMaxDDPercent=0;
datetime       DailyTrackingDay=0;
double         CachedProfitToday=0;
datetime       ProfitCacheDay=0;
datetime       ProfitCacheAt=0;
bool           DashboardLayoutReady=false;
string         DashboardLabelNames[];
string         DashboardLabelText[];
color          DashboardLabelColor[];

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
   Trade.SetAsyncMode(false);
   EaName = MQLInfoString(MQL_PROGRAM_NAME); 

   if(FirstEntryMode==Entry_MA_Filter || FirstEntryMode==Entry_MA_Cross || FirstEntryMode==Entry_MA_Candle)
     {
      MaHandle=iMA(_Symbol,TimeFrame,MA1,0,MA_METHOD1,MA_PRICE1);
      if(MaHandle==INVALID_HANDLE)
         return(INIT_FAILED);
     }

   EventSetTimer(1);
   if(!MQLInfoInteger(MQL_TESTER))
      RefreshNewsCache(true);
   else
     {
      NewsCacheValid=true;
      NewsNextTime=0;
      NewsNextName="TESTER";
     }
   RestoreDrawdownTracking();
   RefreshDailyProfitCache(true);
   EnforceNewsSafety();

   for(int i=0;i<30;i++)
     {
      ObjectDelete(0,IntegerToString(i));
     }

   DeleteDashboardObjects();

   if(ShowComment)
      InitializeDashboardLayout();

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
   EventKillTimer();
   if(MaHandle!=INVALID_HANDLE)
     {
      IndicatorRelease(MaHandle);
      MaHandle=INVALID_HANDLE;
     }
  }

void OnTimer()
  {
   EnforceNewsSafety();
   RefreshDailyProfitCache(false);
   UpdateDrawdownTracking();
   if(ShowComment)
      Information();
  }

void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
  {
   if(trans.type==TRADE_TRANSACTION_DEAL_ADD)
      RefreshDailyProfitCache(true);
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

   ulong newestBuyMsc=0;
   ulong newestSellMsc=0;
   ulong newestBuyTicket=0;
   ulong newestSellTicket=0;

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
               S_Lot          += PositionGetDouble(POSITION_VOLUME);
               S_LotPrice     += PositionGetDouble(POSITION_VOLUME)*PositionGetDouble(POSITION_PRICE_OPEN);
               SumProfitSell  = SumProfitSell + PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);  

               ulong sellMsc=(ulong)PositionGetInteger(POSITION_TIME_MSC);
               ulong sellTicket=(ulong)PositionGetInteger(POSITION_TICKET);
               if(sellMsc>newestSellMsc || (sellMsc==newestSellMsc && sellTicket>newestSellTicket))
                 {
                  newestSellMsc=sellMsc;
                  newestSellTicket=sellTicket;
                  LastLotsSell=PositionGetDouble(POSITION_VOLUME);
                  BarS=iBarShift(Symbol(),TimeFrame,time_open);
                 }

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
               B_Lot          += PositionGetDouble(POSITION_VOLUME);
               B_LotPrice     += PositionGetDouble(POSITION_VOLUME)*PositionGetDouble(POSITION_PRICE_OPEN);
               SumProfitBuy   = SumProfitBuy + PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);  

               ulong buyMsc=(ulong)PositionGetInteger(POSITION_TIME_MSC);
               ulong buyTicket=(ulong)PositionGetInteger(POSITION_TICKET);
               if(buyMsc>newestBuyMsc || (buyMsc==newestBuyMsc && buyTicket>newestBuyTicket))
                 {
                  newestBuyMsc=buyMsc;
                  newestBuyTicket=buyTicket;
                  LastLotsBuy=PositionGetDouble(POSITION_VOLUME);
                  BarB=iBarShift(Symbol(),TimeFrame,time_open);
                 }

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

   ResetRecoveryBarStateForClosedBaskets();

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

   if(B_Lot!=0 && B_LotPrice!=0)
      B_Average=NormalizeDouble(B_LotPrice/B_Lot,_Digits);

   if(S_Lot!=0 && S_LotPrice!=0)
      S_Average=NormalizeDouble(S_LotPrice/S_Lot,_Digits);

   TPB = NormalizeDouble(B_Average+(TakeProfit*pips),_Digits);
   TPS = NormalizeDouble(S_Average-(TakeProfit*pips),_Digits);

    bool newsLock=EnforceNewsSafety();
    if(newsLock && newsLiquidationPending)
       return;

   // Preserve the legacy post-action cadence without blocking MT5's event loop.
   // News safety remains active through OnTimer while trade actions are suppressed.
   if(LegacyActionCooldownActive())
      return;

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
            bool modified=Trade.PositionModify(ticket,PositionGetDouble(POSITION_SL),TPB);
            ValidateTradeResult("PositionModify",TRADE_OP_MODIFY,modified,ticket);
           }

         if(PositionGetSymbol(i)==Symbol() &&
            TPS>0 &&
            PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_SELL &&
            PositionGetDouble(POSITION_TP)!=TPS &&
            PositionGetInteger(POSITION_MAGIC)==MagicNumber)
           {
            bool modified=Trade.PositionModify(ticket,PositionGetDouble(POSITION_SL),TPS);
            ValidateTradeResult("PositionModify",TRADE_OP_MODIFY,modified,ticket);
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
   double realizedProfitToday=CachedProfitToday;

   // ==============================
   // MODE BUY
   // ==============================
   if((ModeTradeP==BorS && OpenOrders<1) || (ModeTradeP==BandS) || (ModeTradeP==BuyOnly))
     {
      if(CountB<1 &&
         FirstEntrySignal(true) &&
         AutoRun &&
         !newsLock &&
         ContinuebyTime &&
         (realizedProfitToday<ProfitPerday || ProfitPerday==0))
        {
         BuyPrice= Ask;

         if(TakeProfit==0)
            TP=0;
         else
            TP=BuyPrice+TakeProfit*pips;	

          mylotsi = Lots;
          success = Trade.Buy(NormalizeLot(mylotsi),_Symbol,BuyPrice,0,TP,EaName+"-1");
          ValidateTradeResult("Buy",TRADE_OP_MARKET_OPEN,success,Trade.ResultDeal());
          SetLegacyActionCooldown();
          return;
        }
     }

   BuyPrice = Ask+Pending*pips;

   if(CountB>0 &&
      CountB<MaxOrder &&
      CountBS<1 &&
      !newsLock &&
      NewsNow()>=RecoveryRetryAfterBuy &&
      BarB>0 &&
       CountBar!=LastBar &&
      BuyPrice<MinPriceBuy &&
      MinPriceBuy-Ask>Distance*pips &&
      MinPriceBuy>0)
     {       
       count = CheckLastOrder(POSITION_TYPE_BUY);
       mylotsi=NormalizeDouble(LastLotsBuy+LotPlus,8);

      if(mylotsi>MaxLot)
        {
         mylotsi = MaxLot;
        }

      success = Trade.BuyStop(NormalizeLot(mylotsi),BuyPrice,_Symbol,0,0,0,0,EaName+"-"+IntegerToString(count+1));
       if(ValidateTradeResult("BuyStop",TRADE_OP_PENDING_CREATE,success,Trade.ResultOrder()))
        {
          LastBar=CountBar;
          LastBarBuy=CountBar;
          RecoveryRetryAfterBuy=0;
         }
       else
          RecoveryRetryAfterBuy=NewsNow()+5;
       SetLegacyActionCooldown();
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
         !newsLock &&
         ContinuebyTime &&
         (realizedProfitToday<ProfitPerday || ProfitPerday==0))
        {
         SellPrice=Bid;

         if(TakeProfit==0)
            TP=0;
         else
            TP=SellPrice-TakeProfit*pips;	

           mylotsi= Lots;
           success = Trade.Sell(NormalizeLot(mylotsi),_Symbol,SellPrice,0,TP,EaName+"-1");
          ValidateTradeResult("Sell",TRADE_OP_MARKET_OPEN,success,Trade.ResultDeal());
          SetLegacyActionCooldown();
          return;
        }
     }

   SellPrice = Bid-Pending*pips;

   if(CountS>0 &&
      CountSS<1 &&
      BarS>0 &&
      !newsLock &&
      NewsNow()>=RecoveryRetryAfterSell &&
       CountBar!=LastBar &&
      CountS<MaxOrder &&
      SellPrice>MaxPriceSell &&
      Bid-MaxPriceSell>Distance*pips &&
      MaxPriceSell>0)
     {       
      count = CheckLastOrder(POSITION_TYPE_SELL);
       mylotsi= Lots;
      mylotsi=NormalizeDouble(LastLotsSell+LotPlus,8);

      if(mylotsi>MaxLot)
        {
         mylotsi = MaxLot;
        }

      success = Trade.SellStop(NormalizeLot(mylotsi),SellPrice,_Symbol,0,0,0,0,EaName+"-"+IntegerToString(count+1));
       if(ValidateTradeResult("SellStop",TRADE_OP_PENDING_CREATE,success,Trade.ResultOrder()))
        {
          LastBar=CountBar;
          LastBarSell=CountBar;
          RecoveryRetryAfterSell=0;
         }
       else
          RecoveryRetryAfterSell=NewsNow()+5;
       SetLegacyActionCooldown();
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
                  bool modified=Trade.OrderModify(m_order.Ticket(),Ask+Pending*pips,0,0,0,0);
                  ValidateTradeResult("OrderModify",TRADE_OP_MODIFY,modified,m_order.Ticket());
                 }

               if(m_order.OrderType()==ORDER_TYPE_SELL_STOP && m_order.PriceOpen()<Bid-Pending*pips)
                 {
                  bool modified=Trade.OrderModify(m_order.Ticket(),Bid-Pending*pips,0,0,0,0);
                  ValidateTradeResult("OrderModify",TRADE_OP_MODIFY,modified,m_order.Ticket());
                 }
              }
           }
        }     
      }

   // The reference strategy evaluated exits after entry/recovery and pending management.
   if(RiskExitTriggered())
      return;

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
                  bool closed=Trade.PositionClose(m_position.Ticket());
                  if(ValidateTradeResult("SecureProfitBuyClose",TRADE_OP_CLOSE,closed,m_position.Ticket()))
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
                  bool closed=Trade.PositionClose(m_position.Ticket());
                  if(ValidateTradeResult("SecureProfitSellClose",TRADE_OP_CLOSE,closed,m_position.Ticket()))
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
   ObjectSetInteger(0,name,OBJPROP_XSIZE,218);
   ObjectSetInteger(0,name,OBJPROP_YSIZE,392);
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
   DashboardLayoutReady=false;
   ArrayResize(DashboardLabelNames,0);
   ArrayResize(DashboardLabelText,0);
   ArrayResize(DashboardLabelColor,0);
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
//| Compact dashboard: create layout once, update only changed values |
//+------------------------------------------------------------------+
int DashboardLabelIndex(string name)
  {
   for(int i=0;i<ArraySize(DashboardLabelNames);i++)
      if(DashboardLabelNames[i]==name)
         return(i);
   return(-1);
  }

void CreateDashboardLabel(string name,string text,int x,int y,int fontSize,string font,color fontcolor)
  {
   ObjectCreate(0,name,OBJ_LABEL,0,0,0,0,0);
   ObjectSetInteger(0,name,OBJPROP_CORNER,CORNER_RIGHT_UPPER);
   ObjectSetInteger(0,name,OBJPROP_ANCHOR,ANCHOR_RIGHT_UPPER);
   ObjectSetInteger(0,name,OBJPROP_XDISTANCE,x);
   ObjectSetInteger(0,name,OBJPROP_YDISTANCE,y);
   ObjectSetString(0,name,OBJPROP_TEXT,text);
   ObjectSetString(0,name,OBJPROP_FONT,font);
   ObjectSetInteger(0,name,OBJPROP_COLOR,fontcolor);
   ObjectSetInteger(0,name,OBJPROP_FONTSIZE,fontSize);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,name,OBJPROP_SELECTED,false);
   ObjectSetInteger(0,name,OBJPROP_HIDDEN,true);
   ObjectSetInteger(0,name,OBJPROP_ZORDER,1);

   int index=ArraySize(DashboardLabelNames);
   ArrayResize(DashboardLabelNames,index+1);
   ArrayResize(DashboardLabelText,index+1);
   ArrayResize(DashboardLabelColor,index+1);
   DashboardLabelNames[index]=name;
   DashboardLabelText[index]=text;
   DashboardLabelColor[index]=fontcolor;
  }

void SetDashboardValue(string name,string text,color fontcolor)
  {
   int index=DashboardLabelIndex(name);
   if(index<0)
      return;

   if(DashboardLabelText[index]!=text)
     {
      ObjectSetString(0,name,OBJPROP_TEXT,text);
      DashboardLabelText[index]=text;
     }
   if(DashboardLabelColor[index]!=fontcolor)
     {
      ObjectSetInteger(0,name,OBJPROP_COLOR,fontcolor);
      DashboardLabelColor[index]=fontcolor;
     }
  }

void InitializeDashboardLayout()
  {
   CreateDashboardPanel();
   const int labelX=130;
   const int valueX=12;
   const int normal=8;
   const int title=9;

   CreateDashboardLabel("DB_TITLE","SUSANOO 2.3",82,26,title,"Arial",clrWhite);
   CreateDashboardLabel("DB_STATUS","WAITING",valueX,26,normal,"Arial",clrSilver);
   CreateDashboardLabel("DB_SYMBOL",_Symbol,labelX,44,title,"Arial",clrWhite);
   CreateDashboardLabel("DB_MAGIC","#"+IntegerToString(MagicNumber),valueX,44,normal,"Arial",clrSilver);

   CreateDashboardLabel("DB_STRATEGY_HEAD","STRATEGY",80,60,normal,"Arial",clrSilver);
   CreateDashboardLabel("DB_L_ENTRY","Entry",labelX,76,normal,"Arial",clrDimGray);
   CreateDashboardLabel("DB_V_ENTRY",FirstEntryModeName(),valueX,76,normal,"Arial",clrWhite);
   CreateDashboardLabel("DB_L_MODE","Mode",labelX,91,normal,"Arial",clrDimGray);
   CreateDashboardLabel("DB_V_MODE",ModeTradeName(),valueX,91,normal,"Arial",clrWhite);
   CreateDashboardLabel("DB_L_TIME","Time",labelX,106,normal,"Arial",clrDimGray);
   CreateDashboardLabel("DB_V_TIME","-",valueX,106,normal,"Arial",clrSilver);

   CreateDashboardLabel("DB_POSITION_HEAD","POSITIONS",76,122,normal,"Arial",clrSilver);
   CreateDashboardLabel("DB_BUY_HEAD","BUY",labelX,138,normal,"Arial",clrWhite);
   CreateDashboardLabel("DB_L_BUY_ORDERS","Orders / Lot",labelX,153,normal,"Arial",clrDimGray);
   CreateDashboardLabel("DB_BUY_V1","-",valueX,153,normal,"Arial",clrWhite);
   CreateDashboardLabel("DB_L_BUY_AVG","Average",labelX,168,normal,"Arial",clrDimGray);
   CreateDashboardLabel("DB_BUY_V2","-",valueX,168,normal,"Arial",clrWhite);
   CreateDashboardLabel("DB_L_BUY_PL","P/L",labelX,183,normal,"Arial",clrDimGray);
   CreateDashboardLabel("DB_BUY_V3","$0.00",valueX,183,title,"Arial",clrWhite);
   CreateDashboardLabel("DB_SELL_HEAD","SELL",labelX,199,normal,"Arial",clrWhite);
   CreateDashboardLabel("DB_L_SELL_ORDERS","Orders / Lot",labelX,214,normal,"Arial",clrDimGray);
   CreateDashboardLabel("DB_SELL_V1","-",valueX,214,normal,"Arial",clrWhite);
   CreateDashboardLabel("DB_L_SELL_AVG","Average",labelX,229,normal,"Arial",clrDimGray);
   CreateDashboardLabel("DB_SELL_V2","-",valueX,229,normal,"Arial",clrWhite);
   CreateDashboardLabel("DB_L_SELL_PL","P/L",labelX,244,normal,"Arial",clrDimGray);
   CreateDashboardLabel("DB_SELL_V3","$0.00",valueX,244,title,"Arial",clrWhite);

   CreateDashboardLabel("DB_ACCOUNT_HEAD","ACCOUNT",82,260,normal,"Arial",clrSilver);
   CreateDashboardLabel("DB_L_FLOATING","Floating",labelX,275,normal,"Arial",clrDimGray);
   CreateDashboardLabel("DB_ACC_V1","$0.00",valueX,275,title,"Arial",clrWhite);
   CreateDashboardLabel("DB_L_TODAY","Today",labelX,290,normal,"Arial",clrDimGray);
   CreateDashboardLabel("DB_ACC_V2","$0.00",valueX,290,normal,"Arial",clrWhite);
   CreateDashboardLabel("DB_L_EQUITY","Equity",labelX,305,normal,"Arial",clrDimGray);
   CreateDashboardLabel("DB_ACC_V3","-",valueX,305,normal,"Arial",clrWhite);
   CreateDashboardLabel("DB_L_BALANCE","Balance",labelX,320,normal,"Arial",clrDimGray);
   CreateDashboardLabel("DB_ACC_V4","-",valueX,320,normal,"Arial",clrWhite);
   CreateDashboardLabel("DB_L_DAILY_DD","Daily DD",labelX,335,normal,"Arial",clrDimGray);
   CreateDashboardLabel("DB_ACC_V5","-",valueX,335,normal,"Arial",clrWhite);
   CreateDashboardLabel("DB_L_PORTFOLIO_DD","Portfolio DD",labelX,350,normal,"Arial",clrDimGray);
   CreateDashboardLabel("DB_ACC_V6","-",valueX,350,normal,"Arial",clrWhite);

   CreateDashboardLabel("DB_SAFETY_HEAD","SAFETY",86,366,normal,"Arial",clrSilver);
   CreateDashboardLabel("DB_NEWS_L","News",labelX,381,normal,"Arial",clrDimGray);
   CreateDashboardLabel("DB_NEWS_V","-",valueX,381,normal,"Arial",clrSilver);
   CreateDashboardLabel("DB_L_NEXT","Next",labelX,396,normal,"Arial",clrDimGray);
   CreateDashboardLabel("DB_NEWS_TIME","-",valueX,396,normal,"Arial",clrSilver);
   DashboardLayoutReady=true;
  }

//+------------------------------------------------------------------+
//| Dashboard                                                        |
//+------------------------------------------------------------------+
void Information()
  {
   if(!DashboardLayoutReady)
      return;

   color normalCol=clrWhite;
   color buyCol=(SumProfitBuy>0 ? clrLime : (SumProfitBuy<0 ? clrTomato : clrWhite));
   color sellCol=(SumProfitSell>0 ? clrLime : (SumProfitSell<0 ? clrTomato : clrWhite));
   color totalCol=(Profit>0 ? clrLime : (Profit<0 ? clrTomato : clrWhite));
   string statusText=AutoRun ? "RUNNING" : "PAUSED";
   color statusCol=AutoRun ? clrLime : clrOrange;
   if(newsLiquidationPending)
     {
      statusText="LIQUIDATING";
      statusCol=clrTomato;
     }
   else if(newsTradeLocked)
     {
      statusText="NEWS LOCK";
      statusCol=clrTomato;
     }

   string timeText=ContinuebyTime ? "OPEN" : "BLOCKED";
   color timeCol=ContinuebyTime ? clrLime : clrOrange;
   double todayProfit=ProfitToday();
   color todayCol=(todayProfit>0 ? clrLime : (todayProfit<0 ? clrTomato : clrWhite));
   string newsText=newsLiquidationPending ? "LIQUIDATING" : (newsTradeLocked ? "CLOSED" : "OPEN");
   color newsCol=(newsLiquidationPending || newsTradeLocked) ? clrTomato : clrLime;

   SetDashboardValue("DB_STATUS",statusText,statusCol);
   SetDashboardValue("DB_V_TIME",timeText,timeCol);
   SetDashboardValue("DB_BUY_V1",IntegerToString(CountB)+" / "+DoubleToString(B_Lot,2),normalCol);
   SetDashboardValue("DB_BUY_V2",ShowPriceOrDash(B_Average),normalCol);
   SetDashboardValue("DB_BUY_V3",MoneyText(SumProfitBuy),buyCol);
   SetDashboardValue("DB_SELL_V1",IntegerToString(CountS)+" / "+DoubleToString(S_Lot,2),normalCol);
   SetDashboardValue("DB_SELL_V2",ShowPriceOrDash(S_Average),normalCol);
   SetDashboardValue("DB_SELL_V3",MoneyText(SumProfitSell),sellCol);
   SetDashboardValue("DB_ACC_V1",MoneyText(Profit),totalCol);
   SetDashboardValue("DB_ACC_V2",MoneyText(todayProfit),todayCol);
   SetDashboardValue("DB_ACC_V3","$"+TestCommaFormat(AccountInfoDouble(ACCOUNT_EQUITY),2),normalCol);
   SetDashboardValue("DB_ACC_V4","$"+TestCommaFormat(AccountInfoDouble(ACCOUNT_BALANCE),2),normalCol);
   SetDashboardValue("DB_ACC_V5","$"+TestCommaFormat(DailyMaxDDMoney,2)+" | "+DoubleToString(DailyMaxDDPercent,2)+"%",normalCol);
   SetDashboardValue("DB_ACC_V6","$"+TestCommaFormat(PortfolioMaxDDMoney,2)+" | "+DoubleToString(PortfolioMaxDDPercent,2)+"%",normalCol);
   SetDashboardValue("DB_NEWS_V",newsText,newsCol);
   SetDashboardValue("DB_NEWS_TIME",NewsNextTime>0 ? TimeToString(NewsNextTime,TIME_DATE|TIME_MINUTES) : "-",normalCol);
  }

void LegacyInformationUnused()
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

    SetText("DB_ACC_L5","Daily Max DD",
            xLabel,314,fs,"Arial",mutedCol);
   SetText("DB_ACC_V5",
            "$"+TestCommaFormat(DailyMaxDDMoney,2)+
            " | "+DoubleToString(DailyMaxDDPercent,2)+"%",
            xValue,314,fs,"Arial",clrTomato);

    SetText("DB_ACC_L6","Portfolio Max DD",
           xLabel,329,fs,"Arial",mutedCol);
   SetText("DB_ACC_V6",
            "$"+TestCommaFormat(PortfolioMaxDDMoney,2)+" | "+DoubleToString(PortfolioMaxDDPercent,2)+"%",
            xValue,329,fs,"Arial",normalCol);

   bool newsClosed=newsTradeLocked;
   bool testerMode=MQLInfoInteger(MQL_TESTER);
   string dashboardNews=testerMode ? "TESTER" : (NewsNextTime>0 ? NewsNextName : "-");
   SetText("DB_NEWS_L","News",
           xLabel,344,fs,"Arial",mutedCol);
   SetText("DB_NEWS_V",newsClosed ? "CLOSED" : "OPEN",
           xValue,344,fs,"Arial",newsClosed ? clrTomato : clrLime);
   SetText("DB_NEWS_TIME",NewsNextTime>0 ? TimeToString(NewsNextTime,TIME_DATE|TIME_MINUTES) : "-",
           xValue,359,fs,"Arial",mutedCol);
   SetText("DB_NEWS_NAME",dashboardNews,
           xValue,374,fs,"Arial",mutedCol);
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
//| Cached daily realized profit                                     |
//+------------------------------------------------------------------+
datetime CurrentServerDay()
  {
   return(StringToTime(TimeToString(NewsNow(),TIME_DATE)));
  }

void RefreshDailyProfitCache(bool force)
  {
   datetime day=CurrentServerDay();
   datetime now=NewsNow();
   if(!force && ProfitCacheDay==day && ProfitCacheAt>0 && now-ProfitCacheAt<60)
      return;

   ulong deal_ticket;
   ulong type;
   ulong magic;
   string sym;
   double value=0;
   datetime from_date=day;

   if(HistorySelect(from_date,now))
     {
      for(int i=0;i<HistoryDealsTotal();i++)
        {
         deal_ticket=HistoryDealGetTicket(i);
         type=HistoryDealGetInteger(deal_ticket,DEAL_TYPE);
         magic=HistoryDealGetInteger(deal_ticket,DEAL_MAGIC);
         sym=HistoryDealGetString(deal_ticket,DEAL_SYMBOL);
         if(type<=1 && magic==MagicNumber && sym==_Symbol)
           {
            value+=HistoryDealGetDouble(deal_ticket,DEAL_PROFIT)+
                   HistoryDealGetDouble(deal_ticket,DEAL_SWAP)+
                   HistoryDealGetDouble(deal_ticket,DEAL_COMMISSION);
           }
        }
     }

   CachedProfitToday=value;
   ProfitCacheDay=day;
   ProfitCacheAt=now;
  }

double ProfitToday()
  {
   return(CachedProfitToday);
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
                     bool modified=Trade.PositionModify(ticket,tss,PositionGetDouble(POSITION_TP));
                     ValidateTradeResult("TrailingSellModify",TRADE_OP_MODIFY,modified,ticket);
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
                     bool modified=Trade.PositionModify(ticket,tss,PositionGetDouble(POSITION_TP));
                     ValidateTradeResult("TrailingBuyModify",TRADE_OP_MODIFY,modified,ticket);
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
double GetMA(int shift=1)
  {
   if(MaHandle==INVALID_HANDLE || shift<0)
      return(0);

   double maBuffer[1];
   int maCopy=CopyBuffer(MaHandle,0,shift,1,maBuffer);

   if(maCopy!=1)
      return(0);

   return(maBuffer[0]);
  }

//+------------------------------------------------------------------+
//| Validate a trade request with operation-specific server results  |
//+------------------------------------------------------------------+
bool ValidateTradeResult(string operation,
                         ENUM_EA_TRADE_OPERATION operationType,
                         bool requestOk,
                         ulong ticket=0)
  {
   uint retcode=Trade.ResultRetcode();
   bool accepted=false;

   if(requestOk)
     {
      switch(operationType)
        {
         case TRADE_OP_MARKET_OPEN:
            accepted=(retcode==TRADE_RETCODE_DONE || retcode==TRADE_RETCODE_DONE_PARTIAL);
            break;
         case TRADE_OP_PENDING_CREATE:
            accepted=(retcode==TRADE_RETCODE_PLACED || retcode==TRADE_RETCODE_DONE);
            break;
         case TRADE_OP_CLOSE:
            accepted=(retcode==TRADE_RETCODE_DONE);
            break;
         case TRADE_OP_DELETE:
            accepted=(retcode==TRADE_RETCODE_DONE);
            break;
         case TRADE_OP_MODIFY:
            accepted=(retcode==TRADE_RETCODE_DONE || retcode==TRADE_RETCODE_NO_CHANGES);
            break;
        }
     }

   if(!accepted)
      Print("Trade failure operation=",operation,
            " symbol=",_Symbol,
            " magic=",MagicNumber,
            " ticket=",ticket,
            " request_ok=",requestOk,
            " retcode=",retcode,
            " description=",Trade.ResultRetcodeDescription());
   return(accepted);
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
               value=MathMax(value,(int)StringToInteger(parts[nub-1]));
          }
       }
     }

   for(int i=0;i<OrdersTotal();i++)
     {
      if(!m_order.SelectByIndex(i) || m_order.Symbol()!=_Symbol || m_order.Magic()!=MagicNumber)
         continue;
      if((type==POSITION_TYPE_BUY && m_order.OrderType()!=ORDER_TYPE_BUY_STOP) ||
         (type==POSITION_TYPE_SELL && m_order.OrderType()!=ORDER_TYPE_SELL_STOP))
         continue;
      int nub=StringSplit(m_order.Comment(),'-',parts);
      if(nub>=2)
         value=MathMax(value,(int)StringToInteger(parts[nub-1]));
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
   double ma1 = 0;
   double ma2 = 0;

   if(FirstEntryMode==Entry_MA_Filter || FirstEntryMode==Entry_MA_Cross || FirstEntryMode==Entry_MA_Candle)
     {
      ma1=GetMA(1);
      if(FirstEntryMode==Entry_MA_Cross)
         ma2=GetMA(2);
       if(c1==0 || (FirstEntryMode==Entry_MA_Cross && c2==0) ||
          ma1==0 || (FirstEntryMode==Entry_MA_Cross && ma2==0))
         return(false);
     }

   switch(FirstEntryMode)
     {
      case Entry_MA_Filter:
         return(isBuy ? c1>ma1 : c1<ma1);

      case Entry_MA_Cross:
         return(isBuy ? (c2<=ma2 && c1>ma1) : (c2>=ma2 && c1<ma1));

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

void ResetRecoveryBarStateForClosedBaskets()
  {
   if(CountB==0 && CountBS==0)
     {
      LastBarBuy=0;
      RecoveryRetryAfterBuy=0;
     }
   if(CountS==0 && CountSS==0)
     {
      LastBarSell=0;
      RecoveryRetryAfterSell=0;
     }
   }

//+------------------------------------------------------------------+
//| Legacy action cadence without a blocking Sleep                    |
//+------------------------------------------------------------------+
void SetLegacyActionCooldown()
  {
   LegacyActionCooldownUntil=NewsNow()+5;
  }

bool LegacyActionCooldownActive()
  {
   return(NewsNow()<LegacyActionCooldownUntil);
  }

//+------------------------------------------------------------------+
//| Cached MT5 economic-calendar safety layer                         |
//+------------------------------------------------------------------+
datetime NewsNow()
  {
   datetime now=TimeTradeServer();
   if(now<=0) now=TimeCurrent();
   return(now);
  }

void RefreshNewsCache(bool force)
  {
   if(!UseNewsFilter) return;
   if(MQLInfoInteger(MQL_TESTER))
     {
      NewsCacheValid=true;
      NewsNextTime=0;
      NewsNextName="TESTER";
      return;
     }
   datetime now=NewsNow();
   if(!force && NewsCacheAt>0 && now-NewsCacheAt<3600) return;
   if(!force && NewsLastAttempt>0 && now-NewsLastAttempt<60) return;
   NewsLastAttempt=now;
   MqlCalendarValue values[];
   int lookbackMinutes=MathMax(NewsResumeMinutes,60)+60;
   int copied=CalendarValueHistory(values,now-lookbackMinutes*60,now+3*86400,"",NewsCurrency);
   if(copied<0)
     {
      int error=GetLastError();
      if(NewsLastErrorLog==0 || now-NewsLastErrorLog>=300)
        {
         Print("News calendar unavailable; no new News lock applied. error=",error);
         NewsLastErrorLog=now;
        }
      return; // retain an active valid cache, but do not lock a normal day with no cache.
     }
   if(copied==0 && NewsCacheValid && (newsLiquidationPending || now<newsLockUntil))
      return;
   ArrayResize(NewsValues,copied);
   for(int i=0;i<copied;i++) NewsValues[i]=values[i];
   NewsCacheAt=now;
   NewsCacheValid=true;
  }

bool IsQualifyingNews(int index,datetime &eventTime,string &eventName)
  {
   if(index<0 || index>=ArraySize(NewsValues)) return(false);
   if(MQLInfoInteger(MQL_TESTER)) return(false);
   MqlCalendarEvent event;
   if(!CalendarEventById(NewsValues[index].event_id,event)) return(false);
   string currency=NewsCurrency;
   StringToUpper(currency);
   if(currency!="USD") return(false);
   if(event.importance!=CALENDAR_IMPORTANCE_HIGH) return(false);
   eventTime=NewsValues[index].time;
   eventName=event.name;
   string lowerName=eventName;
   StringToLower(lowerName);
   string keywords[10]=
     {"cpi","consumer price index","ppi","producer price index","nfp",
      "non-farm payrolls","nonfarm payrolls","non-farm employment",
      "nonfarm employment change","fomc"};
   for(int i=0;i<ArraySize(keywords);i++)
      if(StringFind(lowerName,keywords[i])>=0)
         return(true);
   string rateKeywords[5]=
     {"federal funds rate","fed interest rate decision",
      "federal reserve interest rate decision","fed rate decision","powell"};
   for(int i=0;i<ArraySize(rateKeywords);i++)
      if(StringFind(lowerName,rateKeywords[i])>=0)
         return(true);
   return(false);
  }

void CountMatchingExposure(int &positionsRemaining,int &ordersRemaining)
  {
   positionsRemaining=0;
   ordersRemaining=0;
   for(int i=0;i<PositionsTotal();i++)
     {
      if(!m_position.SelectByIndex(i)) continue;
      if(m_position.Symbol()==_Symbol && m_position.Magic()==MagicNumber)
         positionsRemaining++;
     }
   for(int i=0;i<OrdersTotal();i++)
     {
      if(!m_order.SelectByIndex(i)) continue;
      if(m_order.Symbol()==_Symbol && m_order.Magic()==MagicNumber)
         ordersRemaining++;
     }
  }

void UpdateNewsState(bool &windowActive,bool &hardCloseActive)
  {
   windowActive=false;
   hardCloseActive=false;
   if(!UseNewsFilter && !newsLiquidationPending)
      return;

   RefreshNewsCache(false);
   datetime now=NewsNow();
   NewsNextTime=0;
   NewsNextName="-";

   for(int i=0;i<ArraySize(NewsValues);i++)
     {
      datetime eventTime; string eventName;
      if(!IsQualifyingNews(i,eventTime,eventName)) continue;
      datetime protectionEnd=eventTime+NewsResumeMinutes*60;
      if(eventTime>=now && (NewsNextTime==0 || eventTime<NewsNextTime))
        { NewsNextTime=eventTime; NewsNextName=eventName; }
      if(now>=eventTime-NewsStopMinutes*60 && now<protectionEnd)
        {
         windowActive=true;
         newsLockUntil=(datetime)MathMax((long)newsLockUntil,(long)protectionEnd);
        }
      if(now>=eventTime-NewsHardCloseMinutes*60 && now<protectionEnd)
         hardCloseActive=true;
     }

   if(now<newsLockUntil)
      windowActive=true;
  }

bool EnforceNewsSafety()
  {
   if(MQLInfoInteger(MQL_TESTER))
     {
      newsTradeLocked=false;
      newsLiquidationPending=false;
      NewsNextTime=0;
      NewsNextName="TESTER";
      return(false);
     }
   bool windowActive=false;
   bool hardCloseActive=false;
   UpdateNewsState(windowActive,hardCloseActive);

   if(!UseNewsFilter && !newsLiquidationPending)
     {
      newsTradeLocked=false;
      return(false);
     }

   if(hardCloseActive)
      newsLiquidationPending=true;

   int positionsRemaining=0;
   int ordersRemaining=0;
   CountMatchingExposure(positionsRemaining,ordersRemaining);
   bool mustLock=windowActive || newsLiquidationPending ||
                 (positionsRemaining>0 && hardCloseActive);
   if(!mustLock)
     {
      newsTradeLocked=false;
      return(false);
     }

   newsTradeLocked=true;
   DeleteOrdersByType();
   if(newsLiquidationPending)
      ClosePositionsByType();

   CountMatchingExposure(positionsRemaining,ordersRemaining);
   if(newsLiquidationPending && positionsRemaining==0 && ordersRemaining==0)
      newsLiquidationPending=false;

   if(newsLiquidationPending || windowActive || positionsRemaining>0 || ordersRemaining>0)
      return(true);

   newsTradeLocked=false;
   return(false);
  }

double PersistGlobalMaximum(string name,double candidate)
  {
   if(!GlobalVariableCheck(name))
      GlobalVariableSet(name,candidate);
   for(int attempt=0;attempt<5;attempt++)
     {
      double current=GlobalVariableGet(name);
      if(candidate<=current)
         return(current);
      if(GlobalVariableSetOnCondition(name,candidate,current))
         return(candidate);
     }
   return(MathMax(candidate,GlobalVariableGet(name)));
  }

string AccountDDPrefix()
  {
   return("EA_Susanoo_DD_"+IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)));
  }

void RestoreDrawdownTracking()
  {
   string prefix=AccountDDPrefix();
   PortfolioPeakEquity=GlobalVariableGet(prefix+"_Peak");
   PortfolioMaxDDMoney=GlobalVariableGet(prefix+"_Max");
   PortfolioMaxDDPercent=GlobalVariableGet(prefix+"_MaxPercent");
   if(PortfolioPeakEquity<=0) PortfolioPeakEquity=AccountInfoDouble(ACCOUNT_EQUITY);
   DailyTrackingDay=(datetime)GlobalVariableGet(prefix+"_Day");
   DailyPeakEquity=GlobalVariableGet(prefix+"_DailyPeak");
   DailyMaxDDMoney=GlobalVariableGet(prefix+"_DailyMax");
  }

void UpdateDrawdownTracking()
  {
   datetime now=NewsNow();
   datetime day=StringToTime(TimeToString(now,TIME_DATE));
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   if(DailyTrackingDay!=day)
     { DailyTrackingDay=day; DailyPeakEquity=equity; DailyMaxDDMoney=0; DailyMaxDDPercent=0; }
   if(equity>DailyPeakEquity) DailyPeakEquity=equity;
   double dailyDD=MathMax(0.0,DailyPeakEquity-equity);
   DailyMaxDDMoney=MathMax(DailyMaxDDMoney,dailyDD);
   DailyMaxDDPercent=DailyPeakEquity>0 ? DailyMaxDDMoney/DailyPeakEquity*100.0 : 0;
   if(equity>PortfolioPeakEquity) PortfolioPeakEquity=equity;
   double portfolioDD=MathMax(0.0,PortfolioPeakEquity-equity);
   PortfolioMaxDDMoney=MathMax(PortfolioMaxDDMoney,portfolioDD);
   PortfolioMaxDDPercent=PortfolioPeakEquity>0 ? PortfolioMaxDDMoney/PortfolioPeakEquity*100.0 : 0;
   string prefix=AccountDDPrefix();
   PortfolioPeakEquity=PersistGlobalMaximum(prefix+"_Peak",PortfolioPeakEquity);
   PortfolioMaxDDMoney=PersistGlobalMaximum(prefix+"_Max",PortfolioMaxDDMoney);
   PortfolioMaxDDPercent=PortfolioPeakEquity>0 ? PortfolioMaxDDMoney/PortfolioPeakEquity*100.0 : 0;
   PortfolioMaxDDPercent=PersistGlobalMaximum(prefix+"_MaxPercent",PortfolioMaxDDPercent);
   GlobalVariableSet(prefix+"_Day",(double)DailyTrackingDay);
   GlobalVariableSet(prefix+"_DailyPeak",DailyPeakEquity);
   GlobalVariableSet(prefix+"_DailyMax",DailyMaxDDMoney);
  }

//+------------------------------------------------------------------+
//| Evaluate high-priority risk exits before opening anything         |
//+------------------------------------------------------------------+
bool RiskExitTriggered()
  {
   bool triggered=false;
   if(CountB!=0 && SumProfitBuy>=TP2 && TP2>0)
     {
      ClosePositionsByType(POSITION_TYPE_BUY);
      DeleteOrdersByType(ORDER_TYPE_BUY_STOP);
      triggered=true;
     }
   if(CountS!=0 && SumProfitSell>=TP2 && TP2>0)
     {
      ClosePositionsByType(POSITION_TYPE_SELL);
      DeleteOrdersByType(ORDER_TYPE_SELL_STOP);
      triggered=true;
     }
   if(OpenOrders!=0 && Profit<=-SL2 && SL2>0)
     {
      ClosePositionsByType();
      DeleteOrdersByType();
      if(StopEA) AutoRun=false;
      triggered=true;
     }
   if(OpenOrders!=0 && Profit<=-(SL3*AccountInfoDouble(ACCOUNT_BALANCE)/100) && SL3>0)
     {
      ClosePositionsByType();
      DeleteOrdersByType();
      if(StopEA) AutoRun=false;
      triggered=true;
     }
   if(OpenOrders!=0 && Profit>=(TP3*AccountInfoDouble(ACCOUNT_BALANCE)/100) && TP3>0)
     {
      ClosePositionsByType();
      DeleteOrdersByType();
      triggered=true;
     }
   return(triggered);
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

   for(int i=0; i<n; i++)
     {
      if(trades[i]>0)
        {
         bool closed=Trade.PositionClose(trades[i]);
         ValidateTradeResult("PositionClose",TRADE_OP_CLOSE,closed,trades[i]);
        }
     }
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

      bool deleted=Trade.OrderDelete(m_order.Ticket());
      ValidateTradeResult("OrderDelete",TRADE_OP_DELETE,deleted,m_order.Ticket());
     }
  }
//+------------------------------------------------------------------+

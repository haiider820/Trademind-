class MarketCandle {
  final DateTime time;
  final double open;
  final double high;
  final double low;
  final double close;
  final double volume;

  const MarketCandle({
    required this.time,
    required this.open,
    required this.high,
    required this.low,
    required this.close,
    required this.volume,
  });

  factory MarketCandle.fromJson(Map<String, dynamic> json) {
    return MarketCandle(
      time: DateTime.fromMillisecondsSinceEpoch((json['open_time'] as num).toInt()),
      open: (json['open'] as num).toDouble(),
      high: (json['high'] as num).toDouble(),
      low: (json['low'] as num).toDouble(),
      close: (json['close'] as num).toDouble(),
      volume: (json['volume'] as num).toDouble(),
    );
  }
}

class MarketSummaryItem {
  final String symbol;
  final double price;
  final double change24h;
  final double high24h;
  final double low24h;
  final double volume24h;
  final double? openInterest;
  final String updatedAt;

  const MarketSummaryItem({
    required this.symbol,
    required this.price,
    required this.change24h,
    required this.high24h,
    required this.low24h,
    required this.volume24h,
    required this.openInterest,
    required this.updatedAt,
  });

  factory MarketSummaryItem.fromJson(Map<String, dynamic> json) {
    return MarketSummaryItem(
      symbol: (json['symbol'] as String?) ?? '',
      price: (json['price'] as num?)?.toDouble() ?? 0,
      change24h: (json['change_24h'] as num?)?.toDouble() ?? 0,
      high24h: (json['high_24h'] as num?)?.toDouble() ?? 0,
      low24h: (json['low_24h'] as num?)?.toDouble() ?? 0,
      volume24h: (json['volume_24h'] as num?)?.toDouble() ?? 0,
      openInterest: (json['open_interest'] as num?)?.toDouble(),
      updatedAt: (json['updated_at'] as String?) ?? '',
    );
  }
}

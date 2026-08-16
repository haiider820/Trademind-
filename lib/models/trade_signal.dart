class TradeSignal {
  TradeSignal({
    required this.id,
    required this.pair,
    required this.tradeType,
    required this.entry,
    required this.sl,
    required this.tp,
    required this.status,
    required this.pnl,
    required this.riskLevel,
    required this.createdAt,
  });

  final String id;
  final String pair;
  final String tradeType;
  final double entry;
  final double sl;
  final double tp;
  final String status;
  final double pnl;
  final String riskLevel;
  final DateTime createdAt;

  factory TradeSignal.fromJson(Map<String, dynamic> json) {
    return TradeSignal(
      id: json['id'].toString(),
      pair: json['pair'] as String,
      tradeType: json['trade_type'] as String,
      entry: (json['entry'] as num).toDouble(),
      sl: (json['sl'] as num).toDouble(),
      tp: (json['tp'] as num).toDouble(),
      status: json['status'] as String,
      pnl: (json['pnl'] as num).toDouble(),
      riskLevel: json['risk_level'] as String,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }
}

class MarketOverview {
  MarketOverview({
    required this.btcPrice,
    required this.ethPrice,
    required this.marketCap,
    required this.fearGreedIndex,
    required this.fearGreedClassification,
    required this.btcDominance,
    required this.updatedAt,
  });

  final double btcPrice;
  final double ethPrice;
  final double marketCap;
  final int fearGreedIndex;
  final String fearGreedClassification;
  final double btcDominance;
  final DateTime updatedAt;

  factory MarketOverview.fromJson(Map<String, dynamic> json) {
    return MarketOverview(
      btcPrice: (json['btc_price'] as num).toDouble(),
      ethPrice: (json['eth_price'] as num).toDouble(),
      marketCap: (json['market_cap'] as num).toDouble(),
      fearGreedIndex: json['fear_greed_index'] as int,
      fearGreedClassification: json['fear_greed_classification'] as String,
      btcDominance: (json['btc_dominance'] as num).toDouble(),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }
}

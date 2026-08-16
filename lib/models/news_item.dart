class NewsItem {
  NewsItem({
    required this.id,
    required this.title,
    required this.sentiment,
    required this.category,
    required this.source,
    required this.publishedAt,
  });

  final String id;
  final String title;
  final String sentiment;
  final String category;
  final String source;
  final DateTime publishedAt;

  factory NewsItem.fromJson(Map<String, dynamic> json) {
    return NewsItem(
      id: json['id'].toString(),
      title: json['title'] as String,
      sentiment: json['sentiment'] as String,
      category: json['category'] as String,
      source: json['source'] as String? ?? 'Unknown',
      publishedAt: DateTime.parse(json['published_at'] as String),
    );
  }
}

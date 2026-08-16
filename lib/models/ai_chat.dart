class AiChatMessage {
  AiChatMessage({
    required this.role,
    required this.content,
  });

  final String role;
  final String content;

  Map<String, dynamic> toJson() => {
        'role': role,
        'content': content,
      };
}

class AiChatResponse {
  AiChatResponse({
    required this.reply,
    required this.confidence,
    required this.marketBias,
    required this.riskNotes,
    required this.suggestedAction,
  });

  final String reply;
  final double confidence;
  final String marketBias;
  final List<String> riskNotes;
  final String suggestedAction;

  factory AiChatResponse.fromJson(Map<String, dynamic> json) {
    return AiChatResponse(
      reply: json['reply'] as String,
      confidence: (json['confidence'] as num).toDouble(),
      marketBias: json['market_bias'] as String,
      riskNotes: (json['risk_notes'] as List<dynamic>).map((e) => e.toString()).toList(),
      suggestedAction: json['suggested_action'] as String,
    );
  }
}

class WeeklyThesisBundle {
  final DateTime generatedAt;
  final DateTime expiresAt;
  final List<Thesis> theses;

  const WeeklyThesisBundle({
    required this.generatedAt,
    required this.expiresAt,
    required this.theses,
  });

  bool get isExpired => DateTime.now().isAfter(expiresAt);

  Duration get timeUntilExpiry => expiresAt.difference(DateTime.now());

  factory WeeklyThesisBundle.fromJson(Map<String, dynamic> json) {
    return WeeklyThesisBundle(
      generatedAt: DateTime.parse(json['generated_at'] as String),
      expiresAt: DateTime.parse(json['expires_at'] as String),
      theses: (json['theses'] as List<dynamic>)
          .map((t) => Thesis.fromJson(t as Map<String, dynamic>))
          .toList(),
    );
  }
}

class Thesis {
  final String ticker;
  final String thesis;
  final double confidence;
  final double? targetEntryPrice;
  final double? stopLossPrice;
  final double? takeProfitPrice;
  final String thesisBreachCondition;
  final String reasoning;
  final String? sector;
  final bool selectedForTrading;

  const Thesis({
    required this.ticker,
    required this.thesis,
    required this.confidence,
    this.targetEntryPrice,
    this.stopLossPrice,
    this.takeProfitPrice,
    required this.thesisBreachCondition,
    required this.reasoning,
    this.sector,
    required this.selectedForTrading,
  });

  bool get isBullish => thesis == 'BULLISH';
  bool get isBearish => thesis == 'BEARISH';
  bool get isNeutral => thesis == 'NEUTRAL';

  int get confidencePercent => (confidence * 100).round();

  factory Thesis.fromJson(Map<String, dynamic> json) {
    return Thesis(
      ticker: json['ticker'] as String,
      thesis: json['thesis'] as String,
      confidence: (json['confidence'] as num).toDouble(),
      targetEntryPrice: (json['target_entry_price'] as num?)?.toDouble(),
      stopLossPrice: (json['stop_loss_price'] as num?)?.toDouble(),
      takeProfitPrice: (json['take_profit_price'] as num?)?.toDouble(),
      thesisBreachCondition: json['thesis_breach_condition'] as String? ?? '',
      reasoning: json['reasoning'] as String? ?? '',
      sector: json['sector'] as String?,
      selectedForTrading: json['selected_for_trading'] as bool? ?? false,
    );
  }
}

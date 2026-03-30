class PriceCheckResult {
  final DateTime generatedAt;
  final double? spyChangePct;
  final bool marketStress;
  final int positionsChecked;
  final int aborts;
  final List<PriceCheckAction> actions;

  const PriceCheckResult({
    required this.generatedAt,
    this.spyChangePct,
    required this.marketStress,
    required this.positionsChecked,
    required this.aborts,
    required this.actions,
  });

  factory PriceCheckResult.fromJson(Map<String, dynamic> json) {
    return PriceCheckResult(
      generatedAt: DateTime.parse(json['generated_at'] as String),
      spyChangePct: (json['spy_change_pct'] as num?)?.toDouble(),
      marketStress: json['market_stress'] as bool? ?? false,
      positionsChecked: json['positions_checked'] as int? ?? 0,
      aborts: json['aborts'] as int? ?? 0,
      actions: (json['actions'] as List<dynamic>? ?? [])
          .map((a) => PriceCheckAction.fromJson(a as Map<String, dynamic>))
          .toList(),
    );
  }
}

class PriceCheckAction {
  final String ticker;
  final String action;
  final int shares;
  final double price;
  final String trigger;
  final String reasoning;
  final DateTime timestamp;

  const PriceCheckAction({
    required this.ticker,
    required this.action,
    required this.shares,
    required this.price,
    required this.trigger,
    required this.reasoning,
    required this.timestamp,
  });

  factory PriceCheckAction.fromJson(Map<String, dynamic> json) {
    return PriceCheckAction(
      ticker: json['ticker'] as String? ?? '',
      action: json['action'] as String? ?? '',
      shares: json['shares'] as int? ?? 0,
      price: (json['price'] as num?)?.toDouble() ?? 0,
      trigger: json['trigger'] as String? ?? '',
      reasoning: json['reasoning'] as String? ?? '',
      timestamp: DateTime.parse(json['timestamp'] as String),
    );
  }
}

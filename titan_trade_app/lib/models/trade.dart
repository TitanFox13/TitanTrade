import 'near_miss.dart';

class Trade {
  final String id;
  final String ticker;
  final String action;
  final int shares;
  final double price;
  final double totalValue;
  final DateTime timestamp;
  final String trigger;
  final String? thesisId;
  final String reasoning;
  final double? confidence;
  final double? stopLossPrice;
  final double? takeProfitPrice;
  final List<String> riskFlags;
  final Map<String, GateResult> gateResults;
  final TradeContext? context;

  const Trade({
    required this.id,
    required this.ticker,
    required this.action,
    required this.shares,
    required this.price,
    required this.totalValue,
    required this.timestamp,
    required this.trigger,
    this.thesisId,
    required this.reasoning,
    this.confidence,
    this.stopLossPrice,
    this.takeProfitPrice,
    this.riskFlags = const [],
    this.gateResults = const {},
    this.context,
  });

  bool get isBuy => action == 'BUY';

  factory Trade.fromJson(Map<String, dynamic> json) {
    final gateResultsRaw = json['gate_results'] as Map<String, dynamic>? ?? {};
    final gateResults = gateResultsRaw.map(
      (key, value) => MapEntry(key, GateResult.fromJson(value as Map<String, dynamic>)),
    );

    return Trade(
      id: json['id'] as String? ?? '',
      ticker: json['ticker'] as String,
      action: json['action'] as String,
      shares: json['shares'] as int,
      price: (json['price'] as num).toDouble(),
      totalValue: (json['total_value'] as num).toDouble(),
      timestamp: DateTime.parse(json['timestamp'] as String),
      trigger: json['trigger'] as String,
      thesisId: json['thesis_id'] as String?,
      reasoning: json['reasoning'] as String? ?? '',
      confidence: (json['confidence'] as num?)?.toDouble(),
      stopLossPrice: (json['stop_loss_price'] as num?)?.toDouble(),
      takeProfitPrice: (json['take_profit_price'] as num?)?.toDouble(),
      riskFlags: (json['risk_flags'] as List<dynamic>?)
              ?.map((f) => f as String)
              .toList() ??
          [],
      gateResults: gateResults,
      context: json['context'] != null
          ? TradeContext.fromJson(json['context'] as Map<String, dynamic>)
          : null,
    );
  }
}

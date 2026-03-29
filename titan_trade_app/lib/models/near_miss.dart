class NearMiss {
  final String id;
  final DateTime timestamp;
  final String ticker;
  final double confidence;
  final String thesis;
  final double? targetEntryPrice;
  final double? stopLossPrice;
  final double? takeProfitPrice;
  final String reasoning;
  final List<String> failedGates;
  final Map<String, GateResult> gateResults;
  final int totalGatesFailed;
  final TradeContext? context;

  const NearMiss({
    required this.id,
    required this.timestamp,
    required this.ticker,
    required this.confidence,
    required this.thesis,
    this.targetEntryPrice,
    this.stopLossPrice,
    this.takeProfitPrice,
    required this.reasoning,
    required this.failedGates,
    required this.gateResults,
    required this.totalGatesFailed,
    this.context,
  });

  int get confidencePercent => (confidence * 100).round();

  factory NearMiss.fromJson(Map<String, dynamic> json) {
    final gateResultsRaw = json['gate_results'] as Map<String, dynamic>? ?? {};
    final gateResults = gateResultsRaw.map(
      (key, value) => MapEntry(key, GateResult.fromJson(value as Map<String, dynamic>)),
    );

    return NearMiss(
      id: json['id'] as String? ?? '',
      timestamp: DateTime.parse(json['timestamp'] as String),
      ticker: json['ticker'] as String,
      confidence: (json['confidence'] as num).toDouble(),
      thesis: json['thesis'] as String,
      targetEntryPrice: (json['target_entry_price'] as num?)?.toDouble(),
      stopLossPrice: (json['stop_loss_price'] as num?)?.toDouble(),
      takeProfitPrice: (json['take_profit_price'] as num?)?.toDouble(),
      reasoning: json['reasoning'] as String? ?? '',
      failedGates: (json['failed_gates'] as List<dynamic>?)
              ?.map((g) => g as String)
              .toList() ??
          [],
      gateResults: gateResults,
      totalGatesFailed: json['total_gates_failed'] as int? ?? 0,
      context: json['context'] != null
          ? TradeContext.fromJson(json['context'] as Map<String, dynamic>)
          : null,
    );
  }
}

class GateResult {
  final bool passed;
  final String detail;

  const GateResult({required this.passed, required this.detail});

  factory GateResult.fromJson(Map<String, dynamic> json) {
    return GateResult(
      passed: json['passed'] as bool? ?? false,
      detail: json['detail'] as String? ?? '',
    );
  }
}

class TradeContext {
  final String? marketRegime;
  final double? vixLevel;
  final String? vixClassification;
  final double? spyReturn1d;
  final TechnicalSnapshot? technicals;
  final String? sentrySignal;
  final String? sentryReasoning;
  final List<String> recentNews;
  final int? earningsDaysAway;
  final String? sector;

  const TradeContext({
    this.marketRegime,
    this.vixLevel,
    this.vixClassification,
    this.spyReturn1d,
    this.technicals,
    this.sentrySignal,
    this.sentryReasoning,
    this.recentNews = const [],
    this.earningsDaysAway,
    this.sector,
  });

  factory TradeContext.fromJson(Map<String, dynamic> json) {
    return TradeContext(
      marketRegime: json['market_regime'] as String?,
      vixLevel: (json['vix_level'] as num?)?.toDouble(),
      vixClassification: json['vix_classification'] as String?,
      spyReturn1d: (json['spy_return_1d'] as num?)?.toDouble(),
      technicals: json['technicals'] != null
          ? TechnicalSnapshot.fromJson(json['technicals'] as Map<String, dynamic>)
          : null,
      sentrySignal: json['sentry_signal'] as String?,
      sentryReasoning: json['sentry_reasoning'] as String?,
      recentNews: (json['recent_news'] as List<dynamic>?)
              ?.map((n) => n as String)
              .toList() ??
          [],
      earningsDaysAway: json['earnings_days_away'] as int?,
      sector: json['sector'] as String?,
    );
  }
}

class TechnicalSnapshot {
  final double? rsi14;
  final double? macdHistogram;
  final double? atr14;
  final String? priceVsSma50;
  final String? priceVsSma200;

  const TechnicalSnapshot({
    this.rsi14,
    this.macdHistogram,
    this.atr14,
    this.priceVsSma50,
    this.priceVsSma200,
  });

  factory TechnicalSnapshot.fromJson(Map<String, dynamic> json) {
    return TechnicalSnapshot(
      rsi14: (json['rsi_14'] as num?)?.toDouble(),
      macdHistogram: (json['macd_histogram'] as num?)?.toDouble(),
      atr14: (json['atr_14'] as num?)?.toDouble(),
      priceVsSma50: json['price_vs_sma_50'] as String?,
      priceVsSma200: json['price_vs_sma_200'] as String?,
    );
  }
}

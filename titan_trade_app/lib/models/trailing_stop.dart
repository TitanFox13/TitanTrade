class TrailingStopState {
  final String ticker;
  final double entryPrice;
  final double highWaterMark;
  final double? trailingStopPrice;
  final bool trailingActive;
  final DateTime? lastUpdated;

  const TrailingStopState({
    required this.ticker,
    required this.entryPrice,
    required this.highWaterMark,
    this.trailingStopPrice,
    required this.trailingActive,
    this.lastUpdated,
  });

  double get gainFromEntry =>
      entryPrice > 0 ? (highWaterMark - entryPrice) / entryPrice : 0;

  factory TrailingStopState.fromEntry(String ticker, Map<String, dynamic> json) {
    return TrailingStopState(
      ticker: ticker,
      entryPrice: (json['entry_price'] as num?)?.toDouble() ?? 0,
      highWaterMark: (json['high_water_mark'] as num?)?.toDouble() ?? 0,
      trailingStopPrice: (json['trailing_stop_price'] as num?)?.toDouble(),
      trailingActive: json['trailing_active'] as bool? ?? false,
      lastUpdated: json['last_updated'] != null
          ? DateTime.tryParse(json['last_updated'] as String)
          : null,
    );
  }

  static Map<String, TrailingStopState> fromJson(Map<String, dynamic> json) {
    return json.map(
      (ticker, value) => MapEntry(
        ticker,
        TrailingStopState.fromEntry(ticker, value as Map<String, dynamic>),
      ),
    );
  }
}

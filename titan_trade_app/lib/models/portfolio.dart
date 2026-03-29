class Portfolio {
  final DateTime? lastUpdated;
  final double cashBalance;
  final List<Position> positions;

  const Portfolio({
    required this.lastUpdated,
    required this.cashBalance,
    required this.positions,
  });

  double get investedValue =>
      positions.fold(0.0, (sum, p) => sum + (p.currentPrice ?? p.entryPrice) * p.shares);

  double get totalValue => cashBalance + investedValue;

  double get totalUnrealizedPnl =>
      positions.fold(0.0, (sum, p) => sum + (p.unrealizedPnl ?? 0));

  factory Portfolio.fromJson(Map<String, dynamic> json) {
    return Portfolio(
      lastUpdated: json['last_updated'] != null
          ? DateTime.parse(json['last_updated'] as String)
          : null,
      cashBalance: (json['cash_balance'] as num).toDouble(),
      positions: (json['positions'] as List<dynamic>)
          .map((p) => Position.fromJson(p as Map<String, dynamic>))
          .toList(),
    );
  }

  static const empty = Portfolio(lastUpdated: null, cashBalance: 0, positions: []);
}

class Position {
  final String ticker;
  final int shares;
  final double entryPrice;
  final String entryDate;
  final double? currentPrice;
  final double? stopLossPrice;
  final double? unrealizedPnl;

  const Position({
    required this.ticker,
    required this.shares,
    required this.entryPrice,
    required this.entryDate,
    this.currentPrice,
    this.stopLossPrice,
    this.unrealizedPnl,
  });

  double get marketValue => (currentPrice ?? entryPrice) * shares;
  double get costBasis => entryPrice * shares;
  double get pnlPercent => costBasis > 0 ? ((marketValue - costBasis) / costBasis) * 100 : 0;

  factory Position.fromJson(Map<String, dynamic> json) {
    return Position(
      ticker: json['ticker'] as String,
      shares: json['shares'] as int,
      entryPrice: (json['entry_price'] as num).toDouble(),
      entryDate: json['entry_date'] as String,
      currentPrice: (json['current_price'] as num?)?.toDouble(),
      stopLossPrice: (json['stop_loss_price'] as num?)?.toDouble(),
      unrealizedPnl: (json['unrealized_pnl'] as num?)?.toDouble(),
    );
  }
}

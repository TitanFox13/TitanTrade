class BacktestResult {
  final BacktestConfig config;
  final BacktestMetrics metrics;
  final int tradeCount;

  const BacktestResult({
    required this.config,
    required this.metrics,
    required this.tradeCount,
  });

  factory BacktestResult.fromJson(Map<String, dynamic> json) {
    return BacktestResult(
      config: BacktestConfig.fromJson(json['config'] as Map<String, dynamic>? ?? {}),
      metrics: BacktestMetrics.fromJson(json['metrics'] as Map<String, dynamic>? ?? {}),
      tradeCount: json['trade_count'] as int? ?? 0,
    );
  }
}

class BacktestConfig {
  final double initialCapital;
  final List<String> tickers;
  final String? startDate;
  final String? endDate;
  final int tradingDays;

  const BacktestConfig({
    required this.initialCapital,
    required this.tickers,
    this.startDate,
    this.endDate,
    required this.tradingDays,
  });

  factory BacktestConfig.fromJson(Map<String, dynamic> json) {
    return BacktestConfig(
      initialCapital: (json['initial_capital'] as num?)?.toDouble() ?? 100000,
      tickers: (json['tickers'] as List<dynamic>?)?.map((e) => e as String).toList() ?? [],
      startDate: json['start_date'] as String?,
      endDate: json['end_date'] as String?,
      tradingDays: json['trading_days'] as int? ?? 0,
    );
  }
}

class BacktestMetrics {
  final double totalReturnPct;
  final double spyReturnPct;
  final double alphaPct;
  final double finalValue;
  final int totalTrades;
  final double winRate;
  final double avgWinPct;
  final double avgLossPct;
  final double profitFactor;
  final double maxDrawdownPct;
  final int maxDrawdownDays;
  final double sharpeRatio;
  final double sortinoRatio;
  final double avgHoldingDays;
  final Map<String, int> exitTriggers;

  const BacktestMetrics({
    required this.totalReturnPct,
    required this.spyReturnPct,
    required this.alphaPct,
    required this.finalValue,
    required this.totalTrades,
    required this.winRate,
    required this.avgWinPct,
    required this.avgLossPct,
    required this.profitFactor,
    required this.maxDrawdownPct,
    required this.maxDrawdownDays,
    required this.sharpeRatio,
    required this.sortinoRatio,
    required this.avgHoldingDays,
    required this.exitTriggers,
  });

  factory BacktestMetrics.fromJson(Map<String, dynamic> json) {
    return BacktestMetrics(
      totalReturnPct: (json['total_return_pct'] as num?)?.toDouble() ?? 0,
      spyReturnPct: (json['spy_return_pct'] as num?)?.toDouble() ?? 0,
      alphaPct: (json['alpha_pct'] as num?)?.toDouble() ?? 0,
      finalValue: (json['final_value'] as num?)?.toDouble() ?? 0,
      totalTrades: json['total_trades'] as int? ?? 0,
      winRate: (json['win_rate'] as num?)?.toDouble() ?? 0,
      avgWinPct: (json['avg_win_pct'] as num?)?.toDouble() ?? 0,
      avgLossPct: (json['avg_loss_pct'] as num?)?.toDouble() ?? 0,
      profitFactor: (json['profit_factor'] as num?)?.toDouble() ?? 0,
      maxDrawdownPct: (json['max_drawdown_pct'] as num?)?.toDouble() ?? 0,
      maxDrawdownDays: json['max_drawdown_days'] as int? ?? 0,
      sharpeRatio: (json['sharpe_ratio'] as num?)?.toDouble() ?? 0,
      sortinoRatio: (json['sortino_ratio'] as num?)?.toDouble() ?? 0,
      avgHoldingDays: (json['avg_holding_days'] as num?)?.toDouble() ?? 0,
      exitTriggers: (json['exit_triggers'] as Map<String, dynamic>?)
              ?.map((k, v) => MapEntry(k, (v as num).toInt())) ??
          {},
    );
  }
}

class SentryBundle {
  final DateTime generatedAt;
  final String runType;
  final List<SentrySignal> signals;
  final SentryFailures? failures;

  const SentryBundle({
    required this.generatedAt,
    required this.runType,
    required this.signals,
    this.failures,
  });

  factory SentryBundle.fromJson(Map<String, dynamic> json) {
    return SentryBundle(
      generatedAt: DateTime.parse(json['generated_at'] as String),
      runType: json['run_type'] as String? ?? '',
      signals: (json['signals'] as List<dynamic>)
          .map((s) => SentrySignal.fromJson(s as Map<String, dynamic>))
          .toList(),
      failures: json['failures'] == null
          ? null
          : SentryFailures.fromJson(json['failures'] as Map<String, dynamic>),
    );
  }
}

/// Summary of sentry check health. When Gemini is rate-limited or down,
/// sentry checks fall back to heuristic defaults (price-based ABORT still
/// runs, but news-based ABORT is offline). A high [fallbackRatio] means the
/// news layer is degraded.
class SentryFailures {
  final int fallbackCount;
  final int checksRun;
  final double fallbackRatio;

  const SentryFailures({
    required this.fallbackCount,
    required this.checksRun,
    required this.fallbackRatio,
  });

  /// True when more than 30% of sentry checks used heuristic fallbacks —
  /// matches the server-side threshold that triggers a Discord alert.
  bool get isDegraded => fallbackRatio > 0.30 && checksRun >= 3;

  factory SentryFailures.fromJson(Map<String, dynamic> json) {
    return SentryFailures(
      fallbackCount: (json['fallback_count'] as num?)?.toInt() ?? 0,
      checksRun: (json['checks_run'] as num?)?.toInt() ?? 0,
      fallbackRatio: (json['fallback_ratio'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

class SentrySignal {
  final String ticker;
  final String signal;
  final List<String> conflictingHeadlines;
  final String reasoning;

  const SentrySignal({
    required this.ticker,
    required this.signal,
    required this.conflictingHeadlines,
    required this.reasoning,
  });

  bool get isContinue => signal == 'CONTINUE';
  bool get isAbort => signal == 'ABORT';

  factory SentrySignal.fromJson(Map<String, dynamic> json) {
    return SentrySignal(
      ticker: json['ticker'] as String,
      signal: json['signal'] as String,
      conflictingHeadlines: (json['conflicting_headlines'] as List<dynamic>?)
              ?.map((h) => h as String)
              .toList() ??
          [],
      reasoning: json['reasoning'] as String? ?? '',
    );
  }
}

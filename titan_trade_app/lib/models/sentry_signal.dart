class SentryBundle {
  final DateTime generatedAt;
  final String runType;
  final List<SentrySignal> signals;

  const SentryBundle({
    required this.generatedAt,
    required this.runType,
    required this.signals,
  });

  factory SentryBundle.fromJson(Map<String, dynamic> json) {
    return SentryBundle(
      generatedAt: DateTime.parse(json['generated_at'] as String),
      runType: json['run_type'] as String? ?? '',
      signals: (json['signals'] as List<dynamic>)
          .map((s) => SentrySignal.fromJson(s as Map<String, dynamic>))
          .toList(),
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

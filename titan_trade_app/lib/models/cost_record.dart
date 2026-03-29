class CostRecord {
  final String id;
  final DateTime timestamp;
  final String service;
  final String model;
  final String description;
  final int inputTokens;
  final int outputTokens;
  final double estimatedCostUsd;
  final String? runType;

  const CostRecord({
    required this.id,
    required this.timestamp,
    required this.service,
    required this.model,
    required this.description,
    required this.inputTokens,
    required this.outputTokens,
    required this.estimatedCostUsd,
    this.runType,
  });

  factory CostRecord.fromJson(Map<String, dynamic> json) {
    return CostRecord(
      id: json['id'] as String? ?? '',
      timestamp: DateTime.parse(json['timestamp'] as String),
      service: json['service'] as String? ?? '',
      model: json['model'] as String? ?? '',
      description: json['description'] as String? ?? '',
      inputTokens: (json['input_tokens'] as num?)?.toInt() ?? 0,
      outputTokens: (json['output_tokens'] as num?)?.toInt() ?? 0,
      estimatedCostUsd: (json['estimated_cost_usd'] as num?)?.toDouble() ?? 0,
      runType: json['run_type'] as String?,
    );
  }

  int get totalTokens => inputTokens + outputTokens;
}

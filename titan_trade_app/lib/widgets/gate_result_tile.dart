import 'package:flutter/material.dart';

import '../models/near_miss.dart';

class GateResultTile extends StatelessWidget {
  final String gateName;
  final GateResult result;

  const GateResultTile({super.key, required this.gateName, required this.result});

  static const _gateLabels = {
    'confidence': 'Confidence Threshold',
    'earnings': 'Earnings Blackout',
    'drawdown': 'Drawdown Circuit Breaker',
    'cash_reserve': 'Cash Reserve',
    'position_size': 'Position Sizing',
    'sector_exposure': 'Sector Exposure',
  };

  static const _gateIcons = {
    'confidence': Icons.psychology,
    'earnings': Icons.event_busy,
    'drawdown': Icons.trending_down,
    'cash_reserve': Icons.account_balance_wallet,
    'position_size': Icons.pie_chart,
    'sector_exposure': Icons.category,
  };

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final label = _gateLabels[gateName] ?? gateName;
    final icon = _gateIcons[gateName] ?? Icons.shield;
    final color = result.passed ? Colors.green : Colors.red;

    return ListTile(
      dense: true,
      leading: Icon(
        result.passed ? Icons.check_circle : Icons.cancel,
        color: color,
        size: 20,
      ),
      title: Row(
        children: [
          Icon(icon, size: 16, color: theme.colorScheme.onSurfaceVariant),
          const SizedBox(width: 8),
          Text(label, style: theme.textTheme.bodyMedium),
        ],
      ),
      subtitle: Text(result.detail, style: theme.textTheme.bodySmall),
    );
  }
}

class GateResultsCard extends StatelessWidget {
  final Map<String, GateResult> gateResults;

  const GateResultsCard({super.key, required this.gateResults});

  static const _gateOrder = [
    'confidence',
    'earnings',
    'drawdown',
    'cash_reserve',
    'position_size',
    'sector_exposure',
  ];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final passed = gateResults.values.where((g) => g.passed).length;
    final total = gateResults.length;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text('Risk Gates', style: theme.textTheme.titleSmall),
                const Spacer(),
                Text('$passed/$total passed', style: theme.textTheme.bodySmall),
              ],
            ),
            const Divider(),
            for (final gate in _gateOrder)
              if (gateResults.containsKey(gate))
                GateResultTile(gateName: gate, result: gateResults[gate]!),
          ],
        ),
      ),
    );
  }
}
